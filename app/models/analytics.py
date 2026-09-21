"""Analytics models: experiments, posting time analysis, growth loops."""
import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, Date, DateTime,
    Enum, ForeignKey, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class ExperimentStatus(str, enum.Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    question: Mapped[str] = mapped_column(Text)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ExperimentStatus] = mapped_column(Enum(ExperimentStatus), default=ExperimentStatus.PLANNED)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conclusion: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(String(50))
    confounders: Mapped[str | None] = mapped_column(Text)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    variants: Mapped[list["ExperimentVariant"]] = relationship(back_populates="experiment")


class ExperimentVariant(Base):
    __tablename__ = "experiment_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"))
    label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    post_ids: Mapped[list | None] = mapped_column(JSON)
    metrics_summary: Mapped[dict | None] = mapped_column(JSON)
    is_winner: Mapped[bool | None] = mapped_column(Boolean)

    experiment: Mapped["Experiment"] = relationship(back_populates="variants")


class PostingTimeAnalysis(Base):
    """Aggregated posting time performance."""
    __tablename__ = "posting_time_analysis"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"))
    day_of_week: Mapped[int] = mapped_column(Integer)
    hour: Mapped[int] = mapped_column(Integer)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    median_reach: Mapped[float | None] = mapped_column(Float)
    median_initial_velocity: Mapped[float | None] = mapped_column(Float)
    median_retention: Mapped[float | None] = mapped_column(Float)
    median_engagement: Mapped[float | None] = mapped_column(Float)
    median_follow_conversion: Mapped[float | None] = mapped_column(Float)
    time_matters_score: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GrowthLoop(Base):
    """Tracks growth loops triggered by breakout content."""
    __tablename__ = "growth_loops"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    trigger_post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    identified_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="active")

    actions: Mapped[list | None] = mapped_column(JSON)
    follow_up_post_ids: Mapped[list | None] = mapped_column(JSON)
    total_followers_gained: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ObjectivePortfolio(Base):
    """Tracks the current and target mix of content objectives."""
    __tablename__ = "objective_portfolios"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    target_mix: Mapped[dict] = mapped_column(JSON)
    actual_mix: Mapped[dict | None] = mapped_column(JSON)
    deviation_notes: Mapped[str | None] = mapped_column(Text)
