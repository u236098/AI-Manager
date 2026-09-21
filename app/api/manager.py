"""Manager endpoints — daily briefs, weekly reviews, chat, recommendations."""
from datetime import date
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.manager import (
    DailyBrief, WeeklyReview, Recommendation, ManagerMemory, ManagerConfig,
)

router = APIRouter()


@router.get("/brief/today")
async def todays_brief(creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Get or generate today's daily brief."""
    today = date.today()
    result = await db.execute(
        select(DailyBrief)
        .where(DailyBrief.creator_id == creator_id, DailyBrief.date == today)
    )
    brief = result.scalar_one_or_none()
    if brief:
        return {
            "date": brief.date.isoformat(),
            "account_status": brief.account_status,
            "summary": brief.summary,
            "key_observation": brief.key_observation,
            "actions": brief.actions,
            "warnings": brief.warnings,
            "opportunities": brief.opportunities,
            "full_brief": brief.full_brief,
        }

    from app.services.briefing import generate_daily_brief
    return await generate_daily_brief(creator_id, db)


@router.get("/brief/weekly")
async def latest_weekly_review(creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WeeklyReview)
        .where(WeeklyReview.creator_id == creator_id)
        .order_by(WeeklyReview.week_start.desc())
        .limit(1)
    )
    review = result.scalar_one_or_none()
    if not review:
        return {"message": "No weekly review yet."}
    return {
        "week_start": review.week_start.isoformat(),
        "what_worked": review.what_worked,
        "what_failed": review.what_failed,
        "stop": review.stop,
        "start": review.start,
        "continue_doing": review.continue_doing,
        "next_week_strategy": review.next_week_strategy,
    }


class ChatMessage(BaseModel):
    message: str


@router.post("/chat")
async def chat_with_manager(body: ChatMessage, creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Free-form conversation with the AI manager — routed through orchestration."""
    from app.services.orchestrator import orchestrate
    from app.services.briefing import _gather_brief_context
    context = await _gather_brief_context(creator_id, db)
    return await orchestrate(body.message, context, db, creator_id)


@router.post("/analyze")
async def run_analysis(creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Run the full analysis loop: analyze performance → create observations → recommend."""
    from app.services.analysis import run_analysis_loop
    return await run_analysis_loop(creator_id, db)


@router.post("/analyze/full/{account_id}")
async def run_full_analysis(account_id: int, db: AsyncSession = Depends(get_db)):
    """Comprehensive first-run analytics for a real account with outlier detection."""
    from app.services.analysis import run_full_analytics
    return await run_full_analytics(account_id, db)


@router.post("/analyze/instagram/{account_id}")
async def run_ig_analysis(account_id: int, db: AsyncSession = Depends(get_db)):
    """Instagram analytics — format-segmented, likes-based."""
    from app.services.analysis import run_ig_analytics
    return await run_ig_analytics(account_id, db)


@router.post("/analyze/cross-platform")
async def run_cross_platform(creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    """Cross-platform content theme comparison."""
    from app.services.analysis import run_cross_platform_analysis
    return await run_cross_platform_analysis(creator_id, db)


@router.get("/recommendations")
async def list_recommendations(
    creator_id: int = 1,
    status: str = "pending",
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Recommendation)
        .where(Recommendation.creator_id == creator_id, Recommendation.status == status)
        .order_by(Recommendation.priority.asc().nulls_last())
    )
    recs = result.scalars().all()
    return [
        {
            "id": r.id,
            "agent": r.agent,
            "category": r.category,
            "summary": r.summary,
            "detail": r.detail,
            "reasoning": r.reasoning,
            "evidence_post_ids": r.evidence_post_ids,
            "evidence_memory_ids": r.evidence_memory_ids,
            "metrics_considered": r.metrics_considered,
            "confidence": r.confidence,
            "priority": r.priority,
            "status": r.status,
            "outcome_window_days": r.outcome_window_days,
            "outcome_verdict": r.outcome_verdict,
            "outcome_explanation": r.outcome_explanation,
            "manager_score": r.manager_score,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recs
    ]


class RecommendationDecision(BaseModel):
    decision: str
    feedback: str | None = None


@router.post("/recommendations/{rec_id}/decide")
async def decide_recommendation(
    rec_id: int,
    body: RecommendationDecision,
    db: AsyncSession = Depends(get_db),
):
    rec = await db.get(Recommendation, rec_id)
    if not rec:
        from fastapi import HTTPException
        raise HTTPException(404, "Recommendation not found")
    rec.user_decision = body.decision
    rec.user_feedback = body.feedback
    rec.status = "accepted" if body.decision == "approve" else "rejected"
    await db.commit()
    return {"status": rec.status}


class ScoreOutcome(BaseModel):
    outcome_metrics: dict
    baseline_metrics: dict
    objective: str | None = None


@router.post("/recommendations/{rec_id}/score")
async def score_recommendation_endpoint(
    rec_id: int,
    body: ScoreOutcome,
    db: AsyncSession = Depends(get_db),
):
    """Score a recommendation against actual outcome data."""
    from app.services.analysis import score_recommendation
    rec = await score_recommendation(
        rec_id, db, body.outcome_metrics, body.baseline_metrics, body.objective,
    )
    await db.commit()
    return {
        "id": rec.id,
        "outcome_verdict": rec.outcome_verdict,
        "manager_score": rec.manager_score,
        "outcome_explanation": rec.outcome_explanation,
    }


@router.get("/memory")
async def list_memories(creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManagerMemory)
        .where(ManagerMemory.creator_id == creator_id, ManagerMemory.is_active == True)
        .order_by(ManagerMemory.updated_at.desc())
    )
    memories = result.scalars().all()
    return [
        {
            "id": m.id,
            "knowledge_type": m.knowledge_type.value,
            "category": m.category,
            "statement": m.statement,
            "evidence_post_ids": m.evidence_post_ids,
            "metrics_considered": m.metrics_considered,
            "sample_size": m.sample_size,
            "confidence": m.confidence,
            "updated_at": m.updated_at.isoformat(),
        }
        for m in memories
    ]


@router.get("/config")
async def get_config(creator_id: int = 1, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManagerConfig).where(ManagerConfig.creator_id == creator_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return {"autonomy_level": "adviser"}
    return {
        "autonomy_level": config.autonomy_level.value,
        "auto_approve_reads": config.auto_approve_reads,
        "auto_approve_analytics": config.auto_approve_analytics,
        "auto_approve_drafts": config.auto_approve_drafts,
        "auto_approve_profile_changes": config.auto_approve_profile_changes,
        "auto_approve_posts": config.auto_approve_posts,
    }
