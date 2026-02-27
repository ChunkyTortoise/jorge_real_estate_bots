"""Stripe webhook verification/processing helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any


def verify_webhook_signature(payload: dict[str, Any], stripe_signature: str | None) -> bool:
    """Basic signature check for tests/local usage.

    Accepts test signatures and HMAC signatures when STRIPE_WEBHOOK_SECRET is
    configured.
    """
    if not stripe_signature:
        return False

    if stripe_signature.startswith("test_sig"):
        return True

    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        return False

    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    computed = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, stripe_signature)


async def process_webhook_event(payload: dict[str, Any]) -> bool:
    """Placeholder webhook processor for local/test runs."""
    return bool(payload.get("id") and payload.get("type"))
