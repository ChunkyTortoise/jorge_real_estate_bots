from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text

from bots.shared.auth_middleware import get_current_active_user
from bots.shared.config import settings
from bots.shared.ghl_client import GHLClient
from database.billing_models import AgencyModel, OnboardingStateModel
from database.models import DealModel, LeadModel, PlaybookApplicationModel, RoiReportModel
from database.session import AsyncSessionFactory

router = APIRouter(prefix="/api", tags=["productization"])

ARTIFACTS_DIR = Path("storage/productization")
PLAYBOOK_FILE = ARTIFACTS_DIR / "playbook_applications.json"
REPORTS_DIR = ARTIFACTS_DIR / "reports"
REPORT_INDEX_FILE = ARTIFACTS_DIR / "report_index.json"


@dataclass(frozen=True)
class PlaybookPreset:
    id: str
    name: str
    version: str
    description: str
    min_price: int
    max_price: int
    commission: float
    service_areas: list[str]


PLAYBOOKS: dict[str, PlaybookPreset] = {
    "solo-agent": PlaybookPreset(
        id="solo-agent",
        name="Solo Agent",
        version="1.0.0",
        description="Single-agent setup with lightweight qualification and routing.",
        min_price=180000,
        max_price=700000,
        commission=0.06,
        service_areas=["Rancho Cucamonga", "Ontario", "Upland"],
    ),
    "small-team": PlaybookPreset(
        id="small-team",
        name="Small Team",
        version="1.0.0",
        description="Balanced setup for 3-10 agents with broader lead routing.",
        min_price=200000,
        max_price=950000,
        commission=0.055,
        service_areas=["Rancho Cucamonga", "Ontario", "Upland", "Fontana", "Chino Hills"],
    ),
    "isa-team": PlaybookPreset(
        id="isa-team",
        name="ISA Team",
        version="1.0.0",
        description="High-volume ISA workflow with tighter response SLAs and expanded territory.",
        min_price=220000,
        max_price=1200000,
        commission=0.05,
        service_areas=[
            "Rancho Cucamonga",
            "Ontario",
            "Upland",
            "Fontana",
            "Chino Hills",
            "Riverside",
            "Claremont",
        ],
    ),
}


class CredentialValidationRequest(BaseModel):
    ghl_api_key: str
    ghl_location_id: str
    anthropic_api_key: str
    redis_url: str | None = None
    database_url: str | None = None
    live_check: bool = False


class OnboardingBootstrapRequest(BaseModel):
    agency_id: str | None = None
    agency_name: str = Field(min_length=2, max_length=255)
    agency_slug: str = Field(min_length=2, max_length=255)
    agency_email: str
    ghl_api_key: str
    ghl_location_id: str
    playbook_id: str = Field(default="solo-agent")


class PlaybookApplyRequest(BaseModel):
    agency_id: str
    playbook_id: str
    version: str | None = None
    overwrite: bool = False


class ReportGenerateRequest(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    format: str = Field(default="both", pattern="^(json|html|both)$")


def _ensure_dirs() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def _playbook_or_404(playbook_id: str) -> PlaybookPreset:
    playbook = PLAYBOOKS.get(playbook_id)
    if not playbook:
        raise HTTPException(status_code=404, detail=f"Unknown playbook: {playbook_id}")
    return playbook


def _resolve_user_role(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("role", "viewer"))
    return str(getattr(user, "role", "viewer"))


def _require_role(user: Any, allowed: set[str]) -> None:
    role = _resolve_user_role(user)
    rank = {"viewer": 1, "operator": 2, "admin": 3}
    if role not in rank:
        raise HTTPException(status_code=403, detail="Unknown user role")
    min_allowed = min(rank[r] for r in allowed)
    if rank[role] < min_allowed:
        raise HTTPException(status_code=403, detail="Insufficient role permissions")


def _apply_playbook_to_agency(agency: AgencyModel, playbook: PlaybookPreset) -> None:
    agency.min_price = playbook.min_price
    agency.max_price = playbook.max_price
    agency.standard_commission = playbook.commission
    agency.service_areas = ",".join(playbook.service_areas)


def _user_id_from_user(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("id", "system"))
    return str(getattr(user, "id", "system"))


async def _resolve_agency_id(user: Any) -> str:
    if isinstance(user, dict) and user.get("agency_id"):
        return str(user["agency_id"])
    agency_id = getattr(user, "agency_id", None)
    if agency_id:
        return str(agency_id)

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(AgencyModel.id).limit(1))
        existing = result.scalars().first()
        if existing:
            return str(existing)

    return "demo-agency"


@router.get("/playbooks")
async def list_playbooks(user=Depends(get_current_active_user())) -> dict[str, Any]:
    _require_role(user, {"viewer"})
    return {
        "playbooks": [asdict(playbook) for playbook in PLAYBOOKS.values()],
        "count": len(PLAYBOOKS),
    }


@router.post("/onboarding/validate-credentials")
async def validate_credentials(
    payload: CredentialValidationRequest,
    user=Depends(get_current_active_user()),
) -> dict[str, Any]:
    _require_role(user, {"operator"})
    checks: list[dict[str, Any]] = []

    def add_check(name: str, ok: bool, remediation: str, details: str = "") -> None:
        checks.append(
            {
                "name": name,
                "ok": ok,
                "details": details,
                "remediation": remediation if not ok else "",
            }
        )

    add_check(
        "ghl_api_key",
        payload.ghl_api_key.startswith("eyJ") and len(payload.ghl_api_key) > 20,
        "Provide a valid GoHighLevel JWT API key.",
        "JWT format expected",
    )
    add_check(
        "ghl_location_id",
        len(payload.ghl_location_id.strip()) > 5,
        "Set a valid GoHighLevel location ID.",
    )
    add_check(
        "anthropic_api_key",
        payload.anthropic_api_key.startswith("sk-") and len(payload.anthropic_api_key) > 20,
        "Set a valid Anthropic API key in onboarding credentials.",
    )

    if payload.redis_url:
        add_check(
            "redis_url",
            payload.redis_url.startswith("redis://") or payload.redis_url.startswith("rediss://"),
            "Use redis:// or rediss:// URL.",
        )
    if payload.database_url:
        add_check(
            "database_url",
            payload.database_url.startswith("postgresql://") or payload.database_url.startswith("postgresql+asyncpg://"),
            "Use a PostgreSQL connection string.",
        )

    if payload.live_check:
        try:
            client = GHLClient(api_key=payload.ghl_api_key, location_id=payload.ghl_location_id)
            health_result = await client.health_check()
            add_check(
                "ghl_live_api",
                bool(health_result.get("success")),
                "Verify GoHighLevel API key and location permissions.",
                details="Live API call to GHL /locations endpoint",
            )
        except Exception as exc:  # pragma: no cover - network/runtime specific
            add_check(
                "ghl_live_api",
                False,
                "Verify outbound network and GHL credentials.",
                details=str(exc),
            )

    all_ok = all(item["ok"] for item in checks)
    return {
        "valid": all_ok,
        "checks": checks,
        "next_step": "POST /api/onboarding/bootstrap" if all_ok else "Fix failed checks and retry.",
    }


@router.post("/onboarding/bootstrap")
async def bootstrap_onboarding(
    payload: OnboardingBootstrapRequest,
    user=Depends(get_current_active_user()),
) -> dict[str, Any]:
    _require_role(user, {"operator"})
    _ensure_dirs()
    playbook = _playbook_or_404(payload.playbook_id)
    agency_id = payload.agency_id or await _resolve_agency_id(user)

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(AgencyModel).where(AgencyModel.id == agency_id))
        agency = result.scalar_one_or_none()

        if agency is None:
            agency = AgencyModel(
                id=agency_id,
                name=payload.agency_name,
                slug=_slugify(payload.agency_slug),
                email=payload.agency_email,
                ghl_api_key=payload.ghl_api_key,
                ghl_location_id=payload.ghl_location_id,
                onboarding_completed=False,
                onboarding_step="credentials_connected",
            )
            session.add(agency)
            created = True
        else:
            agency.name = payload.agency_name
            agency.slug = _slugify(payload.agency_slug)
            agency.email = payload.agency_email
            agency.ghl_api_key = payload.ghl_api_key
            agency.ghl_location_id = payload.ghl_location_id
            agency.updated_at = datetime.now(UTC)
            created = False

        _apply_playbook_to_agency(agency, playbook)
        agency.onboarding_step = "playbook_applied"

        state_result = await session.execute(
            select(OnboardingStateModel).where(OnboardingStateModel.agency_id == agency_id)
        )
        state = state_result.scalar_one_or_none()
        if state is None:
            state = OnboardingStateModel(
                id=str(uuid.uuid4()),
                agency_id=agency_id,
                current_step="completed",
                step_ghl_connected=True,
                step_agents_configured=True,
                step_territory_set=True,
            )
            session.add(state)
        else:
            state.current_step = "completed"
            state.step_ghl_connected = True
            state.step_agents_configured = True
            state.step_territory_set = True
            state.updated_at = datetime.now(UTC)

        agency.onboarding_completed = True
        applied_by = _user_id_from_user(user)
        existing_app = (
            await session.execute(
                select(PlaybookApplicationModel).where(
                    PlaybookApplicationModel.agency_id == agency_id,
                    PlaybookApplicationModel.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if existing_app is None:
            session.add(
                PlaybookApplicationModel(
                    agency_id=agency_id,
                    playbook_id=playbook.id,
                    version=playbook.version,
                    applied_by=applied_by,
                    metadata_json={"source": "onboarding_bootstrap"},
                )
            )
        else:
            existing_app.playbook_id = playbook.id
            existing_app.version = playbook.version
            existing_app.applied_by = applied_by
            existing_app.metadata_json = {"source": "onboarding_bootstrap"}
            existing_app.applied_at = datetime.now(UTC)
            existing_app.updated_at = datetime.now(UTC)
        await session.commit()

    applications = _load_json(PLAYBOOK_FILE, {})
    applications[agency_id] = {
        "agency_id": agency_id,
        "playbook_id": playbook.id,
        "playbook_version": playbook.version,
        "applied_at": datetime.now(UTC).isoformat(),
    }
    _save_json(PLAYBOOK_FILE, applications)

    return {
        "agency_id": agency_id,
        "created": created,
        "onboarding_completed": True,
        "playbook": asdict(playbook),
        "checklist": [
            "Credentials validated",
            "Agency profile stored",
            "Playbook applied",
            "Readiness status marked complete",
        ],
    }


@router.get("/integrations/health")
async def integration_health(user=Depends(get_current_active_user())) -> dict[str, Any]:
    _require_role(user, {"viewer"})
    checks: list[dict[str, Any]] = []

    # Database
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        checks.append({"name": "database", "status": "healthy", "remediation": ""})
    except Exception as exc:
        checks.append(
            {
                "name": "database",
                "status": "unhealthy",
                "remediation": "Confirm DATABASE_URL and DB reachability.",
                "details": str(exc),
            }
        )

    # Redis
    redis_status = "healthy"
    redis_remediation = ""
    redis_details = ""
    try:
        from bots.shared.cache_service import RedisCache

        cache = RedisCache(settings.redis_url)
        if getattr(cache, "enabled", False) and getattr(cache, "redis", None) is not None:
            await cache.redis.ping()
        else:
            redis_status = "degraded"
            redis_remediation = "Redis unavailable; app is running with memory cache fallback."
    except Exception as exc:
        redis_status = "unhealthy"
        redis_remediation = "Check REDIS_URL connectivity and credentials."
        redis_details = str(exc)

    checks.append(
        {
            "name": "redis",
            "status": redis_status,
            "remediation": redis_remediation,
            "details": redis_details,
        }
    )

    # GHL
    try:
        has_ghl = bool(settings.ghl_api_key and settings.ghl_location_id)
        checks.append(
            {
                "name": "gohighlevel",
                "status": "healthy" if has_ghl else "unhealthy",
                "remediation": "Set GHL_API_KEY and GHL_LOCATION_ID in environment." if not has_ghl else "",
            }
        )
    except Exception as exc:
        checks.append(
            {
                "name": "gohighlevel",
                "status": "unhealthy",
                "remediation": "Set valid GoHighLevel credentials.",
                "details": str(exc),
            }
        )

    # Model provider
    has_model_key = bool(settings.anthropic_api_key)
    checks.append(
        {
            "name": "model_provider",
            "status": "healthy" if has_model_key else "unhealthy",
            "remediation": "Set ANTHROPIC_API_KEY for lead analysis." if not has_model_key else "",
        }
    )

    # Webhook signature
    has_webhook_signing = bool(settings.ghl_webhook_secret or settings.ghl_webhook_public_key)
    checks.append(
        {
            "name": "webhook_signing",
            "status": "healthy" if has_webhook_signing else "degraded",
            "remediation": "Set GHL_WEBHOOK_SECRET or GHL_WEBHOOK_PUBLIC_KEY to enforce signature verification."
            if not has_webhook_signing
            else "",
        }
    )

    unhealthy = [c for c in checks if c["status"] == "unhealthy"]
    degraded = [c for c in checks if c["status"] == "degraded"]
    overall = "healthy"
    if unhealthy:
        overall = "unhealthy"
    elif degraded:
        overall = "degraded"

    return {
        "status": overall,
        "checked_at": datetime.now(UTC).isoformat(),
        "checks": checks,
        "summary": {
            "healthy": len([c for c in checks if c["status"] == "healthy"]),
            "degraded": len(degraded),
            "unhealthy": len(unhealthy),
        },
    }


@router.post("/playbooks/apply")
async def apply_playbook(payload: PlaybookApplyRequest, user=Depends(get_current_active_user())) -> dict[str, Any]:
    _require_role(user, {"operator"})
    _ensure_dirs()
    playbook = _playbook_or_404(payload.playbook_id)
    desired_version = payload.version or playbook.version

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(AgencyModel).where(AgencyModel.id == payload.agency_id))
        agency = result.scalar_one_or_none()
        if agency is None:
            raise HTTPException(status_code=404, detail="Agency not found. Run onboarding bootstrap first.")

        existing = (
            await session.execute(
                select(PlaybookApplicationModel).where(
                    PlaybookApplicationModel.agency_id == payload.agency_id,
                    PlaybookApplicationModel.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if existing and not payload.overwrite:
            if existing.playbook_id == playbook.id and existing.version == desired_version:
                return {
                    "agency_id": payload.agency_id,
                    "idempotent": True,
                    "message": "Playbook already applied with matching version.",
                    "playbook": asdict(playbook),
                }

        _apply_playbook_to_agency(agency, playbook)
        agency.updated_at = datetime.now(UTC)
        if existing is None:
            session.add(
                PlaybookApplicationModel(
                    agency_id=payload.agency_id,
                    playbook_id=playbook.id,
                    version=desired_version,
                    applied_by=_user_id_from_user(user),
                    metadata_json={"source": "playbooks_apply"},
                )
            )
        else:
            existing.playbook_id = playbook.id
            existing.version = desired_version
            existing.applied_by = _user_id_from_user(user)
            existing.metadata_json = {"source": "playbooks_apply"}
            existing.applied_at = datetime.now(UTC)
            existing.updated_at = datetime.now(UTC)
        await session.commit()

    applications = _load_json(PLAYBOOK_FILE, {})
    applications[payload.agency_id] = {
        "agency_id": payload.agency_id,
        "playbook_id": playbook.id,
        "playbook_version": desired_version,
        "applied_at": datetime.now(UTC).isoformat(),
    }
    _save_json(PLAYBOOK_FILE, applications)

    return {
        "agency_id": payload.agency_id,
        "idempotent": False,
        "playbook": asdict(playbook),
        "version": desired_version,
    }


def _date_range_or_default(date_from: datetime | None, date_to: datetime | None) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    end = date_to or now
    start = date_from or (end - timedelta(days=30))
    return start, end


async def _compute_roi_summary(session, start: datetime, end: datetime) -> dict[str, Any]:
    leads_count = (
        await session.execute(
            select(func.count(LeadModel.id)).where(LeadModel.created_at >= start, LeadModel.created_at <= end)
        )
    ).scalar_one()
    qualified_count = (
        await session.execute(
            select(func.count(LeadModel.id)).where(
                LeadModel.created_at >= start,
                LeadModel.created_at <= end,
                LeadModel.is_qualified.is_(True),
            )
        )
    ).scalar_one()
    deals_count = (
        await session.execute(
            select(func.count(DealModel.id)).where(DealModel.created_at >= start, DealModel.created_at <= end)
        )
    ).scalar_one()
    commission_sum = (
        await session.execute(
            select(func.coalesce(func.sum(DealModel.commission), 0.0)).where(
                DealModel.created_at >= start,
                DealModel.created_at <= end,
            )
        )
    ).scalar_one()

    estimated_cost = float(leads_count) * 7.5
    roi = ((float(commission_sum) - estimated_cost) / estimated_cost) if estimated_cost > 0 else 0.0
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "kpis": {
            "leads": int(leads_count),
            "qualified_leads": int(qualified_count),
            "appointments_or_deals": int(deals_count),
            "attributed_revenue": float(commission_sum),
            "estimated_automation_cost": round(estimated_cost, 2),
            "roi_ratio": round(roi, 4),
        },
    }


async def _compute_roi_trends(session, start: datetime, end: datetime, interval: str) -> dict[str, Any]:
    bucket_days = 7 if interval == "week" else 30
    points: list[dict[str, Any]] = []
    cursor = start
    while cursor < end:
        bucket_end = min(cursor + timedelta(days=bucket_days), end)
        summary = await _compute_roi_summary(session, cursor, bucket_end)
        kpis = summary["kpis"]
        points.append(
            {
                "bucket_start": cursor.isoformat(),
                "bucket_end": bucket_end.isoformat(),
                "leads": kpis["leads"],
                "qualified_leads": kpis["qualified_leads"],
                "revenue": kpis["attributed_revenue"],
                "roi_ratio": kpis["roi_ratio"],
            }
        )
        cursor = bucket_end
    return {
        "interval": interval,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "points": points,
    }


@router.get("/roi/summary")
async def roi_summary(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    user=Depends(get_current_active_user()),
) -> dict[str, Any]:
    _require_role(user, {"viewer"})
    start, end = _date_range_or_default(date_from, date_to)
    async with AsyncSessionFactory() as session:
        return await _compute_roi_summary(session, start, end)


@router.get("/roi/trends")
async def roi_trends(
    interval: str = Query(default="week", pattern="^(week|month)$"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    user=Depends(get_current_active_user()),
) -> dict[str, Any]:
    _require_role(user, {"viewer"})
    start, end = _date_range_or_default(date_from, date_to)
    async with AsyncSessionFactory() as session:
        return await _compute_roi_trends(session, start, end, interval)


@router.post("/reports/generate")
async def generate_report(payload: ReportGenerateRequest, user=Depends(get_current_active_user())) -> dict[str, Any]:
    _require_role(user, {"operator"})
    _ensure_dirs()
    start, end = _date_range_or_default(payload.date_from, payload.date_to)
    async with AsyncSessionFactory() as session:
        summary = await _compute_roi_summary(session, start, end)
        trend = await _compute_roi_trends(session, start, end, "week")
    report_id = str(uuid.uuid4())

    created_files: list[str] = []
    if payload.format in {"json", "both"}:
        json_path = REPORTS_DIR / f"{report_id}.json"
        _save_json(json_path, {"summary": summary, "trend": trend})
        created_files.append(str(json_path))

    if payload.format in {"html", "both"}:
        html_path = REPORTS_DIR / f"{report_id}.html"
        html_path.write_text(
            "\n".join(
                [
                    "<html><head><title>Jorge ROI Report</title></head><body>",
                    f"<h1>Jorge ROI Report</h1><p>Generated: {datetime.now(UTC).isoformat()}</p>",
                    f"<h2>Summary</h2><pre>{json.dumps(summary, indent=2)}</pre>",
                    f"<h2>Weekly Trend</h2><pre>{json.dumps(trend, indent=2)}</pre>",
                    "</body></html>",
                ]
            )
        )
        created_files.append(str(html_path))

    async with AsyncSessionFactory() as session:
        session.add(
            RoiReportModel(
                id=report_id,
                agency_id=await _resolve_agency_id(user),
                date_from=start,
                date_to=end,
                format=payload.format,
                artifact_paths=created_files,
                summary_json={"summary": summary, "trend": trend},
                generated_by=_user_id_from_user(user),
            )
        )
        await session.commit()

    index = _load_json(REPORT_INDEX_FILE, {})
    index[report_id] = {
        "id": report_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "files": created_files,
        "from": summary["from"],
        "to": summary["to"],
    }
    _save_json(REPORT_INDEX_FILE, index)

    return {"report_id": report_id, "files": created_files, "status": "generated"}


@router.get("/reports/{report_id}")
async def get_report(report_id: str, user=Depends(get_current_active_user())) -> dict[str, Any]:
    _require_role(user, {"viewer"})
    metadata: dict[str, Any] | None = None
    async with AsyncSessionFactory() as session:
        model = (
            await session.execute(select(RoiReportModel).where(RoiReportModel.id == report_id))
        ).scalar_one_or_none()
        if model is not None:
            metadata = {
                "id": model.id,
                "generated_at": model.generated_at.isoformat() if model.generated_at else None,
                "files": list(model.artifact_paths or []),
                "from": model.date_from.isoformat() if model.date_from else None,
                "to": model.date_to.isoformat() if model.date_to else None,
                "format": model.format,
            }

    if metadata is None:
        index = _load_json(REPORT_INDEX_FILE, {})
        metadata = index.get(report_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Report not found")

    payload: dict[str, Any] = {"metadata": metadata, "artifacts": []}
    for path_str in metadata.get("files", []):
        path = Path(path_str)
        if path.exists():
            content = path.read_text()
            payload["artifacts"].append(
                {
                    "path": path_str,
                    "content_type": "application/json" if path.suffix == ".json" else "text/html",
                    "content": content,
                }
            )

    return payload
