"""Shared fixtures — in-memory SQLite via aiosqlite for fast isolated tests."""
from __future__ import annotations
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import Base
import app.models  # noqa: F401 — ensure all models are imported so Base.metadata is complete


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(db):
    """DB with a creator, platform account, and sample posts + metrics."""
    from app.models.core import Creator, PlatformAccount, Platform, Post, PostType, PostObjective, PostMetric

    creator = Creator(id=1, name="Kobby Cooper")
    db.add(creator)
    await db.flush()

    account = PlatformAccount(
        id=1, creator_id=1, platform=Platform.INSTAGRAM,
        platform_user_id="123", username="kobbycooper",
    )
    db.add(account)
    await db.flush()

    now = datetime.now(timezone.utc)
    posts = []
    objectives = [PostObjective.REACH, PostObjective.AUTHORITY, PostObjective.FOLLOWER_CONVERSION, PostObjective.PERSONALITY, PostObjective.COMMUNITY]

    for i in range(10):
        post = Post(
            id=i + 1,
            account_id=1,
            platform_post_id=f"post_{i}",
            post_type=PostType.REEL,
            caption=f"Test post {i}",
            objective=objectives[i % len(objectives)],
            published_at=now - timedelta(days=10 - i),
            duration_seconds=30.0,
        )
        db.add(post)
        posts.append(post)

    await db.flush()

    views_base = [5000, 8000, 3000, 12000, 2000, 7000, 15000, 4000, 6000, 9000]
    for i, post in enumerate(posts):
        for hours in [2, 24, 72, 168]:
            scale = {2: 0.3, 24: 0.6, 72: 0.85, 168: 1.0}[hours]
            views = int(views_base[i] * scale)
            metric = PostMetric(
                post_id=post.id,
                views=views,
                likes=int(views * 0.05),
                saves=int(views * 0.02),
                shares=int(views * 0.01),
                comments_count=int(views * 0.005),
                followers_from_post=int(views * 0.003),
                retention_rate=0.45 + (i % 3) * 0.1,
                completion_rate=0.30 + (i % 4) * 0.05,
                hours_after_publish=float(hours),
                captured_at=post.published_at + timedelta(hours=hours),
            )
            db.add(metric)

    await db.flush()
    await db.commit()
    return db
