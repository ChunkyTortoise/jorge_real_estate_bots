"""
Unit tests for Funnel Attribution Tracker.

Tests multi-touch attribution models, funnel event recording,
journey tracking, stage counting, and report generation.
"""
from datetime import datetime, timedelta

import pytest

from bots.shared.funnel_attribution import (
    FUNNEL_STAGES,
    STAGE_AWARENESS,
    STAGE_CONSIDERATION,
    STAGE_INTEREST,
    STAGE_PURCHASE,
    AttributionModel,
    FunnelEvent,
    FunnelReport,
    FunnelTracker,
    generate_funnel_report,
)


# -- Helpers -----------------------------------------------------------

def _ts(offset_hours: int = 0) -> datetime:
    """Return a deterministic timestamp with an optional hour offset."""
    base = datetime(2026, 1, 15, 10, 0, 0)
    return base + timedelta(hours=offset_hours)


def _event(
    contact_id: str = "c1",
    stage: str = STAGE_AWARENESS,
    bot_name: str = "lead_bot",
    offset_hours: int = 0,
    metadata: dict | None = None,
) -> FunnelEvent:
    return FunnelEvent(
        contact_id=contact_id,
        stage=stage,
        bot_name=bot_name,
        timestamp=_ts(offset_hours),
        metadata=metadata or {},
    )


# -- FunnelEvent Dataclass --------------------------------------------

class TestFunnelEvent:
    """Test FunnelEvent creation and fields."""

    def test_create_basic_event(self):
        ev = _event()
        assert ev.contact_id == "c1"
        assert ev.stage == STAGE_AWARENESS
        assert ev.bot_name == "lead_bot"
        assert isinstance(ev.timestamp, datetime)

    def test_default_metadata_is_empty_dict(self):
        ev = _event()
        assert ev.metadata == {}

    def test_metadata_stored(self):
        ev = _event(metadata={"source": "facebook"})
        assert ev.metadata["source"] == "facebook"

    def test_event_different_bots(self):
        ev1 = _event(bot_name="lead_bot")
        ev2 = _event(bot_name="buyer_bot")
        assert ev1.bot_name != ev2.bot_name


# -- FunnelReport Dataclass -------------------------------------------

class TestFunnelReport:
    """Test FunnelReport creation."""

    def test_create_report(self):
        report = FunnelReport(
            total_leads=100,
            conversion_rate=0.15,
            avg_journey_length=4.2,
            cost_per_conversion=None,
            attribution_by_bot={"lead_bot": 0.6, "buyer_bot": 0.4},
        )
        assert report.total_leads == 100
        assert report.conversion_rate == 0.15
        assert report.attribution_by_bot["lead_bot"] == 0.6

    def test_report_with_cost(self):
        report = FunnelReport(
            total_leads=50,
            conversion_rate=0.20,
            avg_journey_length=3.0,
            cost_per_conversion=25.0,
            attribution_by_bot={},
        )
        assert report.cost_per_conversion == 25.0


# -- FunnelTracker -----------------------------------------------------

class TestFunnelTracker:
    """Test FunnelTracker event recording and journey queries."""

    @pytest.fixture
    def tracker(self):
        return FunnelTracker()

    def test_record_single_event(self, tracker):
        ev = _event()
        tracker.record_event(ev)
        assert len(tracker.events) == 1
        assert "c1" in tracker.journeys

    def test_record_multiple_events_same_contact(self, tracker):
        tracker.record_event(_event(stage=STAGE_AWARENESS, offset_hours=0))
        tracker.record_event(_event(stage=STAGE_INTEREST, offset_hours=1))
        tracker.record_event(_event(stage=STAGE_CONSIDERATION, offset_hours=2))
        assert len(tracker.journeys["c1"]) == 3

    def test_record_events_multiple_contacts(self, tracker):
        tracker.record_event(_event(contact_id="c1"))
        tracker.record_event(_event(contact_id="c2"))
        assert len(tracker.journeys) == 2

    def test_get_journey_returns_sorted(self, tracker):
        tracker.record_event(_event(stage=STAGE_INTEREST, offset_hours=2))
        tracker.record_event(_event(stage=STAGE_AWARENESS, offset_hours=0))
        tracker.record_event(_event(stage=STAGE_CONSIDERATION, offset_hours=1))

        journey = tracker.get_journey("c1")
        assert journey[0].stage == STAGE_AWARENESS
        assert journey[1].stage == STAGE_CONSIDERATION
        assert journey[2].stage == STAGE_INTEREST

    def test_get_journey_unknown_contact(self, tracker):
        journey = tracker.get_journey("unknown")
        assert journey == []

    def test_get_stage_counts(self, tracker):
        tracker.record_event(_event(contact_id="c1", stage=STAGE_AWARENESS))
        tracker.record_event(_event(contact_id="c1", stage=STAGE_INTEREST))
        tracker.record_event(_event(contact_id="c2", stage=STAGE_AWARENESS))

        counts = tracker.get_stage_counts()
        assert counts[STAGE_AWARENESS] == 2
        assert counts[STAGE_INTEREST] == 1
        assert counts[STAGE_CONSIDERATION] == 0

    def test_get_stage_counts_empty(self, tracker):
        counts = tracker.get_stage_counts()
        for stage in FUNNEL_STAGES:
            assert counts[stage] == 0


# -- FunnelTracker.get_funnel_stats ------------------------------------

class TestFunnelStats:
    """Test funnel statistics computation."""

    @pytest.fixture
    def tracker(self):
        return FunnelTracker()

    def test_empty_stats(self, tracker):
        stats = tracker.get_funnel_stats()
        assert "stage_counts" in stats
        assert "conversion_rates" in stats
        assert "drop_off_points" in stats

    def test_stats_with_full_funnel(self, tracker):
        for i, stage in enumerate(FUNNEL_STAGES):
            tracker.record_event(_event(contact_id="c1", stage=stage, offset_hours=i))

        stats = tracker.get_funnel_stats()
        assert stats["stage_counts"][STAGE_PURCHASE] == 1
        assert stats["stage_counts"][STAGE_AWARENESS] == 1

    def test_conversion_rates(self, tracker):
        # 2 contacts at awareness, 1 progresses to interest
        tracker.record_event(_event(contact_id="c1", stage=STAGE_AWARENESS))
        tracker.record_event(_event(contact_id="c2", stage=STAGE_AWARENESS))
        tracker.record_event(_event(contact_id="c1", stage=STAGE_INTEREST, offset_hours=1))

        stats = tracker.get_funnel_stats()
        rate_key = f"{STAGE_AWARENESS}_to_{STAGE_INTEREST}"
        assert stats["conversion_rates"][rate_key] == 0.5

    def test_drop_off_points(self, tracker):
        tracker.record_event(_event(contact_id="c1", stage=STAGE_AWARENESS))
        tracker.record_event(_event(contact_id="c2", stage=STAGE_AWARENESS))
        tracker.record_event(_event(contact_id="c1", stage=STAGE_INTEREST, offset_hours=1))

        stats = tracker.get_funnel_stats()
        assert stats["drop_off_points"][STAGE_AWARENESS] == 0.5


# -- AttributionModel -------------------------------------------------

class TestAttributionModel:
    """Test attribution model credit allocation."""

    @pytest.fixture
    def journey(self):
        return [
            _event(bot_name="lead_bot", stage=STAGE_AWARENESS, offset_hours=0),
            _event(bot_name="buyer_bot", stage=STAGE_INTEREST, offset_hours=1),
            _event(bot_name="seller_bot", stage=STAGE_CONSIDERATION, offset_hours=2),
        ]

    def test_first_touch(self, journey):
        credits = AttributionModel.first_touch(journey)
        assert credits == {"lead_bot": 1.0}

    def test_first_touch_empty(self):
        credits = AttributionModel.first_touch([])
        assert credits == {}

    def test_last_touch(self, journey):
        credits = AttributionModel.last_touch(journey)
        assert credits == {"seller_bot": 1.0}

    def test_last_touch_empty(self):
        credits = AttributionModel.last_touch([])
        assert credits == {}

    def test_linear(self, journey):
        credits = AttributionModel.linear(journey)
        expected_share = pytest.approx(1.0 / 3, rel=1e-3)
        assert credits["lead_bot"] == expected_share
        assert credits["buyer_bot"] == expected_share
        assert credits["seller_bot"] == expected_share

    def test_linear_empty(self):
        credits = AttributionModel.linear([])
        assert credits == {}

    def test_linear_same_bot(self):
        journey = [
            _event(bot_name="lead_bot", offset_hours=0),
            _event(bot_name="lead_bot", offset_hours=1),
        ]
        credits = AttributionModel.linear(journey)
        assert credits["lead_bot"] == pytest.approx(1.0, rel=1e-3)

    def test_time_decay(self, journey):
        credits = AttributionModel.time_decay(journey, decay_factor=0.7)
        # Last touch (seller_bot) should get the most credit
        assert credits["seller_bot"] > credits["buyer_bot"]
        assert credits["buyer_bot"] > credits["lead_bot"]

    def test_time_decay_sums_to_one(self, journey):
        credits = AttributionModel.time_decay(journey, decay_factor=0.5)
        total = sum(credits.values())
        assert total == pytest.approx(1.0, rel=1e-3)

    def test_time_decay_empty(self):
        credits = AttributionModel.time_decay([])
        assert credits == {}

    def test_time_decay_single_touch(self):
        journey = [_event(bot_name="lead_bot")]
        credits = AttributionModel.time_decay(journey)
        assert credits == {"lead_bot": pytest.approx(1.0, rel=1e-3)}


# -- generate_funnel_report -------------------------------------------

class TestGenerateFunnelReport:
    """Test the top-level report generation function."""

    @pytest.fixture
    def tracker_with_data(self):
        tracker = FunnelTracker()
        # Contact 1: full funnel (converted)
        for i, stage in enumerate(FUNNEL_STAGES):
            tracker.record_event(_event(
                contact_id="c1", stage=stage,
                bot_name="lead_bot" if i < 3 else "buyer_bot",
                offset_hours=i,
            ))
        # Contact 2: partial funnel (dropped off)
        tracker.record_event(_event(contact_id="c2", stage=STAGE_AWARENESS, offset_hours=0))
        tracker.record_event(_event(contact_id="c2", stage=STAGE_INTEREST, offset_hours=1))
        return tracker

    def test_report_total_leads(self, tracker_with_data):
        report = generate_funnel_report(tracker_with_data)
        assert report.total_leads == 2

    def test_report_conversion_rate(self, tracker_with_data):
        report = generate_funnel_report(tracker_with_data)
        assert report.conversion_rate == 0.5

    def test_report_avg_journey_length(self, tracker_with_data):
        report = generate_funnel_report(tracker_with_data)
        # c1 has 6 events, c2 has 2 => avg = 4.0
        assert report.avg_journey_length == 4.0

    def test_report_linear_attribution(self, tracker_with_data):
        report = generate_funnel_report(tracker_with_data, model="linear")
        assert "lead_bot" in report.attribution_by_bot
        assert "buyer_bot" in report.attribution_by_bot
        total = sum(report.attribution_by_bot.values())
        assert total == pytest.approx(1.0, rel=1e-3)

    def test_report_first_touch_attribution(self, tracker_with_data):
        report = generate_funnel_report(tracker_with_data, model="first_touch")
        assert report.attribution_by_bot["lead_bot"] == 1.0

    def test_report_last_touch_attribution(self, tracker_with_data):
        report = generate_funnel_report(tracker_with_data, model="last_touch")
        assert report.attribution_by_bot["buyer_bot"] == 1.0

    def test_report_time_decay_attribution(self, tracker_with_data):
        report = generate_funnel_report(tracker_with_data, model="time_decay")
        # buyer_bot handles later stages, should get more credit
        assert report.attribution_by_bot["buyer_bot"] > report.attribution_by_bot["lead_bot"]

    def test_report_empty_tracker(self):
        tracker = FunnelTracker()
        report = generate_funnel_report(tracker)
        assert report.total_leads == 0
        assert report.conversion_rate == 0.0
        assert report.avg_journey_length == 0.0
        assert report.attribution_by_bot == {}

    def test_report_no_conversions(self):
        tracker = FunnelTracker()
        tracker.record_event(_event(contact_id="c1", stage=STAGE_AWARENESS))
        report = generate_funnel_report(tracker)
        assert report.total_leads == 1
        assert report.conversion_rate == 0.0
        assert report.attribution_by_bot == {}

    def test_report_cost_per_conversion_is_none(self, tracker_with_data):
        report = generate_funnel_report(tracker_with_data)
        assert report.cost_per_conversion is None
