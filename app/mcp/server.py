"""MCP server for Kobby Manager.

Exposes read-only tools that let ChatGPT (or any MCP client) query the
creator's real Instagram and TikTok performance data. Creator identity
is resolved from the authenticated JWT via creator_id_var.
"""
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from app.auth import creator_id_var
from app.database import _get_session_factory

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    open_world_hint=False,
)

OAUTH_META = {
    "securitySchemes": [
        {
            "type": "oauth2",
            "scopes": ["openid", "profile", "email", "offline_access"],
        }
    ]
}

mcp = MCPServer(
    "Kobby Manager",
    instructions=(
        "Kobby Manager contains the creator's real Instagram and TikTok "
        "performance data. Use these tools to answer questions about "
        "content performance, growth, audience, posts, themes and strategy. "
        "Distinguish facts, observations and hypotheses. "
        "Do not claim causation when the data only shows correlation."
    ),
)


@asynccontextmanager
async def get_db():
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


def _cid() -> int:
    return creator_id_var.get() or 1


@mcp.tool(annotations=READ_ONLY, meta=OAUTH_META)
async def get_creator_overview() -> dict:
    """Return the creator's current account overview across Instagram
    and TikTok, including followers, post counts, top observations
    and hypotheses."""
    from app.services.dashboard import get_creator_overview as _get

    async with get_db() as db:
        return await _get(db, creator_id=_cid())


@mcp.tool(annotations=READ_ONLY, meta=OAUTH_META)
async def get_accounts() -> dict:
    """Return connected social media accounts with follower counts and
    post totals. Never returns tokens or credentials."""
    from app.services.dashboard import get_accounts as _get

    async with get_db() as db:
        return await _get(db, creator_id=_cid())


@mcp.tool(annotations=READ_ONLY, meta=OAUTH_META)
async def get_recent_performance(
    platform: str | None = None,
    days: int = 30,
) -> dict:
    """Return aggregated performance metrics for a recent time window.

    Args:
        platform: Filter to 'instagram' or 'tiktok'. Omit for both.
        days: Number of days to look back (default 30, max 365).
    """
    from app.services.dashboard import get_recent_performance as _get

    async with get_db() as db:
        return await _get(db, creator_id=_cid(), platform=platform, days=days)


@mcp.tool(annotations=READ_ONLY, meta=OAUTH_META)
async def get_content_themes(
    platform: str | None = None,
) -> dict:
    """Return content theme/cluster performance analysis showing which
    themes outperform or underperform the baseline.

    Args:
        platform: Filter to 'instagram' or 'tiktok'. Omit for all.
    """
    from app.services.dashboard import get_content_themes as _get

    async with get_db() as db:
        return await _get(db, creator_id=_cid(), platform=platform)


@mcp.tool(annotations=READ_ONLY, meta=OAUTH_META)
async def get_top_posts(
    platform: str | None = None,
    metric: str = "views",
    limit: int = 10,
    content_theme: str | None = None,
) -> dict:
    """Return the top-performing posts ranked by a chosen metric.

    Args:
        platform: Filter to 'instagram' or 'tiktok'. Omit for both.
        metric: One of views, reach, likes, shares, saves, follows,
                follow_rate, profile_visits, engagement_rate, comments.
                Posts with unavailable follower attribution are excluded
                from follows and follow_rate rankings.
        limit: Number of posts to return (1-50, default 10).
        content_theme: Filter to a specific content theme like
                       'lifestyle', 'calisthenics', 'workout_routine'.
    """
    from app.services.dashboard import get_top_posts as _get

    async with get_db() as db:
        return await _get(
            db, creator_id=_cid(), platform=platform, metric=metric,
            limit=limit, content_theme=content_theme,
        )


@mcp.tool(annotations=READ_ONLY, meta=OAUTH_META)
async def get_post_details(post_id: int) -> dict:
    """Return full details about a single post including metrics,
    content themes and related observations.

    Args:
        post_id: The database ID of the post.
    """
    from app.services.dashboard import get_post_details as _get

    async with get_db() as db:
        return await _get(db, post_id, creator_id=_cid())


@mcp.tool(annotations=READ_ONLY, meta=OAUTH_META)
async def get_manager_memory(
    knowledge_type: str | None = None,
    platform: str | None = None,
    limit: int = 30,
) -> dict:
    """Return the manager's accumulated knowledge — facts, observations
    and hypotheses derived from data analysis.

    Args:
        knowledge_type: Filter by 'fact', 'observation' or 'hypothesis'.
        platform: Filter memories mentioning 'instagram' or 'tiktok'.
        limit: Max memories to return (1-100, default 30).
    """
    from app.services.dashboard import get_manager_memory as _get

    async with get_db() as db:
        return await _get(
            db, creator_id=_cid(), knowledge_type=knowledge_type,
            platform=platform, limit=limit,
        )


@mcp.tool(annotations=READ_ONLY, meta=OAUTH_META)
async def search_posts(
    query: str | None = None,
    platform: str | None = None,
    theme: str | None = None,
    min_views: int | None = None,
    min_likes: int | None = None,
    limit: int = 20,
) -> dict:
    """Search posts by caption text, platform, content theme or
    minimum metric thresholds.

    Args:
        query: Text to search in captions (case-insensitive).
        platform: Filter to 'instagram' or 'tiktok'.
        theme: Content theme like 'lifestyle', 'calisthenics', etc.
        min_views: Minimum view count.
        min_likes: Minimum like count.
        limit: Max results (1-50, default 20).
    """
    from app.services.dashboard import search_posts as _get

    async with get_db() as db:
        return await _get(
            db, creator_id=_cid(), query=query, platform=platform,
            theme=theme, min_views=min_views,
            min_likes=min_likes, limit=limit,
        )
