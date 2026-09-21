"""Short-lived OAuth transaction storage for local development.

Keeps PKCE verifiers and creator/provider context server-side, keyed by the
HMAC-signed OAuth state value. This is intentionally process-local for the
single-process local dev setup. Replace with Redis/DB before multi-worker or
production deployment.
"""
from __future__ import annotations

import time
from typing import Any

from app.config import get_settings

_sessions: dict[str, tuple[float, dict[str, Any]]] = {}


def put_oauth_session(state: str, **data: Any) -> None:
    _sessions[state] = (time.time(), data)
    _prune()


def pop_oauth_session(state: str) -> dict[str, Any] | None:
    item = _sessions.pop(state, None)
    if item is None:
        return None
    created_at, data = item
    if time.time() - created_at > get_settings().oauth_state_ttl_seconds:
        return None
    return data


def _prune() -> None:
    cutoff = time.time() - get_settings().oauth_state_ttl_seconds
    stale = [key for key, (created_at, _) in _sessions.items() if created_at < cutoff]
    for key in stale:
        _sessions.pop(key, None)
