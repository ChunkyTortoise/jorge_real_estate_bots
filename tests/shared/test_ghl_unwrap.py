"""Tests for unwrap_ghl_response helper."""
import pytest
from bots.shared.ghl_client import unwrap_ghl_response


def test_unwraps_success_wrapper():
    resp = {"success": True, "data": {"contact": {"id": "c1", "tags": ["hot"]}}}
    assert unwrap_ghl_response(resp) == {"contact": {"id": "c1", "tags": ["hot"]}}


def test_unwraps_failure_wrapper():
    resp = {"success": False, "data": {}, "error": "not found"}
    assert unwrap_ghl_response(resp) == {}


def test_passthrough_when_already_unwrapped():
    resp = {"contact": {"id": "c1"}}
    assert unwrap_ghl_response(resp) is resp


def test_passthrough_empty_dict():
    assert unwrap_ghl_response({}) == {}


def test_passthrough_non_dict():
    # Should not crash — just return as-is
    result = unwrap_ghl_response(None)  # type: ignore[arg-type]
    assert result is None


def test_nested_custom_fields_accessible():
    """Verify the primary use case: extracting customFields after unwrap."""
    wrapped = {
        "success": True,
        "data": {
            "contact": {
                "id": "c1",
                "customFields": [{"fieldKey": "ai_mode", "value": "buyer"}],
            }
        },
    }
    inner = unwrap_ghl_response(wrapped)
    cfs = inner.get("contact", inner).get("customFields", [])
    assert cfs[0]["value"] == "buyer"
