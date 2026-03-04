from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bots.lead_bot.main import app
from bots.lead_bot import routes_productization
from bots.shared.auth_middleware import auth_middleware
from database.base import Base
from database.billing_models import AgencyModel, OnboardingStateModel
from database.models import PlaybookApplicationModel, RoiReportModel


def _override_viewer():
    return {"id": "user-v", "agency_id": "agency-1", "role": "viewer"}


@pytest_asyncio.fixture
async def productization_client(monkeypatch, tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    for table in (PlaybookApplicationModel.__table__, RoiReportModel.__table__):
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[
                    AgencyModel.__table__,
                    OnboardingStateModel.__table__,
                    PlaybookApplicationModel.__table__,
                    RoiReportModel.__table__,
                ],
            )
        )

    monkeypatch.setattr(routes_productization, "AsyncSessionFactory", lambda: session_factory())

    artifacts_dir = tmp_path / "storage" / "productization"
    reports_dir = artifacts_dir / "reports"
    monkeypatch.setattr(routes_productization, "ARTIFACTS_DIR", artifacts_dir)
    monkeypatch.setattr(routes_productization, "PLAYBOOK_FILE", artifacts_dir / "playbook_applications.json")
    monkeypatch.setattr(routes_productization, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(routes_productization, "REPORT_INDEX_FILE", artifacts_dir / "report_index.json")

    def _override_admin():
        return {"id": "user-1", "agency_id": "agency-1", "role": "admin"}

    app.dependency_overrides[auth_middleware.get_current_active_user] = _override_admin

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_agency(session_factory):
    async with session_factory() as session:
        session.add(
            AgencyModel(
                id="agency-1",
                name="Agency One",
                slug="agency-one",
                email="owner@agency.one",
                onboarding_completed=True,
                onboarding_step="completed",
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_playbook_apply_persists_db_metadata_and_idempotency(productization_client):
    client, session_factory = productization_client
    await _seed_agency(session_factory)

    first = await client.post(
        "/api/playbooks/apply",
        json={"agency_id": "agency-1", "playbook_id": "solo-agent"},
    )
    assert first.status_code == 200
    assert first.json()["idempotent"] is False

    second = await client.post(
        "/api/playbooks/apply",
        json={"agency_id": "agency-1", "playbook_id": "solo-agent"},
    )
    assert second.status_code == 200
    assert second.json()["idempotent"] is True

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(PlaybookApplicationModel).where(PlaybookApplicationModel.agency_id == "agency-1")
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].playbook_id == "solo-agent"
        assert rows[0].metadata_json.get("source") == "playbooks_apply"


@pytest.mark.asyncio
async def test_playbook_apply_overwrite_updates_existing_application(productization_client):
    client, session_factory = productization_client
    await _seed_agency(session_factory)

    first = await client.post(
        "/api/playbooks/apply",
        json={"agency_id": "agency-1", "playbook_id": "solo-agent"},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/playbooks/apply",
        json={
            "agency_id": "agency-1",
            "playbook_id": "small-team",
            "overwrite": True,
            "version": "1.0.0",
        },
    )
    assert second.status_code == 200
    assert second.json()["idempotent"] is False

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(PlaybookApplicationModel).where(PlaybookApplicationModel.agency_id == "agency-1")
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].playbook_id == "small-team"
        assert rows[0].version == "1.0.0"


@pytest.mark.asyncio
async def test_reports_generate_and_get_db_first_when_index_missing(productization_client):
    client, session_factory = productization_client
    await _seed_agency(session_factory)
    summary_payload = {
        "from": "2026-03-01T00:00:00+00:00",
        "to": "2026-03-03T00:00:00+00:00",
        "kpis": {"leads": 1, "qualified_leads": 1, "appointments_or_deals": 1, "attributed_revenue": 5000.0, "estimated_automation_cost": 7.5, "roi_ratio": 665.6667},
    }
    trend_payload = {
        "interval": "week",
        "from": "2026-03-01T00:00:00+00:00",
        "to": "2026-03-03T00:00:00+00:00",
        "points": [],
    }

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(routes_productization, "_compute_roi_summary", AsyncMock(return_value=summary_payload))
        mp.setattr(routes_productization, "_compute_roi_trends", AsyncMock(return_value=trend_payload))
        report = await client.post("/api/reports/generate", json={"format": "json"})
    assert report.status_code == 200
    report_id = report.json()["report_id"]

    # Force retrieval to use DB metadata source by removing legacy index file.
    if routes_productization.REPORT_INDEX_FILE.exists():
        routes_productization.REPORT_INDEX_FILE.unlink()

    get_resp = await client.get(f"/api/reports/{report_id}")
    assert get_resp.status_code == 200
    payload = get_resp.json()
    assert payload["metadata"]["id"] == report_id
    assert payload["artifacts"]

    async with session_factory() as session:
        model = (
            await session.execute(select(RoiReportModel).where(RoiReportModel.id == report_id))
        ).scalar_one_or_none()
        assert model is not None
        assert list(model.artifact_paths)


def test_productization_migration_matches_models():
    migration_path = Path(
        "/Users/cave/Projects/jorge-real-estate-bots/alembic/versions/20260303_000002_productization_metadata.py"
    )
    text = migration_path.read_text()

    assert "revision = \"20260303_000002\"" in text
    assert "down_revision = \"20260206_000001\"" in text
    assert "create_table(\n        \"playbook_applications\"" in text
    assert "create_table(\n        \"roi_reports\"" in text

    playbook_columns = set(PlaybookApplicationModel.__table__.columns.keys())
    report_columns = set(RoiReportModel.__table__.columns.keys())

    assert {
        "id",
        "agency_id",
        "playbook_id",
        "version",
        "applied_by",
        "is_active",
        "metadata_json",
        "applied_at",
        "created_at",
        "updated_at",
    }.issubset(playbook_columns)

    assert {
        "id",
        "agency_id",
        "date_from",
        "date_to",
        "format",
        "artifact_paths",
        "summary_json",
        "generated_by",
        "generated_at",
    }.issubset(report_columns)


@pytest.mark.asyncio
async def test_viewer_can_read_playbooks_but_cannot_generate_reports(productization_client):
    client, _ = productization_client
    app.dependency_overrides[auth_middleware.get_current_active_user] = _override_viewer
    try:
        read_resp = await client.get("/api/playbooks")
        assert read_resp.status_code == 200

        write_resp = await client.post("/api/reports/generate", json={"format": "json"})
        assert write_resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
