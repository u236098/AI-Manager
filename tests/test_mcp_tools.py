"""Tests for the MCP tool service functions.

Tests the shared service layer that powers both MCP tools and REST API.
Validates correct data, security (no credential leaks), and input validation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    Creator, PlatformAccount, Platform, Post, PostType, PostObjective,
    PostMetric, ProfileSnapshot,
)
from app.models.manager import ManagerMemory, KnowledgeType

SENSITIVE_STRINGS = [
    "access_token", "refresh_token", "client_secret",
    "app_secret", "secret_key", "EAAx",
]


@pytest_asyncio.fixture
async def mcp_db(db: AsyncSession):
    """Seed DB with realistic data for MCP tool testing."""
    creator = Creator(id=1, name="Kobby Cooper")
    db.add(creator)
    await db.flush()

    ig_account = PlatformAccount(
        id=1, creator_id=1, platform=Platform.INSTAGRAM,
        platform_user_id="ig_123", username="kobbycooper",
        display_name="Kobby✪",
        access_token="EAAx_FAKE_TOKEN_NEVER_EXPOSE",
        refresh_token="REFRESH_FAKE_NEVER_EXPOSE",
    )
    tt_account = PlatformAccount(
        id=2, creator_id=1, platform=Platform.TIKTOK,
        platform_user_id="tt_456", username="fittokboy",
        display_name="fittokboy",
        access_token="TT_FAKE_TOKEN_NEVER_EXPOSE",
    )
    db.add_all([ig_account, tt_account])
    await db.flush()

    ig_profile = ProfileSnapshot(
        account_id=1, username="kobbycooper",
        follower_count=13388, following_count=500, post_count=117,
    )
    tt_profile = ProfileSnapshot(
        account_id=2, username="fittokboy",
        follower_count=977, following_count=200, post_count=81,
    )
    db.add_all([ig_profile, tt_profile])
    await db.flush()

    now = datetime.now(timezone.utc)
    posts = []
    captions = [
        "Morning sunrise vlog with the crew #lifestyle #grwm",
        "Calisthenics workout at the park #pullup #calisthenics",
        "Quick arm workout at home",
        "Never stop the grind #motivation #discipline",
        "Trending dance challenge #viral #fyp #trend",
        "Team workout with friends #teamwork #crew",
        "Day in my life as a fitness creator #lifestyle #vlog",
        "Muscle up tutorial for beginners #muscleup #calisthenics",
        "Beach workout vibes #outdoor #nature",
        "My physique transformation #gains #transformation",
    ]

    for i in range(10):
        platform = Platform.INSTAGRAM if i < 6 else Platform.TIKTOK
        account_id = 1 if i < 6 else 2
        post = Post(
            id=i + 1,
            account_id=account_id,
            platform_post_id=f"post_{i}",
            post_type=PostType.REEL if platform == Platform.INSTAGRAM else PostType.TIKTOK_VIDEO,
            caption=captions[i],
            objective=PostObjective.REACH,
            published_at=now - timedelta(days=20 - i),
            duration_seconds=30.0,
        )
        db.add(post)
        posts.append(post)
    await db.flush()

    views_list = [5000, 8000, 3000, 12000, 2000, 7000, 634117, 4000, 6000, 9000]
    for i, post in enumerate(posts):
        metric = PostMetric(
            post_id=post.id,
            views=views_list[i],
            likes=int(views_list[i] * 0.05),
            saves=int(views_list[i] * 0.02) if i < 6 else None,
            shares=int(views_list[i] * 0.01),
            comments_count=int(views_list[i] * 0.005),
            followers_from_post=int(views_list[i] * 0.003),
            reach=int(views_list[i] * 1.2) if i < 6 else None,
            profile_visits_from_post=int(views_list[i] * 0.001),
            captured_at=post.published_at + timedelta(hours=168),
            hours_after_publish=168.0,
        )
        db.add(metric)
    await db.flush()

    memories = [
        ManagerMemory(
            creator_id=1, knowledge_type=KnowledgeType.FACT,
            category="baseline",
            statement="TikTok account has 81 videos, 977 followers.",
            evidence_post_ids=[7, 8, 9, 10],
            metrics_considered=["views"], sample_size=81, confidence=0.95,
        ),
        ManagerMemory(
            creator_id=1, knowledge_type=KnowledgeType.OBSERVATION,
            category="content_clustering",
            statement="'lifestyle' content (7 posts) outperforms baseline by 1.8x.",
            evidence_post_ids=[1, 7],
            metrics_considered=["views", "engagement_rate"], sample_size=7, confidence=0.82,
        ),
        ManagerMemory(
            creator_id=1, knowledge_type=KnowledgeType.HYPOTHESIS,
            category="brand_positioning",
            statement="Kobby's strongest positioning may be lifestyle-led.",
            evidence_post_ids=None,
            metrics_considered=["views", "likes"], sample_size=198, confidence=0.45,
        ),
        ManagerMemory(
            creator_id=1, knowledge_type=KnowledgeType.OBSERVATION,
            category="ig_cluster_lifestyle",
            statement="Instagram 'lifestyle' content (24 posts) has median 441 likes.",
            evidence_post_ids=[1, 7],
            metrics_considered=["likes"], sample_size=24, confidence=0.85,
        ),
    ]
    db.add_all(memories)
    await db.flush()
    await db.commit()
    return db


# ---- Tool tests ----


class TestGetCreatorOverview:
    async def test_returns_accounts_and_followers(self, mcp_db):
        from app.services.dashboard import get_creator_overview
        result = await get_creator_overview(mcp_db)
        assert "accounts" in result
        assert result["total_followers"] == 13388 + 977
        assert len(result["accounts"]) == 2

    async def test_no_credentials_in_output(self, mcp_db):
        from app.services.dashboard import get_creator_overview
        result = await get_creator_overview(mcp_db)
        serialized = json.dumps(result)
        for sensitive in SENSITIVE_STRINGS:
            assert sensitive not in serialized


class TestGetAccounts:
    async def test_returns_both_accounts(self, mcp_db):
        from app.services.dashboard import get_accounts
        result = await get_accounts(mcp_db)
        assert len(result["accounts"]) == 2
        platforms = {a["platform"] for a in result["accounts"]}
        assert platforms == {"instagram", "tiktok"}

    async def test_no_tokens_exposed(self, mcp_db):
        from app.services.dashboard import get_accounts
        result = await get_accounts(mcp_db)
        serialized = json.dumps(result)
        assert "access_token" not in serialized
        assert "refresh_token" not in serialized
        assert "client_secret" not in serialized
        assert "EAAx" not in serialized
        assert "FAKE_TOKEN" not in serialized

    async def test_follower_counts(self, mcp_db):
        from app.services.dashboard import get_accounts
        result = await get_accounts(mcp_db)
        ig = next(a for a in result["accounts"] if a["platform"] == "instagram")
        tt = next(a for a in result["accounts"] if a["platform"] == "tiktok")
        assert ig["followers"] == 13388
        assert tt["followers"] == 977


class TestGetRecentPerformance:
    async def test_returns_performance_data(self, mcp_db):
        from app.services.dashboard import get_recent_performance
        result = await get_recent_performance(mcp_db, days=30)
        assert "platforms" in result or "posts" in result

    async def test_platform_filter(self, mcp_db):
        from app.services.dashboard import get_recent_performance
        result = await get_recent_performance(mcp_db, platform="instagram", days=30)
        if "error" not in result:
            assert result.get("platform") == "instagram" or all(
                p["platform"] == "instagram" for p in result.get("platforms", [result])
            )

    async def test_rejects_invalid_days(self, mcp_db):
        from app.services.dashboard import get_recent_performance
        result = await get_recent_performance(mcp_db, days=0)
        assert "error" in result

    async def test_rejects_invalid_platform(self, mcp_db):
        from app.services.dashboard import get_recent_performance
        result = await get_recent_performance(mcp_db, platform="fakebook")
        assert "error" in result


class TestGetContentThemes:
    async def test_returns_themes(self, mcp_db):
        from app.services.dashboard import get_content_themes
        result = await get_content_themes(mcp_db)
        assert "themes" in result
        assert len(result["themes"]) > 0

    async def test_theme_has_expected_fields(self, mcp_db):
        from app.services.dashboard import get_content_themes
        result = await get_content_themes(mcp_db)
        theme = result["themes"][0]
        assert "theme" in theme
        assert "statement" in theme
        assert "confidence" in theme


class TestGetTopPosts:
    async def test_returns_posts_by_views(self, mcp_db):
        from app.services.dashboard import get_top_posts
        result = await get_top_posts(mcp_db, metric="views", limit=5)
        assert "posts" in result
        assert len(result["posts"]) <= 5
        views = [p["views"] for p in result["posts"]]
        assert views == sorted(views, reverse=True)

    async def test_returns_posts_by_follows(self, mcp_db):
        from app.services.dashboard import get_top_posts
        result = await get_top_posts(mcp_db, metric="follows", limit=3)
        assert "posts" in result

    async def test_returns_posts_by_follow_rate(self, mcp_db):
        from app.services.dashboard import get_top_posts
        result = await get_top_posts(mcp_db, metric="follow_rate", limit=3)
        assert "posts" in result
        rates = [p["follow_rate"] for p in result["posts"]]
        assert rates == sorted(rates, reverse=True)
        assert all("followers_from_post" in p for p in result["posts"])

    async def test_missing_follow_attribution_is_not_zero(self, mcp_db):
        from sqlalchemy import update
        from app.models.core import PostMetric
        from app.services.dashboard import get_top_posts

        await mcp_db.execute(
            update(PostMetric)
            .where(PostMetric.post_id == 1)
            .values(followers_from_post=None)
        )
        await mcp_db.commit()

        result = await get_top_posts(mcp_db, metric="follow_rate", limit=50)
        assert all(p["followers_from_post"] is not None for p in result["posts"])
        assert all(p["follow_rate"] is not None for p in result["posts"])

    async def test_rejects_invalid_metric(self, mcp_db):
        from app.services.dashboard import get_top_posts
        result = await get_top_posts(mcp_db, metric="DROP TABLE posts")
        assert "error" in result

    async def test_clamps_limit(self, mcp_db):
        from app.services.dashboard import get_top_posts
        result = await get_top_posts(mcp_db, metric="views", limit=999)
        assert len(result["posts"]) <= 50

    async def test_platform_filter(self, mcp_db):
        from app.services.dashboard import get_top_posts
        result = await get_top_posts(mcp_db, platform="tiktok", metric="views", limit=10)
        for p in result["posts"]:
            assert p["platform"] == "tiktok"

    async def test_no_credentials_in_output(self, mcp_db):
        from app.services.dashboard import get_top_posts
        result = await get_top_posts(mcp_db, metric="views", limit=10)
        serialized = json.dumps(result)
        for sensitive in SENSITIVE_STRINGS:
            assert sensitive not in serialized


class TestGetPostDetails:
    async def test_returns_post_with_metrics(self, mcp_db):
        from app.services.dashboard import get_post_details
        result = await get_post_details(mcp_db, post_id=1)
        assert result["id"] == 1
        assert result["platform"] == "instagram"
        assert result["metrics"] is not None
        assert result["metrics"]["views"] == 5000

    async def test_returns_content_themes(self, mcp_db):
        from app.services.dashboard import get_post_details
        result = await get_post_details(mcp_db, post_id=1)
        assert "content_themes" in result
        assert "lifestyle" in result["content_themes"]

    async def test_returns_related_observations(self, mcp_db):
        from app.services.dashboard import get_post_details
        result = await get_post_details(mcp_db, post_id=1)
        assert "observations" in result
        assert len(result["observations"]) > 0

    async def test_unknown_post_returns_error(self, mcp_db):
        from app.services.dashboard import get_post_details
        result = await get_post_details(mcp_db, post_id=99999)
        assert "error" in result

    async def test_no_credentials_in_output(self, mcp_db):
        from app.services.dashboard import get_post_details
        result = await get_post_details(mcp_db, post_id=1)
        serialized = json.dumps(result)
        for sensitive in SENSITIVE_STRINGS:
            assert sensitive not in serialized


class TestSearchPosts:
    async def test_search_by_caption(self, mcp_db):
        from app.services.dashboard import search_posts
        result = await search_posts(mcp_db, query="workout")
        assert result["count"] > 0
        for p in result["posts"]:
            assert "workout" in p["caption"].lower()

    async def test_search_by_theme(self, mcp_db):
        from app.services.dashboard import search_posts
        result = await search_posts(mcp_db, theme="lifestyle")
        assert result["count"] > 0
        for p in result["posts"]:
            assert "lifestyle" in p["content_themes"]

    async def test_search_by_min_views(self, mcp_db):
        from app.services.dashboard import search_posts
        result = await search_posts(mcp_db, min_views=10000)
        assert result["count"] > 0
        for p in result["posts"]:
            assert p["views"] >= 10000

    async def test_search_platform_filter(self, mcp_db):
        from app.services.dashboard import search_posts
        result = await search_posts(mcp_db, platform="tiktok")
        for p in result["posts"]:
            assert p["platform"] == "tiktok"

    async def test_rejects_invalid_platform(self, mcp_db):
        from app.services.dashboard import search_posts
        result = await search_posts(mcp_db, platform="myspace")
        assert "error" in result

    async def test_limit_clamped(self, mcp_db):
        from app.services.dashboard import search_posts
        result = await search_posts(mcp_db, limit=999)
        assert result["count"] <= 50

    async def test_no_credentials_in_output(self, mcp_db):
        from app.services.dashboard import search_posts
        result = await search_posts(mcp_db)
        serialized = json.dumps(result)
        for sensitive in SENSITIVE_STRINGS:
            assert sensitive not in serialized


class TestGetManagerMemory:
    async def test_returns_all_types(self, mcp_db):
        from app.services.dashboard import get_manager_memory
        result = await get_manager_memory(mcp_db)
        assert result["count"] > 0
        types = {m["type"] for m in result["memories"]}
        assert "fact" in types
        assert "observation" in types
        assert "hypothesis" in types

    async def test_filter_by_type(self, mcp_db):
        from app.services.dashboard import get_manager_memory
        result = await get_manager_memory(mcp_db, knowledge_type="fact")
        for m in result["memories"]:
            assert m["type"] == "fact"

    async def test_rejects_invalid_type(self, mcp_db):
        from app.services.dashboard import get_manager_memory
        result = await get_manager_memory(mcp_db, knowledge_type="made_up")
        assert "error" in result

    async def test_limit_respected(self, mcp_db):
        from app.services.dashboard import get_manager_memory
        result = await get_manager_memory(mcp_db, limit=2)
        assert result["count"] <= 2

    async def test_no_credentials_in_output(self, mcp_db):
        from app.services.dashboard import get_manager_memory
        result = await get_manager_memory(mcp_db)
        serialized = json.dumps(result)
        for sensitive in SENSITIVE_STRINGS:
            assert sensitive not in serialized
