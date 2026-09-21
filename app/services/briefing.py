"""Briefing context gathering — deterministic data assembly for daily/weekly briefs."""
from __future__ import annotations
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.core import Post, PlatformAccount, AccountMetricSnapshot
from app.models.content import ContentCalendar
from app.models.manager import Recommendation, ManagerMemory
from app.models.brand import BrandStrategy


async def gather_brief_context(creator_id: int, db: AsyncSession) -> dict:
    today = date.today()
    week_ago = today - timedelta(days=7)

    accounts_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.creator_id == creator_id,
            PlatformAccount.is_active == True,
        )
    )
    accounts = accounts_result.scalars().all()

    recent_metrics = {}
    for account in accounts:
        metrics_result = await db.execute(
            select(AccountMetricSnapshot)
            .where(
                AccountMetricSnapshot.account_id == account.id,
                AccountMetricSnapshot.date >= week_ago,
            )
            .order_by(AccountMetricSnapshot.date.desc())
        )
        recent_metrics[account.username] = [
            {
                "date": m.date.isoformat(),
                "followers": m.followers,
                "followers_delta": m.followers_delta,
                "total_reach": m.total_reach,
                "profile_to_follow_rate": m.profile_to_follow_rate,
            }
            for m in metrics_result.scalars().all()
        ]

    recent_posts_result = await db.execute(
        select(Post)
        .join(PlatformAccount)
        .where(PlatformAccount.creator_id == creator_id)
        .order_by(Post.published_at.desc())
        .limit(10)
    )
    recent_posts = [
        {
            "id": p.id,
            "objective": p.objective.value if p.objective else None,
            "caption": (p.caption or "")[:100],
            "published_at": p.published_at.isoformat() if p.published_at else None,
        }
        for p in recent_posts_result.scalars().all()
    ]

    calendar_result = await db.execute(
        select(ContentCalendar)
        .where(ContentCalendar.creator_id == creator_id, ContentCalendar.date == today)
    )
    todays_calendar = [
        {"slot": c.slot, "objective": c.objective.value if c.objective else None, "notes": c.notes}
        for c in calendar_result.scalars().all()
    ]

    pending_recs_result = await db.execute(
        select(Recommendation)
        .where(Recommendation.creator_id == creator_id, Recommendation.status == "pending")
        .order_by(Recommendation.priority.asc().nulls_last())
        .limit(10)
    )
    pending_recs = [
        {"summary": r.summary, "category": r.category, "agent": r.agent}
        for r in pending_recs_result.scalars().all()
    ]

    strategy_result = await db.execute(
        select(BrandStrategy).where(BrandStrategy.creator_id == creator_id)
    )
    strategy = strategy_result.scalar_one_or_none()

    memories_result = await db.execute(
        select(ManagerMemory)
        .where(ManagerMemory.creator_id == creator_id, ManagerMemory.is_active == True)
        .order_by(ManagerMemory.updated_at.desc())
        .limit(20)
    )
    active_memories = [
        {
            "knowledge_type": m.knowledge_type.value,
            "category": m.category,
            "statement": m.statement,
            "confidence": m.confidence,
            "sample_size": m.sample_size,
        }
        for m in memories_result.scalars().all()
    ]

    return {
        "today": today.isoformat(),
        "account_metrics": recent_metrics,
        "recent_posts": recent_posts,
        "todays_calendar": todays_calendar,
        "pending_recommendations": pending_recs,
        "brand_strategy": {
            "primary_identity": strategy.primary_identity,
            "brand_goal": strategy.brand_goal,
            "strategic_priorities": strategy.strategic_priorities,
        } if strategy else None,
        "active_memories": active_memories,
    }
