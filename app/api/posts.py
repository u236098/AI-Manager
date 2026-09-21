"""Post management and video analysis endpoints."""
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.core import Post

router = APIRouter()


@router.get("/")
async def list_posts(
    account_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Post).order_by(Post.published_at.desc()).offset(offset).limit(limit)
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
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
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


@router.post("/draft-review")
async def review_draft_video(
    video: UploadFile = File(...),
    objective: str = Form("reach"),
    creator_id: int = Form(1),
    db: AsyncSession = Depends(get_db),
):
    """Upload a draft video for AI review before posting."""
    from app.services.video_analyzer import analyze_draft
    result = await analyze_draft(video, objective, creator_id, db)
    return result
