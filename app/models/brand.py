"""Brand models: strategy, positioning, profile management, identity."""
from datetime import datetime
from sqlalchemy import (
    String, Text, Float, DateTime, ForeignKey, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class BrandStrategy(Base):
    """Living positioning document — updated as the manager learns."""
    __tablename__ = "brand_strategies"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), unique=True)

    primary_identity: Mapped[str | None] = mapped_column(String(300))
    supporting_identities: Mapped[list | None] = mapped_column(JSON)
    personality_traits: Mapped[list | None] = mapped_column(JSON)
    brand_goal: Mapped[str | None] = mapped_column(Text)

    audience_primary_age: Mapped[str | None] = mapped_column(String(50))
    audience_primary_interests: Mapped[list | None] = mapped_column(JSON)
    audience_primary_geography: Mapped[list | None] = mapped_column(JSON)

    private_topics: Mapped[list | None] = mapped_column(JSON)
    style_boundaries: Mapped[list | None] = mapped_column(JSON)
    sponsorship_exclusions: Mapped[list | None] = mapped_column(JSON)

    current_phase: Mapped[str | None] = mapped_column(String(100))
    strategic_priorities: Mapped[list | None] = mapped_column(JSON)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator: Mapped["Creator"] = relationship(back_populates="brand_strategy")


class ProfileScore(Base):
    """Periodic scoring of profile quality across dimensions."""
    __tablename__ = "profile_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"))
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recognition: Mapped[float | None] = mapped_column(Float)
    niche_clarity: Mapped[float | None] = mapped_column(Float)
    follow_proposition: Mapped[float | None] = mapped_column(Float)
    cross_platform_consistency: Mapped[float | None] = mapped_column(Float)
    social_proof: Mapped[float | None] = mapped_column(Float)
    pinned_content_quality: Mapped[float | None] = mapped_column(Float)
    grid_quality: Mapped[float | None] = mapped_column(Float)
    overall: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_profile_scores_account", "account_id", "scored_at"),
    )


class ProfileExperiment(Base):
    """A/B tests on bio, profile pic, pinned posts, etc."""
    __tablename__ = "profile_experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"))
    element: Mapped[str] = mapped_column(String(100))
    before_value: Mapped[str | None] = mapped_column(Text)
    after_value: Mapped[str | None] = mapped_column(Text)
    before_conversion_rate: Mapped[float | None] = mapped_column(Float)
    after_conversion_rate: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conclusion: Mapped[str | None] = mapped_column(Text)
    kept_change: Mapped[bool | None] = mapped_column()


class PinRecommendation(Base):
    __tablename__ = "pin_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"))
    recommended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    slot_1_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    slot_1_purpose: Mapped[str | None] = mapped_column(String(100))
    slot_2_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    slot_2_purpose: Mapped[str | None] = mapped_column(String(100))
    slot_3_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    slot_3_purpose: Mapped[str | None] = mapped_column(String(100))

    reasoning: Mapped[str | None] = mapped_column(Text)
    was_applied: Mapped[bool | None] = mapped_column()
