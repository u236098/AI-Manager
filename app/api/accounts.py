"""Account management endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_creator_id
from app.models.core import PlatformAccount, ProfileSnapshot
from app.services.sync import sync_account, enrich_ig_insights

router = APIRouter()


@router.get("/")
async def list_accounts(creator_id: int = Depends(get_creator_id), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.creator_id == creator_id,
            PlatformAccount.is_active == True,
        )
    )
    accounts = result.scalars().all()
    return [
        {
            "id": a.id,
            "platform": a.platform.value,
            "username": a.username,
            "display_name": a.display_name,
            "connected_at": a.connected_at.isoformat() if a.connected_at else None,
        }
        for a in accounts
    ]


@router.post("/{account_id}/sync")
async def sync_account_endpoint(account_id: int, db: AsyncSession = Depends(get_db)):
    return await sync_account(account_id, db)


@router.post("/{account_id}/enrich-insights")
async def enrich_insights_endpoint(account_id: int, db: AsyncSession = Depends(get_db)):
    return await enrich_ig_insights(account_id, db)


@router.get("/{account_id}/profile-history")
async def profile_history(account_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.account_id == account_id)
        .order_by(ProfileSnapshot.captured_at.desc())
        .limit(30)
    )
    snapshots = result.scalars().all()
    return [
        {
            "id": s.id,
            "captured_at": s.captured_at.isoformat(),
            "username": s.username,
            "bio": s.bio,
            "follower_count": s.follower_count,
            "following_count": s.following_count,
            "post_count": s.post_count,
        }
        for s in snapshots
    ]
