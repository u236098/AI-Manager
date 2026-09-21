"""DB-backed OAuth transaction storage — serverless-safe.

Stores PKCE verifiers and OAuth context in the database, keyed by
the HMAC-signed state parameter. Single-use: pop deletes the row.
"""
from __future__ import annotations
from typing import Any
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth import OAuthTransaction


async def put_oauth_session(state: str, db: AsyncSession, **data: Any) -> None:
    txn = OAuthTransaction(
        state=state,
        provider=data.get("provider", ""),
        data=data,
    )
    db.add(txn)
    await db.commit()


async def pop_oauth_session(state: str, db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(
        select(OAuthTransaction).where(OAuthTransaction.state == state)
    )
    txn = result.scalar_one_or_none()
    if txn is None:
        return None
    data = txn.data
    await db.execute(
        delete(OAuthTransaction).where(OAuthTransaction.state == state)
    )
    await db.commit()
    return data
