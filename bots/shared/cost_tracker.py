"""
Cost Tracker for Jorge Real Estate AI Bots.

Tracks per-request LLM costs and aggregates by model, bot type, and time period.
Stores records in Redis with daily keys for efficient time-range queries.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bots.shared.cache_service import get_cache_service
from bots.shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CostRecord:
    """Single LLM API call cost record."""
    request_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    bot_type: str
    timestamp: datetime


class CostTracker:
    """
    Tracks and aggregates LLM API costs.

    Stores individual cost records in Redis using daily sorted sets
    (key: cost:YYYY-MM-DD, score: unix timestamp) for efficient
    time-range queries and automatic expiry.
    """

    # Anthropic pricing (per million tokens) - May 2026
    MODEL_PRICING: Dict[str, Dict[str, float]] = {
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
        "claude-opus-4-8": {"input": 5.0, "output": 25.0},
    }

    # Fallback pricing for unknown models (use Sonnet pricing)
    _DEFAULT_PRICING = {"input": 3.0, "output": 15.0}

    def __init__(self):
        self.cache_service = get_cache_service()

    @classmethod
    def calculate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate USD cost for a given model and token counts."""
        pricing = cls.MODEL_PRICING.get(model, cls._DEFAULT_PRICING)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 8)

    async def record(self, record: CostRecord) -> None:
        """Store a cost record in Redis under the daily key."""
        day_key = f"cost:{record.timestamp.strftime('%Y-%m-%d')}"
        entry = {
            "request_id": record.request_id,
            "model": record.model,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "cost_usd": record.cost_usd,
            "bot_type": record.bot_type,
            "ts": record.timestamp.isoformat(),
        }

        # Store as a list item in a daily cache key (TTL: 7 days)
        existing = await self.cache_service.get(day_key) or []
        existing.append(entry)
        await self.cache_service.set(day_key, existing, ttl=604_800)

        logger.debug(
            f"Cost recorded: {record.model} "
            f"in={record.input_tokens} out={record.output_tokens} "
            f"${record.cost_usd:.6f} [{record.bot_type}]"
        )

    async def get_summary(self, period: str = "24h") -> Dict[str, Any]:
        """
        Get cost summary for a time period.

        Args:
            period: "24h", "7d", or "30d"

        Returns:
            Dict with total_cost, request_count, by_model breakdown,
            by_bot breakdown, and per_request_average.
        """
        days = {"24h": 1, "7d": 7, "30d": 30}.get(period, 1)

        all_records: List[Dict] = []
        now = datetime.now(timezone.utc)

        for day_offset in range(days):
            from datetime import timedelta
            day = now - timedelta(days=day_offset)
            day_key = f"cost:{day.strftime('%Y-%m-%d')}"
            day_records = await self.cache_service.get(day_key)
            if day_records:
                all_records.extend(day_records)

        if not all_records:
            return {
                "period": period,
                "total_cost": 0.0,
                "request_count": 0,
                "by_model": {},
                "by_bot": {},
                "per_request_average": 0.0,
            }

        total_cost = sum(r["cost_usd"] for r in all_records)
        request_count = len(all_records)

        # Aggregate by model
        by_model: Dict[str, Dict[str, Any]] = {}
        for r in all_records:
            model = r["model"]
            if model not in by_model:
                by_model[model] = {"cost": 0.0, "requests": 0, "input_tokens": 0, "output_tokens": 0}
            by_model[model]["cost"] += r["cost_usd"]
            by_model[model]["requests"] += 1
            by_model[model]["input_tokens"] += r["input_tokens"]
            by_model[model]["output_tokens"] += r["output_tokens"]

        # Aggregate by bot type
        by_bot: Dict[str, Dict[str, Any]] = {}
        for r in all_records:
            bot = r["bot_type"]
            if bot not in by_bot:
                by_bot[bot] = {"cost": 0.0, "requests": 0}
            by_bot[bot]["cost"] += r["cost_usd"]
            by_bot[bot]["requests"] += 1

        return {
            "period": period,
            "total_cost": round(total_cost, 6),
            "request_count": request_count,
            "by_model": {k: {**v, "cost": round(v["cost"], 6)} for k, v in by_model.items()},
            "by_bot": {k: {**v, "cost": round(v["cost"], 6)} for k, v in by_bot.items()},
            "per_request_average": round(total_cost / request_count, 6) if request_count else 0.0,
        }


# Global instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker instance."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker
