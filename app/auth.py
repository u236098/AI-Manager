"""Clerk JWT auth — protects REST API and MCP endpoints.

When CLERK_SECRET_KEY is empty (local dev), auth is disabled and
creator_id defaults to 1. In production, every request must carry
a valid Clerk Bearer token.
"""
from __future__ import annotations

import contextvars
import json
import logging
from functools import lru_cache

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

logger = logging.getLogger(__name__)

MCP_SCOPES = ("openid", "profile", "email", "offline_access")

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
    from app.config import get_settings

    issuer = get_settings().clerk_issuer_url
    decode_kwargs = {
        "algorithms": ["RS256"],
        "options": {"verify_aud": False},
    }
    if issuer:
        decode_kwargs["issuer"] = issuer

    return jwt.decode(
        token,
        signing_key.key,
        **decode_kwargs,
    )


def verify_mcp_token(token: str) -> dict:
    """Verify a Clerk OAuth token issued for this MCP connection."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.clerk_issuer_url:
        raise ValueError("CLERK_ISSUER or CLERK_JWKS_URL is required for MCP OAuth")
    claims = verify_clerk_token(token)

    audiences = claims.get("aud") or []
    if isinstance(audiences, str):
        audiences = [audiences]

    resource = claims.get("resource")
    resource_values = [resource] if isinstance(resource, str) else (resource or [])
    accepted_audiences = {
        settings.canonical_mcp_resource_url,
        settings.canonical_mcp_resource_url.rstrip("/"),
        settings.mcp_oauth_client_id,
    }
    if not accepted_audiences.intersection({*audiences, *resource_values}):
        raise ValueError("Token was not issued for the Kobby Manager MCP resource")

    scope_claim = claims.get("scope", "")
    token_scopes = set(scope_claim.split()) if isinstance(scope_claim, str) else set(scope_claim)
    if "openid" not in token_scopes:
        raise ValueError("Token is missing the required openid scope")

    return claims


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
            context_token = creator_id_var.set(1)
            try:
                return await self.app(scope, receive, send)
            finally:
                creator_id_var.reset(context_token)

        headers = dict(scope.get("headers", []))
        auth_value = headers.get(b"authorization", b"").decode()

        if not auth_value.startswith("Bearer "):
            return await _send_error(
                send,
                401,
                "Missing authorization token",
                oauth_error="invalid_token",
            )

        try:
            claims = verify_mcp_token(auth_value[7:])
        except Exception as e:
            logger.warning("MCP JWT verification failed: %s", e)
            return await _send_error(
                send,
                401,
                "Invalid authorization token",
                oauth_error="invalid_token",
            )

        clerk_user_id = claims.get("sub")
        if not clerk_user_id:
            return await _send_error(send, 401, "Token missing subject claim")

        async with self.db_factory() as db:
            cid = await _resolve_creator_id(clerk_user_id, db)

        if cid is None:
            return await _send_error(send, 403, "User not associated with any creator")

        context_token = creator_id_var.set(cid)
        try:
            return await self.app(scope, receive, send)
        finally:
            creator_id_var.reset(context_token)


async def _send_error(
    send,
    status: int,
    message: str,
    oauth_error: str | None = None,
):
    from app.config import get_settings

    body = json.dumps({"error": message}).encode()
    headers = [
        [b"content-type", b"application/json"],
        [b"content-length", str(len(body)).encode()],
    ]
    if oauth_error:
        settings = get_settings()
        metadata_url = f"{settings.base_url.rstrip('/')}/.well-known/oauth-protected-resource"
        challenge = (
            f'Bearer resource_metadata="{metadata_url}", '
            f'scope="{" ".join(MCP_SCOPES)}", '
            f'error="{oauth_error}", error_description="{message}"'
        )
        headers.append([b"www-authenticate", challenge.encode()])

    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
