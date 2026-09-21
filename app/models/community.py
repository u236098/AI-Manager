"""Community models: comments, followers, relationships, CRM."""
from datetime import datetime
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime,
    Enum, ForeignKey, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base
from app.models.core import Platform


class CommentCategory(str):
    QUESTION = "question"
    COMPLIMENT = "compliment"
    CRITICISM = "criticism"
    FITNESS_QUESTION = "fitness_question"
    CONTENT_REQUEST = "content_request"
    VIDEO_SUGGESTION = "video_suggestion"
    BRAND_OPPORTUNITY = "brand_opportunity"
    SPAM = "spam"
    OTHER = "other"


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    platform_comment_id: Mapped[str | None] = mapped_column(String(200))
    author_username: Mapped[str | None] = mapped_column(String(200))
    author_platform_id: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    like_count: Mapped[int | None] = mapped_column(Integer)

    category: Mapped[str | None] = mapped_column(String(100))
    sentiment: Mapped[str | None] = mapped_column(String(50))
    should_respond: Mapped[bool | None] = mapped_column(Boolean)
    respond_reason: Mapped[str | None] = mapped_column(Text)
    suggested_response: Mapped[str | None] = mapped_column(Text)
    was_responded: Mapped[bool] = mapped_column(Boolean, default=False)
    can_become_content: Mapped[bool | None] = mapped_column(Boolean)

    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"))

    post: Mapped["Post"] = relationship(back_populates="comments")

    __table_args__ = (
        Index("ix_comments_post", "post_id"),
        Index("ix_comments_should_respond", "should_respond"),
        Index("ix_comments_author", "author_platform_id"),
    )


class Contact(Base):
    """Mini-CRM — tracks notable followers, creators, brands."""
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    platform: Mapped[Platform | None] = mapped_column(Enum(Platform))
    platform_user_id: Mapped[str | None] = mapped_column(String(200))
    username: Mapped[str | None] = mapped_column(String(200))
    display_name: Mapped[str | None] = mapped_column(String(300))

    contact_type: Mapped[str] = mapped_column(String(50))
    follower_count: Mapped[int | None] = mapped_column(Integer)
    is_creator: Mapped[bool] = mapped_column(Boolean, default=False)
    niche: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))

    total_comments: Mapped[int] = mapped_column(Integer, default=0)
    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    first_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    audience_overlap_score: Mapped[float | None] = mapped_column(Float)
    collaboration_potential: Mapped[float | None] = mapped_column(Float)
    relationship_status: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_contacts_creator", "creator_id"),
        Index("ix_contacts_collab", "collaboration_potential"),
    )


class CollaborationProposal(Base):
    __tablename__ = "collaboration_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"))
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))

    why: Mapped[str | None] = mapped_column(Text)
    concept: Mapped[str | None] = mapped_column(Text)
    audience_overlap: Mapped[float | None] = mapped_column(Float)
    content_compatibility: Mapped[float | None] = mapped_column(Float)
    brand_safety: Mapped[float | None] = mapped_column(Float)
    overall_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), default="suggested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
