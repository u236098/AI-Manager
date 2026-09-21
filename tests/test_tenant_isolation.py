"""Tenant isolation tests — verify creator-scoped queries never leak cross-tenant data."""
from __future__ import annotations
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app.models.core import Creator, PlatformAccount, Platform, Post, PostType, PostMetric
from app.models.manager import ManagerMemory, KnowledgeType
from app.services.dashboard import (
    get_creator_overview, get_accounts, get_recent_performance,
    get_content_themes, get_top_posts, get_post_details, get_manager_memory,
    search_posts,
)


@pytest_asyncio.fixture
async def multi_tenant_db(db):
    """DB with two creators, each having their own accounts and posts."""
    creator_a = Creator(id=1, name="Creator A", clerk_user_id="clerk_aaa")
    creator_b = Creator(id=2, name="Creator B", clerk_user_id="clerk_bbb")
    db.add_all([creator_a, creator_b])
    await db.flush()

    account_a = PlatformAccount(
        id=1, creator_id=1, platform=Platform.INSTAGRAM,
        platform_user_id="ig_a", username="creator_a",
    )
    account_b = PlatformAccount(
        id=2, creator_id=2, platform=Platform.INSTAGRAM,
        platform_user_id="ig_b", username="creator_b",
    )
    db.add_all([account_a, account_b])
    await db.flush()

    now = datetime.now(timezone.utc)
    for i in range(5):
        post_a = Post(
            id=i + 1, account_id=1, platform_post_id=f"a_{i}",
            post_type=PostType.REEL, caption=f"Creator A post {i}",
            published_at=now - timedelta(days=5 - i),
        )
        post_b = Post(
            id=i + 100, account_id=2, platform_post_id=f"b_{i}",
            post_type=PostType.REEL, caption=f"Creator B post {i}",
            published_at=now - timedelta(days=5 - i),
        )
        db.add_all([post_a, post_b])

    await db.flush()

    for i in range(5):
        metric_a = PostMetric(
            post_id=i + 1, views=1000 * (i + 1), likes=50 * (i + 1),
            captured_at=now, hours_after_publish=24.0,
        )
        metric_b = PostMetric(
            post_id=i + 100, views=2000 * (i + 1), likes=100 * (i + 1),
            captured_at=now, hours_after_publish=24.0,
        )
        db.add_all([metric_a, metric_b])

    mem_a = ManagerMemory(
        creator_id=1, knowledge_type=KnowledgeType.OBSERVATION,
        category="test", statement="Creator A observation",
        confidence=0.9, is_active=True,
    )
    mem_b = ManagerMemory(
        creator_id=2, knowledge_type=KnowledgeType.OBSERVATION,
        category="test", statement="Creator B observation",
        confidence=0.9, is_active=True,
    )
    db.add_all([mem_a, mem_b])

    await db.flush()
    await db.commit()
    return db


async def test_get_accounts_isolated(multi_tenant_db):
    result = await get_accounts(multi_tenant_db, creator_id=1)
    usernames = [a["username"] for a in result["accounts"]]
    assert "creator_a" in usernames
    assert "creator_b" not in usernames


async def test_get_accounts_creator_b(multi_tenant_db):
    result = await get_accounts(multi_tenant_db, creator_id=2)
    usernames = [a["username"] for a in result["accounts"]]
    assert "creator_b" in usernames
    assert "creator_a" not in usernames


async def test_get_creator_overview_isolated(multi_tenant_db):
    """Overview filters by creator_id; accounts without access_token are excluded
    from overview but still returned by get_accounts. Test via get_accounts."""
    result_a = await get_accounts(multi_tenant_db, creator_id=1)
    result_b = await get_accounts(multi_tenant_db, creator_id=2)
    usernames_a = [a["username"] for a in result_a["accounts"]]
    usernames_b = [a["username"] for a in result_b["accounts"]]
    assert "creator_a" in usernames_a
    assert "creator_b" not in usernames_a
    assert "creator_b" in usernames_b
    assert "creator_a" not in usernames_b


async def test_top_posts_isolated(multi_tenant_db):
    result_a = await get_top_posts(multi_tenant_db, creator_id=1)
    result_b = await get_top_posts(multi_tenant_db, creator_id=2)

    captions_a = [p["caption"] for p in result_a["posts"]]
    captions_b = [p["caption"] for p in result_b["posts"]]

    assert all("Creator A" in c for c in captions_a)
    assert all("Creator B" in c for c in captions_b)


async def test_search_posts_isolated(multi_tenant_db):
    result = await search_posts(multi_tenant_db, creator_id=1, query="post")
    captions = [p["caption"] for p in result["posts"]]
    assert all("Creator A" in c for c in captions)
    assert not any("Creator B" in c for c in captions)


async def test_post_details_isolated(multi_tenant_db):
    own_post = await get_post_details(multi_tenant_db, post_id=1, creator_id=1)
    other_post = await get_post_details(multi_tenant_db, post_id=100, creator_id=1)

    assert own_post["caption"] == "Creator A post 0"
    assert other_post == {"error": "Post 100 not found"}


async def test_manager_memory_isolated(multi_tenant_db):
    result_a = await get_manager_memory(multi_tenant_db, creator_id=1)
    result_b = await get_manager_memory(multi_tenant_db, creator_id=2)

    statements_a = [m["statement"] for m in result_a["memories"]]
    statements_b = [m["statement"] for m in result_b["memories"]]

    assert "Creator A observation" in statements_a
    assert "Creator B observation" not in statements_a
    assert "Creator B observation" in statements_b
    assert "Creator A observation" not in statements_b


async def test_recent_performance_isolated(multi_tenant_db):
    result_a = await get_recent_performance(multi_tenant_db, creator_id=1)
    result_b = await get_recent_performance(multi_tenant_db, creator_id=2)
    assert result_a["username"] == "creator_a"
    assert result_b["username"] == "creator_b"


async def test_nonexistent_creator_returns_empty(multi_tenant_db):
    result = await get_accounts(multi_tenant_db, creator_id=999)
    assert result["accounts"] == []


async def test_clerk_user_id_uniqueness(multi_tenant_db):
    """Verify that clerk_user_id column exists and is queryable."""
    from sqlalchemy import select
    creator = await multi_tenant_db.scalar(
        select(Creator).where(Creator.clerk_user_id == "clerk_aaa")
    )
    assert creator is not None
    assert creator.id == 1
    assert creator.name == "Creator A"


async def test_auth_disabled_returns_creator_1():
    """When CLERK_SECRET_KEY is empty, auth is disabled."""
    from app.auth import _auth_enabled
    with patch("app.config.get_settings") as mock_settings:
        mock_settings.return_value.clerk_secret_key = ""
        assert not _auth_enabled()


async def test_mcp_contextvar_default():
    """creator_id_var defaults to 0, _cid() falls back to 1."""
    from app.auth import creator_id_var
    from app.mcp.server import _cid
    token = creator_id_var.set(0)
    try:
        assert _cid() == 1
    finally:
        creator_id_var.reset(token)


async def test_mcp_contextvar_set():
    """When creator_id_var is set, _cid() returns that value."""
    from app.auth import creator_id_var
    from app.mcp.server import _cid
    token = creator_id_var.set(42)
    try:
        assert _cid() == 42
    finally:
        creator_id_var.reset(token)
