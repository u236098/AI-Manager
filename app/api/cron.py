"""Protected scheduled jobs for the production deployment."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.core import PlatformAccount
from app.services.sync import sync_account

router = APIRouter()
log = logging.getLogger("kobby.cron")


@router.get("/sync")
async def scheduled_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Synchronize every active platform account.

    Vercel sends ``Authorization: Bearer $CRON_SECRET`` for configured cron
    invocations. This route is intentionally separate from user-authenticated
    REST routes because it runs without a browser session.
    """
    expected = get_settings().cron_secret
    provided = request.headers.get("authorization", "")
    if not expected or not secrets.compare_digest(
        provided, f"Bearer {expected}"
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")

    accounts = (
        await db.scalars(
            select(PlatformAccount).where(PlatformAccount.is_active == True)
        )
    ).all()

    results: list[dict] = []
    for account in accounts:
        try:
            result = await sync_account(account.id, db)
            results.append({"account_id": account.id, **result})
        except Exception as exc:  # isolate one provider/account failure
            await db.rollback()
            log.exception("Scheduled sync failed for account %s", account.id)
            results.append({
                "account_id": account.id,
                "account": account.username,
                "status": "error",
                "error_type": type(exc).__name__,
            })

    failed = sum(1 for result in results if result.get("status") == "error")
    return {
        "status": "partial" if failed else "ok",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "accounts_attempted": len(accounts),
        "accounts_failed": failed,
        "results": results,
        "note": (
            "This job syncs posts, current metrics, and profile snapshots. "
            "Instagram per-post insight enrichment remains manual."
        ),
    }
