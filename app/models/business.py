"""Business models: sponsorships, revenue, opportunities, monetisation."""
import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, Date, DateTime,
    Enum, ForeignKey, Index, JSON, Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class SponsorshipStatus(str, enum.Enum):
    INQUIRY = "inquiry"
    EVALUATING = "evaluating"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    PAID = "paid"


class Sponsorship(Base):
    __tablename__ = "sponsorships"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    brand_name: Mapped[str] = mapped_column(String(300))
    contact_info: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SponsorshipStatus] = mapped_column(Enum(SponsorshipStatus), default=SponsorshipStatus.INQUIRY)

    offered_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str | None] = mapped_column(String(10))
    counter_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    final_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))

    deliverables: Mapped[str | None] = mapped_column(Text)
    usage_rights: Mapped[str | None] = mapped_column(Text)
    exclusivity: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[date | None] = mapped_column(Date)

    brand_fit_score: Mapped[float | None] = mapped_column(Float)
    audience_fit_score: Mapped[float | None] = mapped_column(Float)
    reputation_risk: Mapped[float | None] = mapped_column(Float)
    ai_recommendation: Mapped[str | None] = mapped_column(Text)
    ai_reasoning: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_sponsorships_creator_status", "creator_id", "status"),
    )


class Revenue(Base):
    __tablename__ = "revenue"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(10), default="EUR")
    description: Mapped[str | None] = mapped_column(Text)
    sponsorship_id: Mapped[int | None] = mapped_column(ForeignKey("sponsorships.id"))


class MonetisationReadiness(Base):
    """Periodic assessment of readiness for various revenue streams."""
    __tablename__ = "monetisation_readiness"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    affiliate_readiness: Mapped[float | None] = mapped_column(Float)
    sponsorship_readiness: Mapped[float | None] = mapped_column(Float)
    digital_product_readiness: Mapped[float | None] = mapped_column(Float)
    coaching_readiness: Mapped[float | None] = mapped_column(Float)
    youtube_readiness: Mapped[float | None] = mapped_column(Float)
    community_readiness: Mapped[float | None] = mapped_column(Float)

    recommended_next_stream: Mapped[str | None] = mapped_column(String(200))
    reasoning: Mapped[str | None] = mapped_column(Text)
    premature_warning: Mapped[bool] = mapped_column(Boolean, default=False)


class Opportunity(Base):
    """External opportunities beyond social media."""
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    type: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(200))
    deadline: Mapped[date | None] = mapped_column(Date)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    ai_recommendation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
