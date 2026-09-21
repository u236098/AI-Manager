"""CSRF-safe OAuth state parameter generation and validation.

Generates HMAC-signed state tokens tied to a timestamp.
On callback, verifies signature + TTL to prevent CSRF attacks.
"""
from __future__ import annotations
import hashlib
import hmac
import time
from app.config import get_settings


def generate_state() -> str:
    s = get_settings()
    ts = str(int(time.time()))
    sig = hmac.new(s.secret_key.encode(), ts.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{ts}.{sig}"


def validate_state(state: str) -> bool:
    s = get_settings()
    parts = state.split(".", 1)
    if len(parts) != 2:
        return False
    ts_str, sig = parts
    try:
        ts = int(ts_str)
    except ValueError:
        return False
    expected_sig = hmac.new(s.secret_key.encode(), ts_str.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected_sig):
        return False
    if time.time() - ts > s.oauth_state_ttl_seconds:
        return False
    return True
