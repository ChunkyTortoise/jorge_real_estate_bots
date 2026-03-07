"""T2: Tests for JSONFormatter, PII redaction, and correlation ID in bots.shared.logger."""
from __future__ import annotations

import json
import logging

import pytest

from bots.shared.logger import (
    JSONFormatter,
    get_correlation_id,
    set_correlation_id,
)


def _make_record(
    message: str,
    level: int = logging.INFO,
    name: str = "test.logger",
    correlation_id: str = "test-corr-id",
) -> logging.LogRecord:
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="test.py",
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    record.correlation_id = correlation_id
    return record


class TestJSONFormatter:
    """T2: JSONFormatter produces correct structured JSON output."""

    @pytest.fixture
    def fmt(self) -> JSONFormatter:
        return JSONFormatter()

    def test_output_is_valid_json(self, fmt):
        output = fmt.format(_make_record("hello"))
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_has_required_keys(self, fmt):
        parsed = json.loads(fmt.format(_make_record("hello")))
        for key in ("timestamp", "level", "correlation_id", "logger", "message"):
            assert key in parsed, f"Missing key: {key}"

    def test_level_name(self, fmt):
        parsed = json.loads(fmt.format(_make_record("msg", level=logging.WARNING)))
        assert parsed["level"] == "WARNING"

    def test_logger_name(self, fmt):
        parsed = json.loads(fmt.format(_make_record("msg", name="bots.lead_bot")))
        assert parsed["logger"] == "bots.lead_bot"

    def test_message(self, fmt):
        parsed = json.loads(fmt.format(_make_record("my log message")))
        assert parsed["message"] == "my log message"

    def test_correlation_id_propagated(self, fmt):
        parsed = json.loads(fmt.format(_make_record("msg", correlation_id="abc-123")))
        assert parsed["correlation_id"] == "abc-123"

    def test_default_correlation_id_when_attribute_missing(self, fmt):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="msg", args=(), exc_info=None,
        )
        # No correlation_id attribute set on record
        parsed = json.loads(fmt.format(record))
        assert parsed["correlation_id"] == "system"

    def test_timestamp_format(self, fmt):
        """Timestamp must match ISO-like format YYYY-MM-DDTHH:MM:SS."""
        import re
        parsed = json.loads(fmt.format(_make_record("msg")))
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", parsed["timestamp"])


class TestPIIRedaction:
    """T2: JSONFormatter.redact scrubs emails and phone numbers."""

    def test_redacts_email(self):
        result = JSONFormatter.redact("Contact: alice@example.com today")
        assert "alice@example.com" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_redacts_phone_dashes(self):
        result = JSONFormatter.redact("Call 555-123-4567 now")
        assert "555-123-4567" not in result
        assert "[REDACTED_PHONE]" in result

    def test_redacts_phone_parens(self):
        result = JSONFormatter.redact("(555) 123-4567")
        assert "(555) 123-4567" not in result
        assert "[REDACTED_PHONE]" in result

    def test_no_pii_unchanged(self):
        msg = "System started successfully"
        assert JSONFormatter.redact(msg) == msg

    def test_redacts_both_in_same_string(self):
        result = JSONFormatter.redact("Email: bob@test.com phone: 555-999-8888")
        assert "[REDACTED_EMAIL]" in result
        assert "[REDACTED_PHONE]" in result
        assert "bob@test.com" not in result
        assert "555-999-8888" not in result


class TestCorrelationID:
    """T2: set_correlation_id / get_correlation_id context variable round-trip."""

    def test_set_and_get(self):
        cid = set_correlation_id("unit-test-id")
        assert cid == "unit-test-id"
        assert get_correlation_id() == "unit-test-id"

    def test_generates_uuid_when_none(self):
        cid = set_correlation_id()
        # UUID4 has 36 characters (with dashes)
        assert len(cid) == 36
        assert get_correlation_id() == cid

    def test_overwrite(self):
        set_correlation_id("first")
        set_correlation_id("second")
        assert get_correlation_id() == "second"
