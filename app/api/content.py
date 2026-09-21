"""Content management endpoints — ideas, calendar, series, hooks."""
from datetime import date
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.content import ContentIdea, ContentCalendar, ContentSeries, Hook

router = APIRouter()


@router.get("/ideas")
async def list_ideas(
    creator_id: int = 1,
    status: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(ContentIdea).where(ContentIdea.creator_id == creator_id)
    if status:
        query = query.where(ContentIdea.status == status)
    query = query.order_by(ContentIdea.ai_score.desc().nulls_last()).limit(limit)
    result = await db.execute(query)
    ideas = result.scalars().all()
    return [
        {
            "id": i.id,
            "title": i.title,
            "concept": i.concept,
            "why": i.why,
            "objective": i.objective.value if i.objective else None,
            "status": i.status.value,
            "ai_score": i.ai_score,
            "suggested_hook": i.suggested_hook,
        }
        for i in ideas
    ]


@router.post("/ideas/generate")
async def generate_ideas(creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Ask the Content Agent to generate new content ideas based on data."""
    from app.agents.content import ContentAgent
    agent = ContentAgent(creator_id)
    result = await agent.run(
        "Generate 5 content ideas for this week based on historical performance, "
        "audience data, current trends, and content gaps. Each idea needs: title, concept, "
        "why (data-driven reasoning), objective, suggested hook, estimated duration, "
        "and target platform.",
    )
    return result


@router.get("/calendar")
async def get_calendar(
    creator_id: int = 1,
    start: date | None = None,
    end: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(ContentCalendar).where(ContentCalendar.creator_id == creator_id)
    if start:
        query = query.where(ContentCalendar.date >= start)
    if end:
        query = query.where(ContentCalendar.date <= end)
    query = query.order_by(ContentCalendar.date)
    result = await db.execute(query)
    entries = result.scalars().all()
    return [
        {
            "id": e.id,
            "date": e.date.isoformat(),
            "slot": e.slot,
            "idea_id": e.idea_id,
            "platform": e.platform.value if e.platform else None,
            "objective": e.objective.value if e.objective else None,
            "notes": e.notes,
            "suggested_time": e.suggested_time,
            "is_rest_day": e.is_rest_day,
        }
        for e in entries
    ]


@router.get("/series")
async def list_series(creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ContentSeries)
        .where(ContentSeries.creator_id == creator_id)
        .order_by(ContentSeries.created_at.desc())
    )
    series = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "status": s.status,
            "episode_count": s.episode_count,
            "avg_performance_vs_median": s.avg_performance_vs_median,
            "momentum": s.momentum,
        }
        for s in series
    ]


@router.get("/hooks")
async def list_hooks(creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Hook)
        .where(Hook.creator_id == creator_id)
        .order_by(Hook.performance_vs_median.desc().nulls_last())
    )
    hooks = result.scalars().all()
    return [
        {
            "id": h.id,
            "text": h.text,
            "hook_type": h.hook_type,
            "retention_1s": h.retention_1s,
            "retention_3s": h.retention_3s,
            "performance_vs_median": h.performance_vs_median,
        }
        for h in hooks
    ]
