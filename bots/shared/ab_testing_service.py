"""
Jorge A/B Testing Service

Enables A/B testing of bot response variations to optimize conversion rates.
Contacts are deterministically assigned to variants via hash-based bucketing,
ensuring consistent experiences across sessions. Statistical significance is
evaluated with a two-proportion z-test.

Usage:
    service = ABTestingService()
    service.create_experiment("greeting_style", ["formal", "casual", "empathetic"])
    variant = await service.get_variant("greeting_style", contact_id)
    await service.record_outcome("greeting_style", contact_id, variant, "conversion")
    results = service.get_experiment_results("greeting_style")
"""

import hashlib
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExperimentStatus(str, Enum):
    """Lifecycle states for an experiment."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


VALID_OUTCOMES = frozenset({
    "response",
    "engagement",
    "conversion",
    "handoff_success",
    "appointment_booked",
})


@dataclass
class VariantStats:
    """Aggregated statistics for a single variant."""

    variant: str
    impressions: int = 0
    conversions: int = 0
    total_value: float = 0.0
    conversion_rate: float = 0.0
    confidence_interval: tuple = (0.0, 0.0)


@dataclass
class ExperimentResult:
    """Full result payload for an experiment."""

    experiment_id: str
    status: str
    variants: List[VariantStats] = field(default_factory=list)
    is_significant: bool = False
    p_value: Optional[float] = None
    winner: Optional[str] = None
    total_impressions: int = 0
    total_conversions: int = 0
    created_at: float = 0.0
    duration_hours: float = 0.0


@dataclass
class _Experiment:
    """Internal experiment state."""

    experiment_id: str
    variants: List[str]
    traffic_split: Dict[str, float]
    status: ExperimentStatus
    created_at: float
    # variant -> list of contact_ids assigned
    assignments: Dict[str, List[str]] = field(default_factory=dict)
    # variant -> list of outcome dicts
    outcomes: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)


class ABTestingService:
    """A/B testing engine for Jorge bot response variations.

    Thread-safe, in-memory experiment management with deterministic
    variant assignment and two-proportion z-test significance analysis.
    """

    # ── Pre-built experiment identifiers ──────────────────────────────
    RESPONSE_TONE_EXPERIMENT = "response_tone"        # formal vs casual vs empathetic
    FOLLOWUP_TIMING_EXPERIMENT = "followup_timing"    # 1hr vs 4hr vs 24hr
    CTA_STYLE_EXPERIMENT = "cta_style"                # direct vs soft vs question
    GREETING_EXPERIMENT = "greeting_style"            # name vs title vs casual

    # ── Singleton ─────────────────────────────────────────────────────
    _instance: Optional["ABTestingService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ABTestingService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._experiments: Dict[str, _Experiment] = {}
        self._data_lock = threading.Lock()
        self._initialized = True
        logger.info("ABTestingService initialized")

    # ── Experiment Management ─────────────────────────────────────────

    def create_experiment(
        self,
        experiment_id: str,
        variants: List[str],
        traffic_split: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Create a new A/B experiment.

        Args:
            experiment_id: Unique identifier for the experiment.
            variants: List of variant names (minimum 2).
            traffic_split: Optional mapping of variant -> fraction (must sum to 1.0).
                           Defaults to equal split across all variants.

        Returns:
            Dict with experiment metadata.

        Raises:
            ValueError: On invalid inputs (duplicate id, <2 variants, bad split).
        """
        if len(variants) < 2:
            raise ValueError("Experiments require at least 2 variants")

        if len(set(variants)) != len(variants):
            raise ValueError("Variant names must be unique")

        # Build or validate traffic split
        if traffic_split is None:
            equal_share = 1.0 / len(variants)
            traffic_split = {v: equal_share for v in variants}
        else:
            if set(traffic_split.keys()) != set(variants):
                raise ValueError(
                    "traffic_split keys must match variant names exactly"
                )
            total = sum(traffic_split.values())
            if not math.isclose(total, 1.0, abs_tol=1e-6):
                raise ValueError(
                    f"traffic_split must sum to 1.0, got {total:.6f}"
                )

        with self._data_lock:
            if experiment_id in self._experiments:
                raise ValueError(
                    f"Experiment '{experiment_id}' already exists"
                )

            experiment = _Experiment(
                experiment_id=experiment_id,
                variants=list(variants),
                traffic_split=dict(traffic_split),
                status=ExperimentStatus.ACTIVE,
                created_at=time.time(),
                assignments={v: [] for v in variants},
                outcomes={v: [] for v in variants},
            )
            self._experiments[experiment_id] = experiment

        logger.info(
            f"Created experiment '{experiment_id}' with variants "
            f"{variants} and split {traffic_split}"
        )
        return {
            "experiment_id": experiment_id,
            "variants": variants,
            "traffic_split": traffic_split,
            "status": ExperimentStatus.ACTIVE.value,
        }

    def deactivate_experiment(self, experiment_id: str) -> Dict[str, Any]:
        """Stop an active experiment.

        Args:
            experiment_id: Experiment to deactivate.

        Returns:
            Dict with final status and duration.

        Raises:
            KeyError: If experiment does not exist.
        """
        with self._data_lock:
            experiment = self._get_experiment(experiment_id)
            experiment.status = ExperimentStatus.COMPLETED
            duration_hours = (time.time() - experiment.created_at) / 3600

        logger.info(
            f"Deactivated experiment '{experiment_id}' "
            f"after {duration_hours:.1f} hours"
        )
        return {
            "experiment_id": experiment_id,
            "status": ExperimentStatus.COMPLETED.value,
            "duration_hours": round(duration_hours, 2),
        }

    def list_experiments(self) -> List[Dict[str, Any]]:
        """List all active experiments.

        Returns:
            List of dicts with experiment metadata.
        """
        with self._data_lock:
            results = []
            for exp in self._experiments.values():
                if exp.status == ExperimentStatus.ACTIVE:
                    total_assigned = sum(
                        len(contacts) for contacts in exp.assignments.values()
                    )
                    results.append({
                        "experiment_id": exp.experiment_id,
                        "variants": exp.variants,
                        "traffic_split": exp.traffic_split,
                        "status": exp.status.value,
                        "total_assignments": total_assigned,
                        "created_at": exp.created_at,
                    })
            return results

    # ── Variant Assignment ────────────────────────────────────────────

    async def get_variant(
        self, experiment_id: str, contact_id: str
    ) -> str:
        """Deterministically assign a contact to a variant.

        Uses a SHA-256 hash of ``contact_id + experiment_id`` mapped onto
        the cumulative traffic split to produce a stable bucket.

        Args:
            experiment_id: Target experiment.
            contact_id: GHL contact identifier.

        Returns:
            The assigned variant name.

        Raises:
            KeyError: If experiment does not exist.
            ValueError: If experiment is not active.
        """
        with self._data_lock:
            experiment = self._get_experiment(experiment_id)
            if experiment.status != ExperimentStatus.ACTIVE:
                raise ValueError(
                    f"Experiment '{experiment_id}' is not active "
                    f"(status={experiment.status.value})"
                )

            variant = self._hash_assign(
                contact_id, experiment_id, experiment.variants,
                experiment.traffic_split,
            )

            # Track assignment (deduplicate)
            if contact_id not in experiment.assignments[variant]:
                experiment.assignments[variant].append(contact_id)

        return variant

    # ── Outcome Tracking ──────────────────────────────────────────────

    async def record_outcome(
        self,
        experiment_id: str,
        contact_id: str,
        variant: str,
        outcome: str,
        value: float = 1.0,
    ) -> Dict[str, Any]:
        """Record a conversion/outcome event for a variant.

        Args:
            experiment_id: Target experiment.
            contact_id: GHL contact identifier.
            variant: Variant the contact was assigned to.
            outcome: One of the VALID_OUTCOMES.
            value: Numeric value for the outcome (default 1.0).

        Returns:
            Dict confirming the recorded outcome.

        Raises:
            KeyError: If experiment does not exist.
            ValueError: On invalid variant or outcome.
        """
        if outcome not in VALID_OUTCOMES:
            raise ValueError(
                f"Invalid outcome '{outcome}'. "
                f"Must be one of: {sorted(VALID_OUTCOMES)}"
            )

        with self._data_lock:
            experiment = self._get_experiment(experiment_id)
            if variant not in experiment.variants:
                raise ValueError(
                    f"Unknown variant '{variant}' for experiment "
                    f"'{experiment_id}'"
                )

            experiment.outcomes[variant].append({
                "contact_id": contact_id,
                "outcome": outcome,
                "value": value,
                "timestamp": time.time(),
            })

        logger.debug(
            f"Recorded outcome '{outcome}' (value={value}) for "
            f"variant '{variant}' in experiment '{experiment_id}'"
        )
        return {
            "experiment_id": experiment_id,
            "contact_id": contact_id,
            "variant": variant,
            "outcome": outcome,
            "value": value,
        }

    # ── Statistical Analysis ──────────────────────────────────────────

    def get_experiment_results(self, experiment_id: str) -> ExperimentResult:
        """Compute per-variant statistics and overall significance.

        For each variant, returns impressions (unique contacts assigned),
        conversions (outcome events), conversion rate, and a 95%
        Wilson score confidence interval.

        Statistical significance is assessed via a two-proportion z-test
        between the best and second-best variants.

        Args:
            experiment_id: Target experiment.

        Returns:
            ExperimentResult with full analysis.

        Raises:
            KeyError: If experiment does not exist.
        """
        with self._data_lock:
            experiment = self._get_experiment(experiment_id)

            variant_stats: List[VariantStats] = []
            for v in experiment.variants:
                impressions = len(experiment.assignments[v])
                outcomes = experiment.outcomes[v]
                conversions = len(outcomes)
                total_value = sum(o["value"] for o in outcomes)

                rate = conversions / impressions if impressions > 0 else 0.0
                ci = self._wilson_confidence_interval(conversions, impressions)

                variant_stats.append(VariantStats(
                    variant=v,
                    impressions=impressions,
                    conversions=conversions,
                    total_value=total_value,
                    conversion_rate=round(rate, 4),
                    confidence_interval=(round(ci[0], 4), round(ci[1], 4)),
                ))

            total_impressions = sum(vs.impressions for vs in variant_stats)
            total_conversions = sum(vs.conversions for vs in variant_stats)

            # Significance between top two variants by conversion rate
            sorted_stats = sorted(
                variant_stats, key=lambda s: s.conversion_rate, reverse=True
            )
            p_value = None
            is_sig = False
            winner = None

            if (
                len(sorted_stats) >= 2
                and sorted_stats[0].impressions > 0
                and sorted_stats[1].impressions > 0
            ):
                p_value = self._two_proportion_z_test(
                    sorted_stats[0].conversions,
                    sorted_stats[0].impressions,
                    sorted_stats[1].conversions,
                    sorted_stats[1].impressions,
                )
                is_sig = p_value < 0.05
                if is_sig:
                    winner = sorted_stats[0].variant

            duration_hours = (time.time() - experiment.created_at) / 3600

        return ExperimentResult(
            experiment_id=experiment_id,
            status=experiment.status.value,
            variants=variant_stats,
            is_significant=is_sig,
            p_value=round(p_value, 6) if p_value is not None else None,
            winner=winner,
            total_impressions=total_impressions,
            total_conversions=total_conversions,
            created_at=experiment.created_at,
            duration_hours=round(duration_hours, 2),
        )

    def is_significant(
        self, experiment_id: str, threshold: float = 0.95
    ) -> bool:
        """Check whether an experiment has reached statistical significance.

        Args:
            experiment_id: Target experiment.
            threshold: Confidence level (default 0.95, i.e. p < 0.05).

        Returns:
            True if the top two variants differ significantly.

        Raises:
            KeyError: If experiment does not exist.
        """
        alpha = 1.0 - threshold
        with self._data_lock:
            experiment = self._get_experiment(experiment_id)

            rates: List[tuple] = []
            for v in experiment.variants:
                n = len(experiment.assignments[v])
                k = len(experiment.outcomes[v])
                if n > 0:
                    rates.append((v, k, n))

            if len(rates) < 2:
                return False

            rates.sort(key=lambda t: t[1] / t[2], reverse=True)
            p_value = self._two_proportion_z_test(
                rates[0][1], rates[0][2],
                rates[1][1], rates[1][2],
            )

        return p_value < alpha

    # ── Internal Helpers ──────────────────────────────────────────────

    def _get_experiment(self, experiment_id: str) -> _Experiment:
        """Retrieve an experiment or raise KeyError. Caller must hold lock."""
        try:
            return self._experiments[experiment_id]
        except KeyError:
            raise KeyError(f"Experiment '{experiment_id}' not found")

    @staticmethod
    def _hash_assign(
        contact_id: str,
        experiment_id: str,
        variants: List[str],
        traffic_split: Dict[str, float],
    ) -> str:
        """Map a contact deterministically to a variant via hash bucketing."""
        digest = hashlib.sha256(
            f"{contact_id}:{experiment_id}".encode()
        ).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF  # normalise to [0, 1]

        cumulative = 0.0
        for variant in variants:
            cumulative += traffic_split[variant]
            if bucket <= cumulative:
                return variant

        # Floating-point guard: return last variant
        return variants[-1]

    @staticmethod
    def _wilson_confidence_interval(
        successes: int, trials: int, z: float = 1.96
    ) -> tuple:
        """Wilson score interval for a binomial proportion.

        Returns (lower, upper) bounds.  When trials == 0 returns (0, 0).
        """
        if trials == 0:
            return (0.0, 0.0)

        p_hat = successes / trials
        z2 = z * z
        denominator = 1 + z2 / trials
        centre = p_hat + z2 / (2 * trials)
        spread = z * math.sqrt(
            (p_hat * (1 - p_hat) + z2 / (4 * trials)) / trials
        )

        lower = max(0.0, (centre - spread) / denominator)
        upper = min(1.0, (centre + spread) / denominator)
        return (lower, upper)

    @staticmethod
    def _two_proportion_z_test(
        k1: int, n1: int, k2: int, n2: int
    ) -> float:
        """Two-proportion z-test returning a two-sided p-value.

        Uses the normal approximation to the binomial.

        Args:
            k1: Successes in group 1.
            n1: Trials in group 1.
            k2: Successes in group 2.
            n2: Trials in group 2.

        Returns:
            Two-sided p-value (0.0 to 1.0).
        """
        if n1 == 0 or n2 == 0:
            return 1.0

        p1 = k1 / n1
        p2 = k2 / n2
        p_pool = (k1 + k2) / (n1 + n2)

        if p_pool == 0.0 or p_pool == 1.0:
            return 1.0

        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
        if se == 0:
            return 1.0

        z = abs(p1 - p2) / se

        # Two-sided p-value via the complementary error function
        p_value = math.erfc(z / math.sqrt(2))
        return p_value

    # ── Testing Support ───────────────────────────────────────────────

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state. For testing only."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._experiments.clear()
                cls._instance._initialized = False
            cls._instance = None
