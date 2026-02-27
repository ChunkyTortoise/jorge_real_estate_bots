"""
In-memory bot settings store.

Only stores *overrides* — bots fall back to their own hardcoded defaults
when no override is set, so there's no duplication or drift.

Overrides apply at request time (no restart needed) but are lost on process
restart; the dashboard re-saves them after any deployment.
"""
from __future__ import annotations

from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "seller": {},   # populated at runtime via GET /admin/settings (bot injects its defaults)
}

# Live overrides keyed by bot name — updated via PUT /admin/settings
_overrides: Dict[str, Any] = {}

KNOWN_BOTS = {"seller", "buyer", "lead"}


def get_override(bot: str) -> Dict[str, Any]:
    """Return only the active overrides for a bot (empty dict = use hardcoded defaults)."""
    return _overrides.get(bot, {})


def update_settings(bot: str, settings: Dict[str, Any]) -> None:
    """Apply partial settings overrides for a bot."""
    _overrides.setdefault(bot, {}).update(settings)


def get_all_overrides() -> Dict[str, Any]:
    """Return all active overrides."""
    return {bot: _overrides.get(bot, {}) for bot in KNOWN_BOTS}


def reset(bot: str | None = None) -> None:
    """Clear overrides (all bots, or a specific one)."""
    if bot:
        _overrides.pop(bot, None)
    else:
        _overrides.clear()
