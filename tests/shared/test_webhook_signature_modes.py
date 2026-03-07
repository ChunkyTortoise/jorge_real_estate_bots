"""Tests for all three webhook signature verification modes: RSA, HMAC, and pass-through."""
from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
from unittest.mock import patch

import pytest

from bots.lead_bot.main import verify_ghl_signature


# ── RSA mode ─────────────────────────────────────────────────────────────────

def test_rsa_valid_signature_accepted():
    """Valid RSA signature passes verification."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.backends import default_backend

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()
    pem = public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    payload = b'{"contact_id": "c1"}'
    signature = base64.b64encode(
        private_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    ).decode()

    with patch("bots.lead_bot.main.settings") as s:
        s.ghl_webhook_public_key = pem
        s.ghl_webhook_secret = None
        assert verify_ghl_signature(payload, signature) is True


def test_rsa_invalid_signature_rejected():
    """Tampered RSA signature is rejected."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.backends import default_backend

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()
    pem = public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    payload = b'{"contact_id": "c1"}'
    bad_sig = base64.b64encode(b"fakesignature").decode()

    with patch("bots.lead_bot.main.settings") as s:
        s.ghl_webhook_public_key = pem
        s.ghl_webhook_secret = None
        assert verify_ghl_signature(payload, bad_sig) is False


def test_rsa_missing_signature_rejected():
    """When RSA mode active and signature is None, returns False."""
    with patch("bots.lead_bot.main.settings") as s:
        s.ghl_webhook_public_key = "-----BEGIN PUBLIC KEY-----\nfake\n-----END PUBLIC KEY-----\n"
        s.ghl_webhook_secret = None
        assert verify_ghl_signature(b"payload", None) is False


# ── HMAC mode ────────────────────────────────────────────────────────────────

def test_hmac_hex_valid_accepted():
    """Valid HMAC hex digest is accepted."""
    secret = "test-secret"
    payload = b'{"contact_id": "c2"}'
    sig = _hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    with patch("bots.lead_bot.main.settings") as s:
        s.ghl_webhook_public_key = None
        s.ghl_webhook_secret = secret
        assert verify_ghl_signature(payload, sig) is True


def test_hmac_b64_valid_accepted():
    """Valid HMAC base64 digest is accepted."""
    secret = "test-secret"
    payload = b'{"contact_id": "c3"}'
    sig_bytes = _hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    sig = base64.b64encode(sig_bytes).decode()

    with patch("bots.lead_bot.main.settings") as s:
        s.ghl_webhook_public_key = None
        s.ghl_webhook_secret = secret
        assert verify_ghl_signature(payload, sig) is True


def test_hmac_invalid_rejected():
    """Bad HMAC value is rejected."""
    with patch("bots.lead_bot.main.settings") as s:
        s.ghl_webhook_public_key = None
        s.ghl_webhook_secret = "test-secret"
        assert verify_ghl_signature(b"payload", "deadbeef") is False


def test_hmac_missing_signature_rejected():
    """When HMAC mode active and signature is None, returns False."""
    with patch("bots.lead_bot.main.settings") as s:
        s.ghl_webhook_public_key = None
        s.ghl_webhook_secret = "test-secret"
        assert verify_ghl_signature(b"payload", None) is False


# ── Pass-through mode ────────────────────────────────────────────────────────

def test_no_secret_allows_all():
    """When no secret configured, all requests are allowed (pass-through)."""
    with patch("bots.lead_bot.main.settings") as s:
        s.ghl_webhook_public_key = None
        s.ghl_webhook_secret = None
        s.environment = "development"
        assert verify_ghl_signature(b"any-payload", None) is True
        assert verify_ghl_signature(b"any-payload", "random-sig") is True


def test_no_secret_production_still_allows_but_would_warn():
    """Pass-through in production still returns True (warning is logged elsewhere)."""
    with patch("bots.lead_bot.main.settings") as s:
        s.ghl_webhook_public_key = None
        s.ghl_webhook_secret = None
        s.environment = "production"
        result = verify_ghl_signature(b"payload", None)
        assert result is True
