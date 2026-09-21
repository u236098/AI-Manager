"""Core models: creator, platforms, accounts, posts, metrics."""
import enum
from datetime import datetime, date
from sqlalchemy import (
    String, Text, Integer, BigInteger, Float, Boolean, Date, DateTime,
    Enum, ForeignKey, Index, UniqueConstraint, JSON, Interval,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class Platform(str, enum.Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    accounts: Mapped[list["PlatformAccount"]] = relationship(back_populates="creator")
    brand_strategy: Mapped["BrandStrategy"] = relationship(back_populates="creator", uselist=False)


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    platform: Mapped[Platform] = mapped_column(Enum(Platform))
    platform_user_id: Mapped[str | None] = mapped_column(String(200))
    username: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str | None] = mapped_column(String(300))
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    creator: Mapped["Creator"] = relationship(back_populates="accounts")
    profiles: Mapped[list["ProfileSnapshot"]] = relationship(back_populates="account")
    posts: Mapped[list["Post"]] = relationship(back_populates="account")

    __table_args__ = (
        UniqueConstraint("platform", "platform_user_id"),
    )


class ProfileSnapshot(Base):
    """Periodic snapshot of the account profile for tracking changes."""
    __tablename__ = "profile_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    username: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str | None] = mapped_column(String(300))
    bio: Mapped[str | None] = mapped_column(Text)
    profile_pic_url: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(200))
    follower_count: Mapped[int | None] = mapped_column(BigInteger)
    following_count: Mapped[int | None] = mapped_column(Integer)
    post_count: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict | None] = mapped_column(JSON)

    account: Mapped["PlatformAccount"] = relationship(back_populates="profiles")

    __table_args__ = (
        Index("ix_profile_snapshots_account_captured", "account_id", "captured_at"),
    )


class PostType(str, enum.Enum):
    REEL = "reel"
    FEED = "feed"
    STORY = "story"
    CAROUSEL = "carousel"
    TIKTOK_VIDEO = "tiktok_video"


class PostObjective(str, enum.Enum):
    REACH = "reach"
    FOLLOWER_CONVERSION = "follower_conversion"
    AUTHORITY = "authority"
    PERSONALITY = "personality"
    COMMUNITY = "community"
    TRUST = "trust"
    COMMERCIAL = "commercial"
    EXPERIMENTAL = "experimental"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"))
    platform_post_id: Mapped[str | None] = mapped_column(String(200))
    post_type: Mapped[PostType] = mapped_column(Enum(PostType))
    objective: Mapped[PostObjective | None] = mapped_column(Enum(PostObjective))

    caption: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list | None] = mapped_column(JSON)
    mentions: Mapped[list | None] = mapped_column(JSON)
    media_url: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    local_media_path: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    content_idea_id: Mapped[int | None] = mapped_column(ForeignKey("content_ideas.id"))
    series_id: Mapped[int | None] = mapped_column(ForeignKey("content_series.id"))
    series_episode: Mapped[int | None] = mapped_column(Integer)

    account: Mapped["PlatformAccount"] = relationship(back_populates="posts")
    metrics: Mapped[list["PostMetric"]] = relationship(back_populates="post")
    visual_features: Mapped["VideoVisualFeatures"] = relationship(back_populates="post", uselist=False)
    transcript: Mapped["Transcript"] = relationship(back_populates="post", uselist=False)
    hook: Mapped["Hook"] = relationship(back_populates="post", uselist=False)
    comments: Mapped[list["Comment"]] = relationship(back_populates="post")
    draft_reviews: Mapped[list["DraftReview"]] = relationship(back_populates="post")

    __table_args__ = (
        UniqueConstraint("account_id", "platform_post_id"),
        Index("ix_posts_published", "account_id", "published_at"),
        Index("ix_posts_objective", "objective"),
    )


class PostMetric(Base):
    """Time-series metrics — snapshot taken at regular intervals after publish."""
    __tablename__ = "post_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    hours_after_publish: Mapped[float | None] = mapped_column(Float)

    views: Mapped[int | None] = mapped_column(BigInteger)
    likes: Mapped[int | None] = mapped_column(BigInteger)
    comments_count: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    reach: Mapped[int | None] = mapped_column(BigInteger)
    impressions: Mapped[int | None] = mapped_column(BigInteger)

    followers_from_post: Mapped[int | None] = mapped_column(Integer)
    profile_visits_from_post: Mapped[int | None] = mapped_column(Integer)

    avg_watch_time_seconds: Mapped[float | None] = mapped_column(Float)
    retention_rate: Mapped[float | None] = mapped_column(Float)
    completion_rate: Mapped[float | None] = mapped_column(Float)

    audience_source: Mapped[dict | None] = mapped_column(JSON)
    audience_demographics: Mapped[dict | None] = mapped_column(JSON)
    extra: Mapped[dict | None] = mapped_column(JSON)

    post: Mapped["Post"] = relationship(back_populates="metrics")

    __table_args__ = (
        Index("ix_post_metrics_post_captured", "post_id", "captured_at"),
    )


class AccountMetricSnapshot(Base):
    """Daily account-level metrics."""
    __tablename__ = "account_metric_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"))
    date: Mapped[date] = mapped_column(Date)

    followers: Mapped[int | None] = mapped_column(BigInteger)
    followers_delta: Mapped[int | None] = mapped_column(Integer)
    following: Mapped[int | None] = mapped_column(Integer)
    posts_count: Mapped[int | None] = mapped_column(Integer)
    total_reach: Mapped[int | None] = mapped_column(BigInteger)
    total_impressions: Mapped[int | None] = mapped_column(BigInteger)
    profile_visits: Mapped[int | None] = mapped_column(Integer)
    profile_to_follow_rate: Mapped[float | None] = mapped_column(Float)
    audience_top_countries: Mapped[dict | None] = mapped_column(JSON)
    audience_top_cities: Mapped[dict | None] = mapped_column(JSON)
    audience_age_gender: Mapped[dict | None] = mapped_column(JSON)
    audience_active_hours: Mapped[dict | None] = mapped_column(JSON)
    extra: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("account_id", "date"),
        Index("ix_account_metrics_date", "account_id", "date"),
    )
