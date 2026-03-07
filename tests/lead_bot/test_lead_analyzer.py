"""Comprehensive tests for LeadAnalyzer service."""
from __future__ import annotations

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.lead_bot.services.lead_analyzer import LeadAnalyzer
from bots.shared.business_rules import JorgeBusinessRules
from bots.shared.models import PerformanceMetrics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def analyzer():
    """Create a LeadAnalyzer with mocked external dependencies."""
    with (
        patch("bots.lead_bot.services.lead_analyzer.ClaudeClient"),
        patch("bots.lead_bot.services.lead_analyzer.GHLClient"),
        patch("bots.lead_bot.services.lead_analyzer.CacheService"),
        patch("bots.lead_bot.services.lead_analyzer.event_broker"),
    ):
        return LeadAnalyzer()


def _lead(
    *,
    contact_id: str = "c1",
    name: str = "Test User",
    email: str = "test@example.com",
    phone: str = "5551234567",
    source: str = "website",
    tags: list | None = None,
    custom: dict | None = None,
) -> dict:
    """Helper to build a minimal lead_data dict."""
    return {
        "id": contact_id,
        "name": name,
        "email": email,
        "phone": phone,
        "source": source,
        "tags": tags or [],
        "customField": custom or {},
    }


# ---------------------------------------------------------------------------
# _extract_message_for_cache
# ---------------------------------------------------------------------------

class TestExtractMessageForCache:
    def test_basic_fields(self, analyzer):
        msg = analyzer._extract_message_for_cache(
            _lead(name="Alice", email="a@b.com", phone="555")
        )
        assert "Alice" in msg
        assert "a@b.com" in msg
        assert "555" in msg

    def test_tags_included(self, analyzer):
        msg = analyzer._extract_message_for_cache(_lead(tags=["buyer", "hot"]))
        assert "buyer" in msg
        assert "hot" in msg

    def test_custom_fields_budget_timeline_location(self, analyzer):
        msg = analyzer._extract_message_for_cache(
            _lead(custom={"budget": "500000", "timeline": "30", "location": "Ontario"})
        )
        assert "budget:500000" in msg
        assert "timeline:30" in msg
        assert "location:Ontario" in msg

    def test_empty_lead(self, analyzer):
        msg = analyzer._extract_message_for_cache({})
        assert msg == ""

    def test_partial_lead_no_email(self, analyzer):
        msg = analyzer._extract_message_for_cache({"name": "Bob", "phone": "123"})
        assert "Bob" in msg
        assert "123" in msg


# ---------------------------------------------------------------------------
# _parse_claude_response
# ---------------------------------------------------------------------------

class TestParseClaudeResponse:
    def test_valid_json(self, analyzer):
        raw = json.dumps({
            "score": 85,
            "temperature": "hot",
            "reasoning": "Great lead",
            "action": "Call now",
            "budget_estimate": "$400K-$600K",
            "timeline_estimate": "30 days",
        })
        result = analyzer._parse_claude_response(raw)
        assert result["score"] == 85
        assert result["temperature"] == "hot"
        assert result["reasoning"] == "Great lead"

    def test_json_embedded_in_text(self, analyzer):
        raw = 'Here is the analysis:\n{"score": 72, "temperature": "warm", "reasoning": "ok", "action": "follow up"}\nDone.'
        result = analyzer._parse_claude_response(raw)
        assert result["score"] == 72
        assert result["temperature"] == "warm"

    def test_score_clamped_to_0_100(self, analyzer):
        result = analyzer._parse_claude_response('{"score": 150, "temperature": "hot"}')
        assert result["score"] == 100

        result = analyzer._parse_claude_response('{"score": -20, "temperature": "cold"}')
        assert result["score"] == 0

    def test_invalid_temperature_defaults_to_warm(self, analyzer):
        result = analyzer._parse_claude_response('{"score": 50, "temperature": "blazing"}')
        assert result["temperature"] == "warm"

    def test_missing_score_defaults_to_50(self, analyzer):
        result = analyzer._parse_claude_response('{"temperature": "cold"}')
        assert result["score"] == 50

    def test_totally_invalid_response(self, analyzer):
        result = analyzer._parse_claude_response("not json at all")
        assert result["score"] == 50
        assert result["temperature"] == "warm"
        assert "Error" in result["reasoning"] or "error" in result["reasoning"].lower() or result["reasoning"] == "Error parsing AI response"

    def test_empty_string(self, analyzer):
        result = analyzer._parse_claude_response("")
        assert result["score"] == 50
        assert result["temperature"] == "warm"


# ---------------------------------------------------------------------------
# _fallback_scoring
# ---------------------------------------------------------------------------

class TestFallbackScoring:
    def test_email_and_phone(self, analyzer):
        result = analyzer._fallback_scoring(_lead(email="a@b.com", phone="555"))
        assert result["score"] == 60
        assert result["temperature"] == "warm"

    def test_email_only(self, analyzer):
        result = analyzer._fallback_scoring(_lead(email="a@b.com", phone=""))
        assert result["score"] == 50
        assert result["temperature"] == "warm"

    def test_phone_only(self, analyzer):
        result = analyzer._fallback_scoring(_lead(email="", phone="555"))
        assert result["score"] == 50
        assert result["temperature"] == "warm"

    def test_no_contact_info(self, analyzer):
        result = analyzer._fallback_scoring(_lead(email="", phone=""))
        assert result["score"] == 30
        assert result["temperature"] == "cold"

    def test_fallback_has_required_keys(self, analyzer):
        result = analyzer._fallback_scoring(_lead())
        for key in ("score", "temperature", "reasoning", "action", "budget_estimate", "timeline_estimate"):
            assert key in result


# ---------------------------------------------------------------------------
# _extract_lead_details — budget parsing
# ---------------------------------------------------------------------------

class TestExtractLeadDetails:
    def test_budget_range_with_k(self, analyzer):
        analysis = {"budget_estimate": "$400K-$600K"}
        result = analyzer._extract_lead_details(analysis, _lead())
        assert result.get("budget_min") == 400000
        assert result.get("budget_max") == 600000

    def test_single_budget_value(self, analyzer):
        analysis = {"budget_estimate": "$500000"}
        result = analyzer._extract_lead_details(analysis, _lead())
        assert result.get("budget_max") == 500000

    def test_no_budget(self, analyzer):
        analysis = {}
        result = analyzer._extract_lead_details(analysis, _lead())
        assert "budget_min" not in result
        assert "budget_max" not in result

    def test_location_from_custom_field(self, analyzer):
        analysis = {}
        lead = _lead(custom={"location": "Rancho Cucamonga"})
        result = analyzer._extract_lead_details(analysis, lead)
        assert result["location_preferences"] == ["Rancho Cucamonga"]

    def test_location_from_tags_service_area(self, analyzer):
        analysis = {}
        lead = _lead(tags=["Ontario", "random_tag"])
        result = analyzer._extract_lead_details(analysis, lead)
        assert "Ontario" in result.get("location_preferences", [])

    def test_no_location_info(self, analyzer):
        analysis = {}
        lead = _lead(tags=[], custom={})
        result = analyzer._extract_lead_details(analysis, lead)
        assert result.get("location_preferences") is None or result.get("location_preferences") == []


# ---------------------------------------------------------------------------
# _add_jorge_validation
# ---------------------------------------------------------------------------

class TestAddJorgeValidation:
    def test_high_priority_in_range_and_area(self, analyzer):
        analysis = {
            "budget_max": 500000,
            "location_preferences": ["Rancho Cucamonga"],
        }
        result = analyzer._add_jorge_validation(analysis)
        assert result["meets_jorge_criteria"] is True
        assert result["jorge_priority"] == "high"
        assert result["service_area_match"] is True
        assert result["estimated_commission"] == 500000 * 0.06

    def test_budget_below_minimum(self, analyzer):
        analysis = {"budget_max": 100000, "location_preferences": []}
        result = analyzer._add_jorge_validation(analysis)
        assert result["meets_jorge_criteria"] is False

    def test_budget_above_maximum(self, analyzer):
        analysis = {"budget_max": 1000000, "location_preferences": []}
        result = analyzer._add_jorge_validation(analysis)
        assert result["jorge_priority"] == "review_required"

    def test_no_budget_still_passes(self, analyzer):
        analysis = {"location_preferences": []}
        result = analyzer._add_jorge_validation(analysis)
        assert result["meets_jorge_criteria"] is True
        assert result["estimated_commission"] == 0.0


# ---------------------------------------------------------------------------
# _build_analysis_prompt
# ---------------------------------------------------------------------------

class TestBuildAnalysisPrompt:
    def test_includes_contact_info(self, analyzer):
        prompt = analyzer._build_analysis_prompt(
            _lead(name="Alice", email="alice@test.com", source="Zillow")
        )
        assert "Alice" in prompt
        assert "alice@test.com" in prompt
        assert "Zillow" in prompt

    def test_includes_custom_fields(self, analyzer):
        prompt = analyzer._build_analysis_prompt(
            _lead(custom={"budget": "400K", "timeline": "30 days"})
        )
        assert "budget" in prompt
        assert "400K" in prompt

    def test_no_tags_shows_none(self, analyzer):
        prompt = analyzer._build_analysis_prompt(_lead(tags=[]))
        assert "None" in prompt


# ---------------------------------------------------------------------------
# _get_system_prompt
# ---------------------------------------------------------------------------

class TestGetSystemPrompt:
    def test_system_prompt_contains_business_rules(self, analyzer):
        with patch("bots.lead_bot.services.lead_analyzer._get_bot_override", return_value={}):
            prompt = analyzer._get_system_prompt()
        assert "Price Range" in prompt
        assert "Service Areas" in prompt
        assert "HOT" in prompt
        assert "WARM" in prompt
        assert "COLD" in prompt
        assert "JSON" in prompt


# ---------------------------------------------------------------------------
# analyze_lead — full flow
# ---------------------------------------------------------------------------

class TestAnalyzeLead:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_fast(self, analyzer):
        """When performance cache has a result, return it without AI call."""
        cached = {
            "score": 90,
            "temperature": "hot",
            "reasoning": "cached",
            "action": "call",
            "budget_max": 500000,
            "location_preferences": ["Ontario"],
        }
        analyzer.performance_cache.get = AsyncMock(return_value=cached)

        with patch("bots.lead_bot.services.lead_analyzer.event_broker") as mock_eb:
            mock_eb.publish_lead_event = AsyncMock()
            result, metrics = await analyzer.analyze_lead(_lead())

        assert metrics.cache_hit is True
        assert result["score"] == 90
        # AI should NOT have been called
        analyzer.claude.agenerate.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_ai_skips_cache(self, analyzer):
        """force_ai=True bypasses cache and runs AI."""
        analyzer.performance_cache.get = AsyncMock(return_value={"score": 90})
        analyzer.performance_cache.set = AsyncMock()
        analyzer.claude.agenerate = AsyncMock(
            return_value=SimpleNamespace(content='{"score": 75, "temperature": "warm"}')
        )
        analyzer.ghl.update_lead_score = AsyncMock(return_value={"success": True})
        analyzer.ghl.send_immediate_followup = AsyncMock(return_value={"success": True})

        with (
            patch("bots.lead_bot.services.lead_analyzer.event_broker") as mock_eb,
            patch("bots.lead_bot.services.lead_analyzer.upsert_contact", new=AsyncMock()),
            patch("bots.lead_bot.services.lead_analyzer.upsert_lead", new=AsyncMock()),
        ):
            mock_eb.publish_lead_event = AsyncMock()
            result, metrics = await analyzer.analyze_lead(_lead(), force_ai=True)

        assert result["score"] == 75
        assert metrics.analysis_type == "ai"

    @pytest.mark.asyncio
    async def test_ai_error_triggers_fallback(self, analyzer):
        """When AI analysis raises, fallback scoring is used."""
        analyzer.performance_cache.get = AsyncMock(return_value=None)
        analyzer.performance_cache.set = AsyncMock()
        analyzer.claude.agenerate = AsyncMock(side_effect=RuntimeError("AI down"))

        with (
            patch("bots.lead_bot.services.lead_analyzer.event_broker") as mock_eb,
            patch("bots.lead_bot.services.lead_analyzer.upsert_contact", new=AsyncMock()),
            patch("bots.lead_bot.services.lead_analyzer.upsert_lead", new=AsyncMock()),
        ):
            mock_eb.publish_lead_event = AsyncMock()
            result, metrics = await analyzer.analyze_lead(
                _lead(email="a@b.com", phone="555")
            )

        assert result["fallback_used"] is True
        assert result["score"] == 60  # email + phone fallback
        assert metrics.analysis_type == "fallback"

    @pytest.mark.asyncio
    async def test_persists_lead_to_db(self, analyzer):
        """analyze_lead calls upsert_contact and upsert_lead."""
        analyzer.performance_cache.get = AsyncMock(return_value=None)
        analyzer.performance_cache.set = AsyncMock()
        analyzer.claude.agenerate = AsyncMock(
            return_value=SimpleNamespace(content='{"score": 80, "temperature": "hot"}')
        )
        analyzer.ghl.update_lead_score = AsyncMock(return_value={"success": True})
        analyzer.ghl.send_immediate_followup = AsyncMock(return_value={"success": True})

        mock_upsert_contact = AsyncMock()
        mock_upsert_lead = AsyncMock()

        with (
            patch("bots.lead_bot.services.lead_analyzer.event_broker") as mock_eb,
            patch("bots.lead_bot.services.lead_analyzer.upsert_contact", mock_upsert_contact),
            patch("bots.lead_bot.services.lead_analyzer.upsert_lead", mock_upsert_lead),
        ):
            mock_eb.publish_lead_event = AsyncMock()
            await analyzer.analyze_lead(_lead(contact_id="persist-test"))

        mock_upsert_contact.assert_called_once()
        mock_upsert_lead.assert_called_once()
        assert mock_upsert_lead.call_args.kwargs["contact_id"] == "persist-test"

    @pytest.mark.asyncio
    async def test_no_contact_id_skips_persist(self, analyzer):
        """When contact_id is None, _persist_lead does nothing."""
        mock_upsert_contact = AsyncMock()
        with patch("bots.lead_bot.services.lead_analyzer.upsert_contact", mock_upsert_contact):
            await analyzer._persist_lead(None, _lead(), {"score": 50})
        mock_upsert_contact.assert_not_called()


# ---------------------------------------------------------------------------
# PerformanceMetrics integration
# ---------------------------------------------------------------------------

class TestPerformanceMetrics:
    def test_metrics_to_dict(self):
        m = PerformanceMetrics(start_time=time.time())
        d = m.to_dict()
        assert "start_time" in d
        assert d["cache_hit"] is False
        assert d["five_minute_rule_compliant"] is True
