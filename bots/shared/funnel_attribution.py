"""
Funnel Attribution Tracker for Jorge Real Estate AI Bots.

Multi-touch attribution for lead-to-close journeys across bots.
Tracks contacts through funnel stages and attributes conversions
to bots using first-touch, last-touch, linear, and time-decay models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# Funnel stage constants
STAGE_AWARENESS = "awareness"
STAGE_INTEREST = "interest"
STAGE_CONSIDERATION = "consideration"
STAGE_INTENT = "intent"
STAGE_EVALUATION = "evaluation"
STAGE_PURCHASE = "purchase"

FUNNEL_STAGES = [
    STAGE_AWARENESS,
    STAGE_INTEREST,
    STAGE_CONSIDERATION,
    STAGE_INTENT,
    STAGE_EVALUATION,
    STAGE_PURCHASE,
]


@dataclass
class FunnelEvent:
    """A single event in a contact's funnel journey."""

    contact_id: str
    stage: str
    bot_name: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)


@dataclass
class FunnelReport:
    """Aggregated funnel performance report."""

    total_leads: int
    conversion_rate: float
    avg_journey_length: float
    cost_per_conversion: float | None
    attribution_by_bot: dict[str, float]


class FunnelTracker:
    """
    Tracks contacts through funnel stages and maintains journey histories.

    Records events as contacts progress through the funnel, and provides
    aggregated statistics on conversion rates and stage distribution.

    Optionally persists events to Redis sorted sets for cross-process durability.
    """

    _REDIS_TTL = 2_592_000  # 30 days

    def __init__(self, redis_client: Optional[Any] = None) -> None:
        self.events: list[FunnelEvent] = []
        self.journeys: dict[str, list[FunnelEvent]] = {}
        self._redis = redis_client

    def _redis_key(self, contact_id: str) -> str:
        return f"funnel:events:{contact_id}"

    @staticmethod
    def _serialize_event(event: FunnelEvent) -> str:
        """Serialize a FunnelEvent to JSON for Redis storage."""
        data = {
            "contact_id": event.contact_id,
            "stage": event.stage,
            "bot_name": event.bot_name,
            "timestamp": event.timestamp.isoformat(),
            "metadata": event.metadata,
        }
        return json.dumps(data)

    @staticmethod
    def _deserialize_event(raw: str) -> FunnelEvent:
        """Deserialize a JSON string back to a FunnelEvent."""
        data = json.loads(raw)
        return FunnelEvent(
            contact_id=data["contact_id"],
            stage=data["stage"],
            bot_name=data["bot_name"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )

    async def _persist_to_redis(self, event: FunnelEvent) -> None:
        """Write event to a Redis sorted set keyed by contact_id."""
        key = self._redis_key(event.contact_id)
        score = event.timestamp.timestamp()
        member = self._serialize_event(event)
        await self._redis.zadd(key, {member: score})
        await self._redis.expire(key, self._REDIS_TTL)

    async def _load_from_redis(self, contact_id: str) -> list[FunnelEvent]:
        """Read all events for a contact from Redis sorted set."""
        key = self._redis_key(contact_id)
        members = await self._redis.zrangebyscore(key, "-inf", "+inf")
        return [self._deserialize_event(m) for m in members]

    def record_event(self, event: FunnelEvent) -> None:
        """Store a funnel event and update the contact's journey."""
        self.events.append(event)
        if event.contact_id not in self.journeys:
            self.journeys[event.contact_id] = []
        self.journeys[event.contact_id].append(event)

    async def record_event_async(self, event: FunnelEvent) -> None:
        """Store a funnel event, persisting to Redis if configured."""
        self.record_event(event)
        if self._redis is not None:
            await self._persist_to_redis(event)

    def get_journey(self, contact_id: str) -> list[FunnelEvent]:
        """Return ordered events for a contact (in-memory only)."""
        events = self.journeys.get(contact_id, [])
        return sorted(events, key=lambda e: e.timestamp)

    async def get_journey_async(self, contact_id: str) -> list[FunnelEvent]:
        """Return ordered events, reading from Redis if available."""
        if self._redis is not None:
            try:
                events = await self._load_from_redis(contact_id)
                if events:
                    return sorted(events, key=lambda e: e.timestamp)
            except Exception:
                pass
        # Fall back to in-memory
        return self.get_journey(contact_id)

    def get_funnel_stats(self) -> dict:
        """
        Calculate conversion rates between stages and drop-off points.

        Returns a dict with:
        - stage_counts: contacts at each stage
        - conversion_rates: rate from each stage to the next
        - drop_off_points: stages where contacts are lost
        """
        stage_counts = self.get_stage_counts()
        conversion_rates: dict[str, float] = {}
        drop_off_points: dict[str, float] = {}

        for i in range(len(FUNNEL_STAGES) - 1):
            current = FUNNEL_STAGES[i]
            next_stage = FUNNEL_STAGES[i + 1]
            current_count = stage_counts.get(current, 0)
            next_count = stage_counts.get(next_stage, 0)

            if current_count > 0:
                rate = next_count / current_count
                conversion_rates[f"{current}_to_{next_stage}"] = round(rate, 4)
                drop_off_points[current] = round(1.0 - rate, 4)
            else:
                conversion_rates[f"{current}_to_{next_stage}"] = 0.0
                drop_off_points[current] = 0.0

        return {
            "stage_counts": stage_counts,
            "conversion_rates": conversion_rates,
            "drop_off_points": drop_off_points,
        }

    def get_stage_counts(self) -> dict[str, int]:
        """
        Count contacts that have reached each stage.

        A contact is counted at a stage if they have at least one event
        at that stage in their journey.
        """
        counts: dict[str, int] = {stage: 0 for stage in FUNNEL_STAGES}
        for contact_id, events in self.journeys.items():
            reached_stages = {e.stage for e in events}
            for stage in reached_stages:
                if stage in counts:
                    counts[stage] += 1
        return counts


class AttributionModel:
    """
    Multi-touch attribution models for assigning conversion credit to bots.

    Each model returns a dict mapping bot_name -> credit (float, sums to 1.0).
    """

    @staticmethod
    def first_touch(journey: list[FunnelEvent]) -> dict[str, float]:
        """100% credit to the first bot in the journey."""
        if not journey:
            return {}
        sorted_journey = sorted(journey, key=lambda e: e.timestamp)
        return {sorted_journey[0].bot_name: 1.0}

    @staticmethod
    def last_touch(journey: list[FunnelEvent]) -> dict[str, float]:
        """100% credit to the last bot in the journey."""
        if not journey:
            return {}
        sorted_journey = sorted(journey, key=lambda e: e.timestamp)
        return {sorted_journey[-1].bot_name: 1.0}

    @staticmethod
    def linear(journey: list[FunnelEvent]) -> dict[str, float]:
        """Equal credit split across all touchpoints."""
        if not journey:
            return {}
        credit_per_touch = 1.0 / len(journey)
        result: dict[str, float] = {}
        for event in journey:
            result[event.bot_name] = result.get(event.bot_name, 0.0) + credit_per_touch
        return result

    @staticmethod
    def time_decay(journey: list[FunnelEvent], decay_factor: float = 0.7) -> dict[str, float]:
        """
        More recent touchpoints get more credit.

        The most recent event gets weight 1.0, the one before gets
        decay_factor, then decay_factor^2, etc. Weights are then
        normalized so they sum to 1.0.
        """
        if not journey:
            return {}
        sorted_journey = sorted(journey, key=lambda e: e.timestamp)
        n = len(sorted_journey)

        # Most recent = highest weight
        weights = [decay_factor ** (n - 1 - i) for i in range(n)]
        total_weight = sum(weights)

        if total_weight == 0:
            return {}

        result: dict[str, float] = {}
        for event, weight in zip(sorted_journey, weights):
            normalized = weight / total_weight
            result[event.bot_name] = result.get(event.bot_name, 0.0) + normalized
        return result


def generate_funnel_report(tracker: FunnelTracker, model: str = "linear") -> FunnelReport:
    """
    Generate a comprehensive funnel performance report.

    Args:
        tracker: FunnelTracker with recorded events.
        model: Attribution model name (first_touch, last_touch, linear, time_decay).

    Returns:
        FunnelReport with aggregated metrics.
    """
    total_leads = len(tracker.journeys)

    # Count conversions (contacts that reached purchase stage)
    conversions = 0
    for contact_id, events in tracker.journeys.items():
        if any(e.stage == STAGE_PURCHASE for e in events):
            conversions += 1

    conversion_rate = conversions / total_leads if total_leads > 0 else 0.0

    # Average journey length
    journey_lengths = [len(events) for events in tracker.journeys.values()]
    avg_journey_length = sum(journey_lengths) / len(journey_lengths) if journey_lengths else 0.0

    # Attribution
    model_map = {
        "first_touch": AttributionModel.first_touch,
        "last_touch": AttributionModel.last_touch,
        "linear": AttributionModel.linear,
        "time_decay": AttributionModel.time_decay,
    }
    attr_func = model_map.get(model, AttributionModel.linear)

    # Aggregate attribution across all converted journeys
    attribution_by_bot: dict[str, float] = {}
    converted_journeys = 0
    for contact_id, events in tracker.journeys.items():
        if any(e.stage == STAGE_PURCHASE for e in events):
            sorted_events = sorted(events, key=lambda e: e.timestamp)
            credits = attr_func(sorted_events)
            for bot, credit in credits.items():
                attribution_by_bot[bot] = attribution_by_bot.get(bot, 0.0) + credit
            converted_journeys += 1

    # Normalize attribution to percentages
    if converted_journeys > 0:
        for bot in attribution_by_bot:
            attribution_by_bot[bot] = round(attribution_by_bot[bot] / converted_journeys, 4)

    return FunnelReport(
        total_leads=total_leads,
        conversion_rate=round(conversion_rate, 4),
        avg_journey_length=round(avg_journey_length, 2),
        cost_per_conversion=None,
        attribution_by_bot=attribution_by_bot,
    )
