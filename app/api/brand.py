"""Brand management endpoints — strategy, profile scores, experiments."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_creator_id
from app.models.brand import BrandStrategy, ProfileScore, ProfileExperiment, PinRecommendation
from app.models.core import PlatformAccount

router = APIRouter()


@router.get("/strategy")
async def get_strategy(creator_id: int = Depends(get_creator_id), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BrandStrategy).where(BrandStrategy.creator_id == creator_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        return {"message": "No brand strategy configured yet."}
    return {
        "primary_identity": strategy.primary_identity,
        "supporting_identities": strategy.supporting_identities,
        "personality_traits": strategy.personality_traits,
        "brand_goal": strategy.brand_goal,
        "audience_primary_age": strategy.audience_primary_age,
        "audience_primary_interests": strategy.audience_primary_interests,
        "private_topics": strategy.private_topics,
        "style_boundaries": strategy.style_boundaries,
        "current_phase": strategy.current_phase,
        "strategic_priorities": strategy.strategic_priorities,
    }


@router.get("/profile-scores/{account_id}")
async def profile_scores(
    account_id: int,
    creator_id: int = Depends(get_creator_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProfileScore)
        .join(PlatformAccount, PlatformAccount.id == ProfileScore.account_id)
        .where(
            ProfileScore.account_id == account_id,
            PlatformAccount.creator_id == creator_id,
        )
        .order_by(ProfileScore.scored_at.desc())
        .limit(10)
    )
    scores = result.scalars().all()
    return [
        {
            "scored_at": s.scored_at.isoformat(),
            "recognition": s.recognition,
            "niche_clarity": s.niche_clarity,
            "follow_proposition": s.follow_proposition,
            "cross_platform_consistency": s.cross_platform_consistency,
            "social_proof": s.social_proof,
            "pinned_content_quality": s.pinned_content_quality,
            "grid_quality": s.grid_quality,
            "overall": s.overall,
        }
        for s in scores
    ]


@router.get("/pin-recommendations/{account_id}")
async def pin_recommendations(
    account_id: int,
    creator_id: int = Depends(get_creator_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PinRecommendation)
        .join(PlatformAccount, PlatformAccount.id == PinRecommendation.account_id)
        .where(
            PinRecommendation.account_id == account_id,
            PlatformAccount.creator_id == creator_id,
        )
        .order_by(PinRecommendation.recommended_at.desc())
        .limit(5)
    )
    recs = result.scalars().all()
    return [
        {
            "recommended_at": r.recommended_at.isoformat(),
            "slot_1_post_id": r.slot_1_post_id,
            "slot_1_purpose": r.slot_1_purpose,
            "slot_2_post_id": r.slot_2_post_id,
            "slot_2_purpose": r.slot_2_purpose,
            "slot_3_post_id": r.slot_3_post_id,
            "slot_3_purpose": r.slot_3_purpose,
            "reasoning": r.reasoning,
        }
        for r in recs
    ]
