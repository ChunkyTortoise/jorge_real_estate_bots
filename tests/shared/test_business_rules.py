"""Tests for bots.shared.business_rules — JorgeBusinessRules."""

from __future__ import annotations

import pytest

from bots.shared.business_rules import JorgeBusinessRules


# ---------------------------------------------------------------------------
# calculate_commission
# ---------------------------------------------------------------------------

class TestCalculateCommission:
    def test_standard_rate(self):
        assert JorgeBusinessRules.calculate_commission(500000) == 30000.0

    def test_custom_rate(self):
        assert JorgeBusinessRules.calculate_commission(500000, rate=0.03) == 15000.0

    def test_min_budget(self):
        assert JorgeBusinessRules.calculate_commission(200000) == 12000.0

    def test_max_budget(self):
        assert JorgeBusinessRules.calculate_commission(800000) == 48000.0

    def test_zero_price(self):
        assert JorgeBusinessRules.calculate_commission(0) == 0.0

    def test_negative_price(self):
        # Negative budget produces negative commission (no guard in source)
        assert JorgeBusinessRules.calculate_commission(-100000) == -6000.0

    def test_very_large_price(self):
        result = JorgeBusinessRules.calculate_commission(10_000_000)
        assert result == 600000.0

    def test_fractional_price(self):
        result = JorgeBusinessRules.calculate_commission(350000.50)
        assert result == pytest.approx(21000.03)


# ---------------------------------------------------------------------------
# validate_lead — price bounds
# ---------------------------------------------------------------------------

class TestValidateLeadBudget:
    def test_budget_in_range(self):
        result = JorgeBusinessRules.validate_lead({"budget_max": 400000})
        assert result["passes_jorge_criteria"] is True
        assert result["estimated_commission"] == 24000.0

    def test_budget_below_min(self):
        result = JorgeBusinessRules.validate_lead({"budget_max": 100000})
        assert result["passes_jorge_criteria"] is False
        assert any("too low" in issue for issue in result["validation_issues"])

    def test_budget_above_max(self):
        result = JorgeBusinessRules.validate_lead({"budget_max": 1000000})
        assert result["jorge_priority"] == "review_required"
        assert any("above target" in issue for issue in result["validation_issues"])

    def test_budget_exactly_min(self):
        result = JorgeBusinessRules.validate_lead({"budget_max": 200000})
        assert result["passes_jorge_criteria"] is True

    def test_budget_exactly_max(self):
        result = JorgeBusinessRules.validate_lead({"budget_max": 800000})
        assert result["passes_jorge_criteria"] is True

    def test_zero_budget(self):
        result = JorgeBusinessRules.validate_lead({"budget_max": 0})
        # 0 is falsy so budget_max check is skipped
        assert result["passes_jorge_criteria"] is True
        assert result["estimated_commission"] == 0.0

    def test_missing_budget(self):
        result = JorgeBusinessRules.validate_lead({})
        assert result["passes_jorge_criteria"] is True
        assert result["estimated_commission"] == 0.0

    def test_negative_budget(self):
        # Negative is truthy, so it triggers the < MIN_BUDGET check and fails
        result = JorgeBusinessRules.validate_lead({"budget_max": -50000})
        assert result["passes_jorge_criteria"] is False
        assert any("too low" in issue for issue in result["validation_issues"])


# ---------------------------------------------------------------------------
# validate_lead — service area
# ---------------------------------------------------------------------------

class TestValidateLeadServiceArea:
    def test_matching_area(self):
        result = JorgeBusinessRules.validate_lead({
            "budget_max": 400000,
            "location_preferences": ["Rancho Cucamonga"],
        })
        assert result["service_area_match"] is True
        assert result["jorge_priority"] == "high"

    def test_non_matching_area(self):
        result = JorgeBusinessRules.validate_lead({
            "budget_max": 400000,
            "location_preferences": ["Los Angeles"],
        })
        assert result["service_area_match"] is False
        assert result["jorge_priority"] == "normal"

    def test_case_insensitive_area(self):
        result = JorgeBusinessRules.validate_lead({
            "budget_max": 400000,
            "location_preferences": ["rancho cucamonga"],
        })
        assert result["service_area_match"] is True

    def test_string_location_preferences(self):
        result = JorgeBusinessRules.validate_lead({
            "budget_max": 400000,
            "location_preferences": "Ontario, CA",
        })
        assert result["service_area_match"] is True

    def test_empty_location(self):
        result = JorgeBusinessRules.validate_lead({
            "budget_max": 400000,
            "location_preferences": [],
        })
        assert result["service_area_match"] is False

    def test_all_service_areas(self):
        for area in JorgeBusinessRules.SERVICE_AREAS:
            result = JorgeBusinessRules.validate_lead({
                "budget_max": 400000,
                "location_preferences": [area],
            })
            assert result["service_area_match"] is True, f"Failed for {area}"


# ---------------------------------------------------------------------------
# validate_lead — priority logic
# ---------------------------------------------------------------------------

class TestValidateLeadPriority:
    def test_high_priority_in_range_and_area(self):
        result = JorgeBusinessRules.validate_lead({
            "budget_max": 500000,
            "location_preferences": ["Upland"],
        })
        assert result["jorge_priority"] == "high"

    def test_normal_priority_in_range_no_area(self):
        result = JorgeBusinessRules.validate_lead({
            "budget_max": 500000,
            "location_preferences": ["San Diego"],
        })
        assert result["jorge_priority"] == "normal"

    def test_review_required_over_max(self):
        result = JorgeBusinessRules.validate_lead({
            "budget_max": 900000,
            "location_preferences": ["Fontana"],
        })
        assert result["jorge_priority"] == "review_required"


# ---------------------------------------------------------------------------
# get_temperature / is_hot_lead
# ---------------------------------------------------------------------------

class TestLeadTemperature:
    def test_hot(self):
        assert JorgeBusinessRules.get_temperature(80) == "hot"
        assert JorgeBusinessRules.get_temperature(100) == "hot"

    def test_warm(self):
        assert JorgeBusinessRules.get_temperature(60) == "warm"
        assert JorgeBusinessRules.get_temperature(79) == "warm"

    def test_cold(self):
        assert JorgeBusinessRules.get_temperature(0) == "cold"
        assert JorgeBusinessRules.get_temperature(59) == "cold"

    def test_is_hot_lead_true(self):
        assert JorgeBusinessRules.is_hot_lead(80) is True
        assert JorgeBusinessRules.is_hot_lead(95) is True

    def test_is_hot_lead_false(self):
        assert JorgeBusinessRules.is_hot_lead(79) is False
        assert JorgeBusinessRules.is_hot_lead(0) is False


# ---------------------------------------------------------------------------
# is_qualified_lead
# ---------------------------------------------------------------------------

class TestIsQualifiedLead:
    def test_qualified(self):
        assert JorgeBusinessRules.is_qualified_lead({"budget_max": 400000}) is True

    def test_not_qualified(self):
        assert JorgeBusinessRules.is_qualified_lead({"budget_max": 100000}) is False


# ---------------------------------------------------------------------------
# get_service_areas / is_service_area
# ---------------------------------------------------------------------------

class TestServiceAreas:
    def test_get_service_areas_returns_copy(self):
        areas = JorgeBusinessRules.get_service_areas()
        assert areas == ["Rancho Cucamonga", "Ontario", "Upland", "Fontana", "Chino Hills"]
        # Should be a copy, not the same list
        areas.append("test")
        assert "test" not in JorgeBusinessRules.SERVICE_AREAS

    def test_is_service_area_true(self):
        assert JorgeBusinessRules.is_service_area("Rancho Cucamonga") is True
        assert JorgeBusinessRules.is_service_area("downtown Fontana area") is True

    def test_is_service_area_false(self):
        assert JorgeBusinessRules.is_service_area("Los Angeles") is False
        assert JorgeBusinessRules.is_service_area("") is False

    def test_is_service_area_case_insensitive(self):
        assert JorgeBusinessRules.is_service_area("ONTARIO") is True
        assert JorgeBusinessRules.is_service_area("chino hills") is True
