"""Dashboard aggregate endpoints — one call for the overview page."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_creator_id
from app.models.core import (
    PlatformAccount, Post, PostMetric, PostType, Platform,
    AccountMetricSnapshot, ProfileSnapshot,
)
from app.models.manager import ManagerMemory, KnowledgeType

router = APIRouter()


@router.get("/overview")
async def dashboard_overview(creator_id: int = Depends(get_creator_id), db: AsyncSession = Depends(get_db)):
    accounts_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.creator_id == creator_id,
            PlatformAccount.is_active == True,
            PlatformAccount.access_token.isnot(None),
        )
    )
    accounts = accounts_result.scalars().all()

    account_summaries = []
    for acc in accounts:
        latest_profile = (
            await db.scalars(
                select(ProfileSnapshot)
                .where(ProfileSnapshot.account_id == acc.id)
                .order_by(ProfileSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()

        post_count = await db.scalar(
            select(func.count()).select_from(Post).where(Post.account_id == acc.id)
        )

        account_summaries.append({
            "id": acc.id,
            "platform": acc.platform.value,
            "username": acc.username,
            "followers": latest_profile.follower_count if latest_profile else None,
            "post_count": post_count,
        })

    total_followers = sum(a["followers"] or 0 for a in account_summaries)

    observations = (
        await db.scalars(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.is_active == True,
                ManagerMemory.knowledge_type == KnowledgeType.OBSERVATION,
            ).order_by(ManagerMemory.confidence.desc().nulls_last()).limit(8)
        )
    ).all()

    hypotheses = (
        await db.scalars(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.is_active == True,
                ManagerMemory.knowledge_type == KnowledgeType.HYPOTHESIS,
            ).order_by(ManagerMemory.updated_at.desc()).limit(3)
        )
    ).all()

    top_posts = []
    for acc in accounts:
        result = await db.execute(
            select(Post, PostMetric)
            .join(PostMetric)
            .where(Post.account_id == acc.id)
            .order_by(
                PostMetric.reach.desc().nulls_last(),
                PostMetric.views.desc().nulls_last(),
                PostMetric.likes.desc().nulls_last(),
            )
            .limit(5)
        )
        for post, metric in result:
            top_posts.append({
                "id": post.id,
                "platform": acc.platform.value,
                "post_type": post.post_type.value if post.post_type else None,
                "caption": (post.caption or "")[:100],
                "published_at": post.published_at.isoformat() if post.published_at else None,
                "reach": metric.reach,
                "views": metric.views,
                "likes": metric.likes,
                "saves": metric.saves,
                "shares": metric.shares,
                "followers_from_post": metric.followers_from_post,
                "comments": metric.comments_count,
            })
    top_posts.sort(key=lambda p: (p.get("reach") or p.get("views") or p.get("likes") or 0), reverse=True)

    return {
        "accounts": account_summaries,
        "total_followers": total_followers,
        "top_posts": top_posts[:10],
        "observations": [
            {
                "id": o.id,
                "category": o.category,
                "statement": o.statement,
                "confidence": o.confidence,
                "sample_size": o.sample_size,
            }
            for o in observations
        ],
        "hypotheses": [
            {
                "id": h.id,
                "category": h.category,
                "statement": h.statement,
                "confidence": h.confidence,
            }
            for h in hypotheses
        ],
    }


@router.get("/posts-with-metrics")
async def posts_with_metrics(
    account_id: int | None = None,
    creator_id: int = Depends(get_creator_id),
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Post, PostMetric, PlatformAccount.platform, PlatformAccount.username)
        .join(PostMetric)
        .join(PlatformAccount)
        .where(PlatformAccount.creator_id == creator_id)
    )
    if account_id:
        query = query.where(Post.account_id == account_id)
    query = query.order_by(Post.published_at.desc().nulls_last()).offset(offset).limit(limit)

    result = await db.execute(query)
    rows = []
    for post, metric, platform, username in result:
        rows.append({
            "id": post.id,
            "platform": platform.value,
            "username": username,
            "post_type": post.post_type.value if post.post_type else None,
            "caption": post.caption,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "thumbnail_url": post.thumbnail_url,
            "media_url": post.media_url,
            "reach": metric.reach,
            "views": metric.views,
            "likes": metric.likes,
            "saves": metric.saves,
            "shares": metric.shares,
            "comments": metric.comments_count,
            "followers_from_post": metric.followers_from_post,
            "profile_visits": metric.profile_visits_from_post,
            "avg_watch_time": metric.avg_watch_time_seconds,
        })
    return rows


@router.get("/content-themes")
async def content_themes(creator_id: int = Depends(get_creator_id), db: AsyncSession = Depends(get_db)):
    """Return content cluster performance for the content winners card."""
    memories = (
        await db.scalars(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.is_active == True,
                ManagerMemory.category.like("content_cluster%"),
            ).order_by(ManagerMemory.updated_at.desc())
        )
    ).all()

    themes = []
    for m in memories:
        metrics = m.metrics_considered or {}
        vs_median = None
        if isinstance(metrics, dict):
            vs_median = metrics.get("vs_median") or metrics.get("vs_median_likes") or metrics.get("vs_median_views")
        import re
        if vs_median is None:
            match = re.search(r"(\d+\.?\d*)x\b", m.statement)
            if match:
                vs_median = float(match.group(1))
        themes.append({
            "category": m.category.replace("content_clustering", "").replace("content_cluster_", "").strip("_: ") or m.category,
            "statement": m.statement,
            "vs_median": vs_median,
            "sample_size": m.sample_size,
            "confidence": m.confidence,
        })
    themes.sort(key=lambda t: (t["vs_median"] or 0), reverse=True)
    return themes


@router.get("/performance-timeline")
async def performance_timeline(
    account_id: int | None = None,
    creator_id: int = Depends(get_creator_id),
    db: AsyncSession = Depends(get_db),
):
    """Monthly aggregated performance for the chart."""
    query = (
        select(
            func.date_trunc("month", Post.published_at).label("month"),
            PlatformAccount.platform,
            func.count(Post.id).label("posts"),
            func.avg(PostMetric.reach).label("avg_reach"),
            func.avg(PostMetric.views).label("avg_views"),
            func.avg(PostMetric.likes).label("avg_likes"),
            func.sum(PostMetric.reach).label("total_reach"),
            func.sum(PostMetric.views).label("total_views"),
        )
        .join(PostMetric, PostMetric.post_id == Post.id)
        .join(PlatformAccount, PlatformAccount.id == Post.account_id)
        .where(PlatformAccount.creator_id == creator_id)
    )
    if account_id:
        query = query.where(Post.account_id == account_id)
    query = query.group_by("month", PlatformAccount.platform).order_by("month")

    result = await db.execute(query)
    timeline = []
    for row in result:
        timeline.append({
            "month": row.month.isoformat() if row.month else None,
            "platform": row.platform.value,
            "posts": row.posts,
            "avg_reach": round(float(row.avg_reach), 1) if row.avg_reach else None,
            "avg_views": round(float(row.avg_views), 1) if row.avg_views else None,
            "avg_likes": round(float(row.avg_likes), 1) if row.avg_likes else None,
            "total_reach": int(row.total_reach) if row.total_reach else None,
            "total_views": int(row.total_views) if row.total_views else None,
        })
    return timeline
