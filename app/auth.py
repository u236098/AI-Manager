"""Clerk JWT auth — protects REST API and MCP endpoints.

When CLERK_SECRET_KEY is empty (local dev), auth is disabled and
creator_id defaults to 1. In production, every request must carry
a valid Clerk Bearer token.
"""
from __future__ import annotations

import contextvars
import logging
from functools import lru_cache

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)

creator_id_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    "creator_id", default=0
)


def _auth_enabled() -> bool:
    from app.config import get_settings
    return bool(get_settings().clerk_secret_key)


@lru_cache
def _jwks_client() -> PyJWKClient | None:
    from app.config import get_settings
    url = get_settings().clerk_jwks_url
    if not url:
        return None
    return PyJWKClient(url)


def verify_clerk_token(token: str) -> dict:
    """Verify a Clerk JWT and return its claims."""
    client = _jwks_client()
    if client is None:
        raise ValueError("CLERK_JWKS_URL not configured")
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )


async def _resolve_creator_id(clerk_user_id: str, db: AsyncSession) -> int | None:
    from app.models.core import Creator
    creator = await db.scalar(
        select(Creator).where(Creator.clerk_user_id == clerk_user_id)
    )
    return creator.id if creator else None


async def get_creator_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> int:
    """FastAPI dependency — returns the authenticated creator_id.

    Auth disabled (no CLERK_SECRET_KEY): returns 1 (dev mode).
    Auth enabled: verifies Clerk JWT, resolves creator_id from DB.
    """
    if not _auth_enabled():
        return 1

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing authorization token")

    try:
        claims = verify_clerk_token(auth_header[7:])
    except Exception as e:
        logger.warning("JWT verification failed: %s", e)
        raise HTTPException(401, "Invalid authorization token")

    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(401, "Token missing subject claim")

    cid = await _resolve_creator_id(clerk_user_id, db)
    if cid is None:
        raise HTTPException(403, "User not associated with any creator account")
    return cid


class MCPAuthMiddleware:
    """ASGI middleware that authenticates MCP requests and sets creator_id_var.

    Wraps the MCP ASGI handler so tools can read creator_id_var.get().
    When auth is disabled, sets creator_id_var to 1.
    """

    def __init__(self, app, db_factory):
        self.app = app
        self.db_factory = db_factory

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        if not _auth_enabled():
            creator_id_var.set(1)
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers", []))
        auth_value = headers.get(b"authorization", b"").decode()

        if not auth_value.startswith("Bearer "):
            return await _send_error(send, 401, "Missing authorization token")

        try:
            claims = verify_clerk_token(auth_value[7:])
        except Exception as e:
            logger.warning("MCP JWT verification failed: %s", e)
            return await _send_error(send, 401, "Invalid authorization token")

        clerk_user_id = claims.get("sub")
        if not clerk_user_id:
            return await _send_error(send, 401, "Token missing subject claim")

        async with self.db_factory() as db:
            cid = await _resolve_creator_id(clerk_user_id, db)

        if cid is None:
            return await _send_error(send, 403, "User not associated with any creator")

        creator_id_var.set(cid)
        return await self.app(scope, receive, send)


async def _send_error(send, status: int, message: str):
    import json
    body = json.dumps({"error": message}).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
