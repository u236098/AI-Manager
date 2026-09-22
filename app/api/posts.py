"""Post management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_creator_id
from app.models.core import PlatformAccount, Post

router = APIRouter()


@router.get("/")
async def list_posts(
    account_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    creator_id: int = Depends(get_creator_id),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Post)
        .join(PlatformAccount, PlatformAccount.id == Post.account_id)
        .where(PlatformAccount.creator_id == creator_id)
        .order_by(Post.published_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if account_id:
        query = query.where(Post.account_id == account_id)
    result = await db.execute(query)
    posts = result.scalars().all()
    return [
        {
            "id": p.id,
            "platform_post_id": p.platform_post_id,
            "post_type": p.post_type.value if p.post_type else None,
            "objective": p.objective.value if p.objective else None,
            "caption": p.caption,
            "duration_seconds": p.duration_seconds,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "is_pinned": p.is_pinned,
        }
        for p in posts
    ]


@router.get("/{post_id}")
async def get_post(
    post_id: int,
    creator_id: int = Depends(get_creator_id),
    db: AsyncSession = Depends(get_db),
):
    post = await db.scalar(
        select(Post)
        .join(PlatformAccount, PlatformAccount.id == Post.account_id)
        .where(Post.id == post_id, PlatformAccount.creator_id == creator_id)
    )
    if not post:
        from fastapi import HTTPException
        raise HTTPException(404, "Post not found")
    return {
        "id": post.id,
        "post_type": post.post_type.value if post.post_type else None,
        "objective": post.objective.value if post.objective else None,
        "caption": post.caption,
        "duration_seconds": post.duration_seconds,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "is_pinned": post.is_pinned,
        "series_id": post.series_id,
        "series_episode": post.series_episode,
    }

