"""Manager models: memory, recommendations, briefings, reviews, reputation."""
import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, Date, DateTime,
    Enum, ForeignKey, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class KnowledgeType(str, enum.Enum):
    FACT = "fact"
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"


class ManagerMemory(Base):
    """Lessons the AI manager has learned — its persistent playbook."""
    __tablename__ = "manager_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    knowledge_type: Mapped[KnowledgeType] = mapped_column(Enum(KnowledgeType))
    category: Mapped[str] = mapped_column(String(100))
    statement: Mapped[str] = mapped_column(Text)
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    evidence_post_ids: Mapped[list | None] = mapped_column(JSON)
    contradicting_post_ids: Mapped[list | None] = mapped_column(JSON)
    metrics_considered: Mapped[list | None] = mapped_column(JSON)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    superseded_by_id: Mapped[int | None] = mapped_column(ForeignKey("manager_memory.id"))
    promoted_from_id: Mapped[int | None] = mapped_column(ForeignKey("manager_memory.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_memory_creator_category", "creator_id", "category"),
        Index("ix_memory_active", "creator_id", "is_active"),
        Index("ix_memory_knowledge_type", "creator_id", "knowledge_type"),
    )


class Recommendation(Base):
    """Every recommendation the manager makes — scored later against outcomes.

    Full provenance: what was recommended, why, from what evidence, with what
    confidence, and whether it actually worked.
    """
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    agent: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    reasoning: Mapped[str | None] = mapped_column(Text)

    evidence_post_ids: Mapped[list | None] = mapped_column(JSON)
    evidence_memory_ids: Mapped[list | None] = mapped_column(JSON)
    metrics_considered: Mapped[list | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    priority: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(50), default="pending")
    user_decision: Mapped[str | None] = mapped_column(String(50))
    user_feedback: Mapped[str | None] = mapped_column(Text)

    outcome_window_days: Mapped[int | None] = mapped_column(Integer, default=7)
    outcome_measured: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome_metrics: Mapped[dict | None] = mapped_column(JSON)
    outcome_baseline_metrics: Mapped[dict | None] = mapped_column(JSON)
    outcome_verdict: Mapped[str | None] = mapped_column(String(50))
    outcome_explanation: Mapped[str | None] = mapped_column(Text)
    manager_score: Mapped[float | None] = mapped_column(Float)

    related_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    resulting_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    related_experiment_id: Mapped[int | None] = mapped_column(ForeignKey("experiments.id"))
    memory_created_id: Mapped[int | None] = mapped_column(ForeignKey("manager_memory.id"))
    manager_decision_id: Mapped[int | None] = mapped_column(ForeignKey("manager_decisions.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_recommendations_status", "creator_id", "status"),
        Index("ix_recommendations_outcome", "outcome_verdict"),
        Index("ix_recommendations_due", "outcome_due_at", "outcome_measured"),
    )


class DailyBrief(Base):
    __tablename__ = "daily_briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    date: Mapped[date] = mapped_column(Date)

    account_status: Mapped[str | None] = mapped_column(String(50))
    summary: Mapped[str | None] = mapped_column(Text)
    key_observation: Mapped[str | None] = mapped_column(Text)
    actions: Mapped[list | None] = mapped_column(JSON)
    warnings: Mapped[list | None] = mapped_column(JSON)
    opportunities: Mapped[list | None] = mapped_column(JSON)
    full_brief: Mapped[str | None] = mapped_column(Text)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_briefs_date", "creator_id", "date"),
    )


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    week_start: Mapped[date] = mapped_column(Date)

    what_worked: Mapped[list | None] = mapped_column(JSON)
    what_failed: Mapped[list | None] = mapped_column(JSON)
    why_analysis: Mapped[str | None] = mapped_column(Text)
    audience_changes: Mapped[str | None] = mapped_column(Text)
    competitor_changes: Mapped[str | None] = mapped_column(Text)
    brand_health: Mapped[str | None] = mapped_column(Text)
    experiment_results: Mapped[list | None] = mapped_column(JSON)
    series_performance: Mapped[list | None] = mapped_column(JSON)
    growth_summary: Mapped[str | None] = mapped_column(Text)

    stop: Mapped[list | None] = mapped_column(JSON)
    start: Mapped[list | None] = mapped_column(JSON)
    continue_doing: Mapped[list | None] = mapped_column(JSON)

    next_week_strategy: Mapped[str | None] = mapped_column(Text)
    next_week_calendar: Mapped[list | None] = mapped_column(JSON)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MonthlyReview(Base):
    __tablename__ = "monthly_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    month: Mapped[date] = mapped_column(Date)

    growth_assessment: Mapped[str | None] = mapped_column(Text)
    audience_quality: Mapped[str | None] = mapped_column(Text)
    brand_recognition: Mapped[str | None] = mapped_column(Text)
    platform_comparison: Mapped[str | None] = mapped_column(Text)
    niche_balance: Mapped[str | None] = mapped_column(Text)
    sentiment_analysis: Mapped[str | None] = mapped_column(Text)
    monetisation_readiness: Mapped[str | None] = mapped_column(Text)
    collaboration_review: Mapped[str | None] = mapped_column(Text)
    positioning_changes: Mapped[str | None] = mapped_column(Text)
    strategic_recommendations: Mapped[list | None] = mapped_column(JSON)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReputationFlag(Base):
    """Warnings about content that could harm the brand."""
    __tablename__ = "reputation_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    related_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    flag_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)
    was_heeded: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AutonomyLevel(str, enum.Enum):
    ADVISER = "adviser"
    COPILOT = "copilot"
    MANAGER = "manager"
    LIMITED_AUTOPILOT = "limited_autopilot"


class ManagerDecision(Base):
    """Record of every orchestrated decision the Manager makes."""
    __tablename__ = "manager_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    decision_type: Mapped[str] = mapped_column(String(100))
    request_context: Mapped[str | None] = mapped_column(Text)

    agents_consulted: Mapped[list | None] = mapped_column(JSON)
    agent_outputs: Mapped[dict | None] = mapped_column(JSON)
    conflicts_detected: Mapped[list | None] = mapped_column(JSON)

    final_decision: Mapped[str] = mapped_column(Text)
    final_reasoning: Mapped[str | None] = mapped_column(Text)

    evidence_post_ids: Mapped[list | None] = mapped_column(JSON)
    evidence_memory_ids: Mapped[list | None] = mapped_column(JSON)
    metrics_considered: Mapped[list | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_decisions_creator_type", "creator_id", "decision_type"),
    )


class ManagerConfig(Base):
    __tablename__ = "manager_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), unique=True)
    autonomy_level: Mapped[AutonomyLevel] = mapped_column(
        Enum(AutonomyLevel), default=AutonomyLevel.ADVISER
    )
    auto_approve_reads: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_approve_analytics: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_approve_drafts: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_approve_profile_changes: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_approve_posts: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_approve_deletes: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
