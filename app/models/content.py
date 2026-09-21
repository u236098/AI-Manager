"""Content models: ideas, calendar, series, hooks, transcripts, visual features, drafts."""
import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, Date, DateTime,
    Enum, ForeignKey, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from app.models.core import PostObjective, Platform


class IdeaStatus(str, enum.Enum):
    BACKLOG = "backlog"
    RESEARCHING = "researching"
    SCORED = "scored"
    APPROVED = "approved"
    SCRIPTED = "scripted"
    FILMING = "filming"
    EDITING = "editing"
    READY = "ready"
    PUBLISHED = "published"
    KILLED = "killed"


class ContentIdea(Base):
    """Full content pipeline — idea through to published post."""
    __tablename__ = "content_ideas"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    status: Mapped[IdeaStatus] = mapped_column(Enum(IdeaStatus), default=IdeaStatus.BACKLOG)

    title: Mapped[str] = mapped_column(String(500))
    concept: Mapped[str | None] = mapped_column(Text)
    why: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[PostObjective | None] = mapped_column(Enum(PostObjective))
    target_platforms: Mapped[list | None] = mapped_column(JSON)

    suggested_hook: Mapped[str | None] = mapped_column(Text)
    script: Mapped[str | None] = mapped_column(Text)
    shot_list: Mapped[list | None] = mapped_column(JSON)
    estimated_duration_min: Mapped[float | None] = mapped_column(Float)
    estimated_duration_max: Mapped[float | None] = mapped_column(Float)
    caption_draft: Mapped[str | None] = mapped_column(Text)
    hashtag_suggestions: Mapped[list | None] = mapped_column(JSON)

    ai_score: Mapped[float | None] = mapped_column(Float)
    ai_score_breakdown: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(100))
    source_detail: Mapped[str | None] = mapped_column(Text)

    series_id: Mapped[int | None] = mapped_column(ForeignKey("content_series.id"))
    trend_id: Mapped[int | None] = mapped_column(ForeignKey("trends.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_content_ideas_status", "creator_id", "status"),
    )


class ContentCalendar(Base):
    __tablename__ = "content_calendar"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    date: Mapped[date] = mapped_column(Date)
    slot: Mapped[str | None] = mapped_column(String(50))
    idea_id: Mapped[int | None] = mapped_column(ForeignKey("content_ideas.id"))
    platform: Mapped[Platform | None] = mapped_column(Enum(Platform))
    objective: Mapped[PostObjective | None] = mapped_column(Enum(PostObjective))
    notes: Mapped[str | None] = mapped_column(Text)
    suggested_time: Mapped[str | None] = mapped_column(String(20))
    is_rest_day: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_calendar_date", "creator_id", "date"),
    )


class ContentSeries(Base):
    __tablename__ = "content_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="active")
    episode_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_performance_vs_median: Mapped[float | None] = mapped_column(Float)
    momentum: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Hook(Base):
    """Private hook library — Kobby's tested hooks with performance data."""
    __tablename__ = "hooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    text: Mapped[str] = mapped_column(Text)
    hook_type: Mapped[str | None] = mapped_column(String(100))

    retention_1s: Mapped[float | None] = mapped_column(Float)
    retention_3s: Mapped[float | None] = mapped_column(Float)
    avg_watch_time: Mapped[float | None] = mapped_column(Float)
    performance_vs_median: Mapped[float | None] = mapped_column(Float)

    post: Mapped["Post"] = relationship(back_populates="hook")

    __table_args__ = (
        Index("ix_hooks_creator", "creator_id"),
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), unique=True)
    full_text: Mapped[str | None] = mapped_column(Text)
    segments: Mapped[list | None] = mapped_column(JSON)
    language: Mapped[str | None] = mapped_column(String(10))
    has_speech: Mapped[bool] = mapped_column(Boolean, default=False)
    first_spoken_sentence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["Post"] = relationship(back_populates="transcript")


class VideoVisualFeatures(Base):
    """AI-extracted visual tags from video frames."""
    __tablename__ = "video_visual_features"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), unique=True)

    face_visible_first_2s: Mapped[bool | None] = mapped_column(Boolean)
    body_visible: Mapped[bool | None] = mapped_column(Boolean)
    physique_reveal: Mapped[bool | None] = mapped_column(Boolean)
    shirtless: Mapped[bool | None] = mapped_column(Boolean)
    location_type: Mapped[str | None] = mapped_column(String(100))
    location_name: Mapped[str | None] = mapped_column(String(200))
    other_people_visible: Mapped[bool | None] = mapped_column(Boolean)
    exercise_performed: Mapped[str | None] = mapped_column(String(200))
    camera_movement: Mapped[str | None] = mapped_column(String(100))
    camera_angle: Mapped[str | None] = mapped_column(String(100))
    text_overlay: Mapped[bool | None] = mapped_column(Boolean)
    text_overlay_content: Mapped[str | None] = mapped_column(Text)
    first_visual_description: Mapped[str | None] = mapped_column(Text)
    editing_speed: Mapped[str | None] = mapped_column(String(50))
    cut_count: Mapped[int | None] = mapped_column(Integer)
    has_music: Mapped[bool | None] = mapped_column(Boolean)
    has_voice: Mapped[bool | None] = mapped_column(Boolean)
    music_genre: Mapped[str | None] = mapped_column(String(100))
    cta_type: Mapped[str | None] = mapped_column(String(100))
    dominant_emotion: Mapped[str | None] = mapped_column(String(100))
    lighting: Mapped[str | None] = mapped_column(String(100))
    color_palette: Mapped[str | None] = mapped_column(String(200))
    first_movement_second: Mapped[float | None] = mapped_column(Float)
    strongest_visual_second: Mapped[float | None] = mapped_column(Float)

    extra_tags: Mapped[dict | None] = mapped_column(JSON)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["Post"] = relationship(back_populates="visual_features")


class DraftReview(Base):
    """AI review of video before publishing."""
    __tablename__ = "draft_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"))
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    draft_file_path: Mapped[str | None] = mapped_column(Text)

    opening_score: Mapped[float | None] = mapped_column(Float)
    overall_score: Mapped[float | None] = mapped_column(Float)
    issues: Mapped[list | None] = mapped_column(JSON)
    suggestions: Mapped[list | None] = mapped_column(JSON)
    predicted_objective_fit: Mapped[str | None] = mapped_column(String(100))

    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["Post"] = relationship(back_populates="draft_reviews")


class StoriesPlan(Base):
    __tablename__ = "stories_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    date: Mapped[date] = mapped_column(Date)
    time_slot: Mapped[str] = mapped_column(String(20))
    story_type: Mapped[str] = mapped_column(String(100))
    concept: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(String(100))
    was_posted: Mapped[bool] = mapped_column(Boolean, default=False)
