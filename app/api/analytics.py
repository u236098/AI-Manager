"""Analytics endpoints — metrics, experiments, posting time analysis."""
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_creator_id
from app.models.core import AccountMetricSnapshot, PostMetric
from app.models.analytics import Experiment, PostingTimeAnalysis

router = APIRouter()


@router.get("/account/{account_id}/metrics")
async def account_metrics(
    account_id: int,
    start: date | None = None,
    end: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(AccountMetricSnapshot)
        .where(AccountMetricSnapshot.account_id == account_id)
        .order_by(AccountMetricSnapshot.date.desc())
    )
    if start:
        query = query.where(AccountMetricSnapshot.date >= start)
    if end:
        query = query.where(AccountMetricSnapshot.date <= end)
    result = await db.execute(query.limit(90))
    snapshots = result.scalars().all()
    return [
        {
            "date": s.date.isoformat(),
            "followers": s.followers,
            "followers_delta": s.followers_delta,
            "total_reach": s.total_reach,
            "profile_visits": s.profile_visits,
            "profile_to_follow_rate": s.profile_to_follow_rate,
        }
        for s in snapshots
    ]


@router.get("/post/{post_id}/metrics")
async def post_metrics(post_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PostMetric)
        .where(PostMetric.post_id == post_id)
        .order_by(PostMetric.captured_at)
    )
    metrics = result.scalars().all()
    return [
        {
            "captured_at": m.captured_at.isoformat(),
            "hours_after_publish": m.hours_after_publish,
            "views": m.views,
            "likes": m.likes,
            "comments_count": m.comments_count,
            "shares": m.shares,
            "saves": m.saves,
            "reach": m.reach,
            "followers_from_post": m.followers_from_post,
            "retention_rate": m.retention_rate,
        }
        for m in metrics
    ]


@router.get("/experiments")
async def list_experiments(creator_id: int = Depends(get_creator_id), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Experiment)
        .where(Experiment.creator_id == creator_id)
        .order_by(Experiment.created_at.desc())
    )
    experiments = result.scalars().all()
    return [
        {
            "id": e.id,
            "question": e.question,
            "status": e.status.value,
            "conclusion": e.conclusion,
            "confidence": e.confidence,
            "sample_size": e.sample_size,
        }
        for e in experiments
    ]


@router.get("/posting-times/{account_id}")
async def posting_time_analysis(account_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PostingTimeAnalysis).where(PostingTimeAnalysis.account_id == account_id)
    )
    analysis = result.scalars().all()
    return [
        {
            "day_of_week": a.day_of_week,
            "hour": a.hour,
            "sample_size": a.sample_size,
            "median_reach": a.median_reach,
            "median_engagement": a.median_engagement,
            "time_matters_score": a.time_matters_score,
        }
        for a in analysis
    ]
