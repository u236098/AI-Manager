"""Intelligence models: competitors, trends, research."""
from datetime import datetime
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime,
    Enum, ForeignKey, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from app.models.core import Platform


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    platform: Mapped[Platform] = mapped_column(Enum(Platform))
    username: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str | None] = mapped_column(String(300))
    follower_count: Mapped[int | None] = mapped_column(Integer)
    niche: Mapped[str | None] = mapped_column(String(200))
    relevance_score: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list["CompetitorPost"]] = relationship(back_populates="competitor")


class CompetitorPost(Base):
    __tablename__ = "competitor_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id"))
    platform_post_id: Mapped[str | None] = mapped_column(String(200))
    post_type: Mapped[str | None] = mapped_column(String(50))
    caption: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    views: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments_count: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)

    median_views_at_capture: Mapped[int | None] = mapped_column(Integer)
    outlier_ratio: Mapped[float | None] = mapped_column(Float)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)
    outlier_analysis: Mapped[str | None] = mapped_column(Text)

    format_tags: Mapped[list | None] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    competitor: Mapped["Competitor"] = relationship(back_populates="posts")

    __table_args__ = (
        Index("ix_competitor_posts_outlier", "competitor_id", "is_outlier"),
    )


class Trend(Base):
    __tablename__ = "trends"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    platform: Mapped[Platform | None] = mapped_column(Enum(Platform))
    trend_type: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)

    momentum: Mapped[float | None] = mapped_column(Float)
    kobby_fit: Mapped[float | None] = mapped_column(Float)
    audience_fit: Mapped[float | None] = mapped_column(Float)
    originality_potential: Mapped[float | None] = mapped_column(Float)
    difficulty: Mapped[float | None] = mapped_column(Float)
    shelf_life_days: Mapped[int | None] = mapped_column(Integer)

    recommendation: Mapped[str | None] = mapped_column(String(50))
    reasoning: Mapped[str | None] = mapped_column(Text)

    source_url: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_trends_creator_rec", "creator_id", "recommendation"),
    )


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    trend_id: Mapped[int] = mapped_column(ForeignKey("trends.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    momentum: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict | None] = mapped_column(JSON)
