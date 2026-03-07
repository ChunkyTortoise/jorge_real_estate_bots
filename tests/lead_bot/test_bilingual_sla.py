"""T3: Tests for bilingual SLA check inside check_stalled_conversations."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.lead_bot.main import check_stalled_conversations


def _make_overdue_conv(contact_id: str, hours_overdue: float = 2.0) -> MagicMock:
    conv = MagicMock()
    conv.contact_id = contact_id
    conv.status = "awaiting_human"
    conv.bot_type = "bilingual_handoff"
    conv.last_activity = datetime.now(timezone.utc) - timedelta(hours=hours_overdue)
    return conv


def _make_session_cm(conversations: list) -> tuple:
    """Return (factory_mock, session_mock) yielding the given conversations."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = conversations

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    factory = MagicMock(return_value=mock_session)
    return factory, mock_session


def _make_sleep(*, iterations: int = 1):
    """Patch for asyncio.sleep: allows N iterations then raises CancelledError."""
    call_count = [0]

    async def _sleep(delay):
        call_count[0] += 1
        if call_count[0] > iterations:
            raise asyncio.CancelledError()

    return _sleep


@pytest.mark.asyncio
async def test_overdue_bilingual_triggers_alert():
    """Contacts overdue > 1h with bilingual_handoff status trigger push_alert_outbound."""
    factory, _ = _make_session_cm([_make_overdue_conv("c-bil-1")])
    alert_calls: list = []

    async def _capture_alert(alert, url):
        alert_calls.append((alert, url))

    with (
        patch("asyncio.sleep", side_effect=_make_sleep(iterations=1)),
        patch("database.session.AsyncSessionFactory", factory),
        patch("database.models.ConversationModel", MagicMock()),
        patch("sqlalchemy.select", MagicMock()),
        patch("bots.shared.alerting_service.push_alert_outbound", side_effect=_capture_alert),
        patch("bots.lead_bot.main.settings") as mock_settings,
        patch("bots.shared.alerting_service.AlertingService") as mock_svc_cls,
    ):
        mock_settings.alert_webhook_url = "https://hooks.slack.com/test"
        mock_svc_cls.return_value = MagicMock()

        try:
            await check_stalled_conversations()
        except asyncio.CancelledError:
            pass

    assert len(alert_calls) == 1
    alert_payload, url = alert_calls[0]
    assert alert_payload["rule_name"] == "bilingual_sla_breach"
    assert alert_payload["severity"] == "warning"
    assert url == "https://hooks.slack.com/test"


@pytest.mark.asyncio
async def test_non_overdue_bilingual_no_alert():
    """Contacts with last_activity within 1h do NOT trigger push_alert_outbound."""
    conv = _make_overdue_conv("c-bil-2", hours_overdue=0.5)
    factory, _ = _make_session_cm([conv])
    alert_calls: list = []

    async def _capture_alert(alert, url):
        alert_calls.append(alert)

    with (
        patch("asyncio.sleep", side_effect=_make_sleep(iterations=1)),
        patch("database.session.AsyncSessionFactory", factory),
        patch("database.models.ConversationModel", MagicMock()),
        patch("sqlalchemy.select", MagicMock()),
        patch("bots.shared.alerting_service.push_alert_outbound", side_effect=_capture_alert),
        patch("bots.lead_bot.main.settings") as mock_settings,
        patch("bots.shared.alerting_service.AlertingService"),
    ):
        mock_settings.alert_webhook_url = "https://hooks.slack.com/test"

        try:
            await check_stalled_conversations()
        except asyncio.CancelledError:
            pass

    assert len(alert_calls) == 0


@pytest.mark.asyncio
async def test_no_webhook_url_skips_push():
    """When alert_webhook_url is falsy, push_alert_outbound is never called."""
    factory, _ = _make_session_cm([_make_overdue_conv("c-bil-3")])
    alert_calls: list = []

    async def _capture_alert(alert, url):
        alert_calls.append(alert)

    with (
        patch("asyncio.sleep", side_effect=_make_sleep(iterations=1)),
        patch("database.session.AsyncSessionFactory", factory),
        patch("database.models.ConversationModel", MagicMock()),
        patch("sqlalchemy.select", MagicMock()),
        patch("bots.shared.alerting_service.push_alert_outbound", side_effect=_capture_alert),
        patch("bots.lead_bot.main.settings") as mock_settings,
        patch("bots.shared.alerting_service.AlertingService") as mock_svc_cls,
    ):
        mock_settings.alert_webhook_url = None
        mock_svc_cls.return_value = MagicMock()

        try:
            await check_stalled_conversations()
        except asyncio.CancelledError:
            pass

    assert len(alert_calls) == 0
