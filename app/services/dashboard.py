"""Shared dashboard/MCP service functions.

These are the canonical data-access functions for creator overview, accounts,
performance, themes, posts, and memory. Both the REST API and MCP tools
call into this module rather than duplicating query logic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    PlatformAccount, Post, PostMetric, ProfileSnapshot,
    AccountMetricSnapshot, Platform,
)
from app.models.manager import ManagerMemory, KnowledgeType


ALLOWED_METRICS = {
    "views",
    "reach",
    "likes",
    "shares",
    "saves",
    "follows",
    "profile_visits",
    "engagement_rate",
    "comments",
}

SENSITIVE_FIELDS = {
    "access_token", "refresh_token", "token_expires_at",
    "meta_app_secret", "tiktok_client_secret", "client_secret",
}


def _strip_sensitive(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in SENSITIVE_FIELDS}


async def get_creator_overview(db: AsyncSession, creator_id: int = 1) -> dict:
    accounts_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.creator_id == creator_id,
            PlatformAccount.is_active == True,
            PlatformAccount.access_token.isnot(None),
        )
    )
    accounts = accounts_result.scalars().all()

    account_summaries = []
    for acc in accounts:
        latest_profile = (
            await db.scalars(
                select(ProfileSnapshot)
                .where(ProfileSnapshot.account_id == acc.id)
                .order_by(ProfileSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()

        post_count = await db.scalar(
            select(func.count()).select_from(Post).where(Post.account_id == acc.id)
        )

        account_summaries.append({
            "id": acc.id,
            "platform": acc.platform.value,
            "username": acc.username,
            "followers": latest_profile.follower_count if latest_profile else None,
            "post_count": post_count,
        })

    total_followers = sum(a["followers"] or 0 for a in account_summaries)

    observations = (
        await db.scalars(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.is_active == True,
                ManagerMemory.knowledge_type == KnowledgeType.OBSERVATION,
            ).order_by(ManagerMemory.confidence.desc().nulls_last()).limit(8)
        )
    ).all()

    hypotheses = (
        await db.scalars(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.is_active == True,
                ManagerMemory.knowledge_type == KnowledgeType.HYPOTHESIS,
            ).order_by(ManagerMemory.updated_at.desc()).limit(3)
        )
    ).all()

    return {
        "accounts": account_summaries,
        "total_followers": total_followers,
        "observations": [
            {
                "id": o.id,
                "category": o.category,
                "statement": o.statement,
                "confidence": o.confidence,
                "sample_size": o.sample_size,
            }
            for o in observations
        ],
        "hypotheses": [
            {
                "id": h.id,
                "category": h.category,
                "statement": h.statement,
                "confidence": h.confidence,
            }
            for h in hypotheses
        ],
    }


async def get_accounts(db: AsyncSession, creator_id: int = 1) -> dict:
    accounts_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.creator_id == creator_id,
            PlatformAccount.is_active == True,
        )
    )
    accounts = accounts_result.scalars().all()

    result = []
    for acc in accounts:
        latest_profile = (
            await db.scalars(
                select(ProfileSnapshot)
                .where(ProfileSnapshot.account_id == acc.id)
                .order_by(ProfileSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()

        post_count = await db.scalar(
            select(func.count()).select_from(Post).where(Post.account_id == acc.id)
        )

        result.append({
            "platform": acc.platform.value,
            "username": acc.username,
            "display_name": acc.display_name,
            "followers": latest_profile.follower_count if latest_profile else None,
            "posts": post_count,
        })

    return {"accounts": result}


async def get_recent_performance(
    db: AsyncSession,
    creator_id: int = 1,
    platform: str | None = None,
    days: int = 30,
) -> dict:
    if days < 1:
        return {"error": "days must be >= 1"}
    if days > 365:
        days = 365

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(PlatformAccount)
        .where(
            PlatformAccount.creator_id == creator_id,
            PlatformAccount.is_active == True,
        )
    )
    if platform:
        platform_lower = platform.lower()
        if platform_lower not in ("instagram", "tiktok", "youtube"):
            return {"error": f"Unknown platform: {platform}"}
        query = query.where(PlatformAccount.platform == Platform(platform_lower))

    accounts = (await db.execute(query)).scalars().all()
    if not accounts:
        return {"error": "No accounts found"}

    results = []
    for acc in accounts:
        rows = (await db.execute(
            select(Post, PostMetric)
            .join(PostMetric, PostMetric.post_id == Post.id)
            .where(
                Post.account_id == acc.id,
                Post.published_at >= cutoff,
            )
            .order_by(Post.published_at.desc())
        )).all()

        if not rows:
            results.append({
                "platform": acc.platform.value,
                "username": acc.username,
                "window_days": days,
                "posts": 0,
            })
            continue

        views_list = [m.views or 0 for _, m in rows]
        likes_list = [m.likes or 0 for _, m in rows]
        saves_list = [m.saves or 0 for _, m in rows if m.saves is not None]
        shares_list = [m.shares or 0 for _, m in rows if m.shares is not None]
        follows_list = [m.followers_from_post or 0 for _, m in rows if m.followers_from_post is not None]

        perf = {
            "platform": acc.platform.value,
            "username": acc.username,
            "window_days": days,
            "posts": len(rows),
            "median_views": round(median(views_list)) if views_list else 0,
            "median_likes": round(median(likes_list)) if likes_list else 0,
            "total_saves": sum(saves_list),
            "total_shares": sum(shares_list),
            "follows_from_posts": sum(follows_list),
        }

        # Historical comparison: same window before this one
        prev_cutoff = cutoff - timedelta(days=days)
        prev_rows = (await db.execute(
            select(PostMetric.views)
            .join(Post, Post.id == PostMetric.post_id)
            .where(
                Post.account_id == acc.id,
                Post.published_at >= prev_cutoff,
                Post.published_at < cutoff,
            )
        )).scalars().all()

        if prev_rows:
            prev_views = [v or 0 for v in prev_rows]
            prev_median = median(prev_views) if prev_views else 0
            if prev_median > 0:
                perf["historical_comparison"] = round(
                    (median(views_list) if views_list else 0) / prev_median, 2
                )

        results.append(perf)

    if len(results) == 1:
        return results[0]
    return {"platforms": results}


async def get_content_themes(
    db: AsyncSession,
    creator_id: int = 1,
    platform: str | None = None,
) -> dict:
    memories = (
        await db.scalars(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.is_active == True,
                ManagerMemory.category.like("content_cluster%"),
            ).order_by(ManagerMemory.updated_at.desc())
        )
    ).all()

    # Also include cross-platform winner/divergent observations
    xplat = (
        await db.scalars(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.is_active == True,
                ManagerMemory.category.like("xplat_%"),
            ).order_by(ManagerMemory.updated_at.desc())
        )
    ).all()

    # Also include IG cluster observations
    ig_clusters = (
        await db.scalars(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.is_active == True,
                ManagerMemory.category.like("ig_cluster_%"),
            ).order_by(ManagerMemory.updated_at.desc())
        )
    ).all()

    import re

    def _extract_theme(m: ManagerMemory) -> dict:
        metrics = m.metrics_considered or {}
        vs_median = None
        if isinstance(metrics, dict):
            vs_median = metrics.get("vs_median") or metrics.get("vs_median_likes") or metrics.get("vs_median_views")
        if vs_median is None:
            match = re.search(r"(\d+\.?\d*)x\b", m.statement)
            if match:
                vs_median = float(match.group(1))

        cat = m.category
        for prefix in ("content_clustering", "content_cluster_", "ig_cluster_", "xplat_winner_", "xplat_diverge_"):
            cat = cat.replace(prefix, "")
        cat = cat.strip("_: ") or m.category

        return {
            "theme": cat,
            "category": m.category,
            "statement": m.statement,
            "vs_median": vs_median,
            "sample_size": m.sample_size,
            "confidence": m.confidence,
            "evidence_post_ids": m.evidence_post_ids,
        }

    all_memories = list(memories) + list(xplat) + list(ig_clusters)
    themes = [_extract_theme(m) for m in all_memories]
    themes.sort(key=lambda t: (t["vs_median"] or 0), reverse=True)
    return {"themes": themes}


async def get_top_posts(
    db: AsyncSession,
    creator_id: int = 1,
    platform: str | None = None,
    metric: str = "views",
    limit: int = 10,
    content_theme: str | None = None,
) -> dict:
    if metric not in ALLOWED_METRICS:
        return {"error": f"Invalid metric '{metric}'. Allowed: {sorted(ALLOWED_METRICS)}"}
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50

    metric_col_map = {
        "views": PostMetric.views,
        "reach": PostMetric.reach,
        "likes": PostMetric.likes,
        "shares": PostMetric.shares,
        "saves": PostMetric.saves,
        "follows": PostMetric.followers_from_post,
        "profile_visits": PostMetric.profile_visits_from_post,
        "comments": PostMetric.comments_count,
    }

    query = (
        select(Post, PostMetric, PlatformAccount.platform, PlatformAccount.username)
        .join(PostMetric, PostMetric.post_id == Post.id)
        .join(PlatformAccount, PlatformAccount.id == Post.account_id)
        .where(PlatformAccount.creator_id == creator_id)
    )

    if platform:
        platform_lower = platform.lower()
        if platform_lower not in ("instagram", "tiktok", "youtube"):
            return {"error": f"Unknown platform: {platform}"}
        query = query.where(PlatformAccount.platform == Platform(platform_lower))

    if metric == "engagement_rate":
        # Sort by computed engagement rate; filter to posts with views > 0
        query = query.where(PostMetric.views > 0).order_by(
            (
                (func.coalesce(PostMetric.likes, 0) + func.coalesce(PostMetric.comments_count, 0) + func.coalesce(PostMetric.shares, 0))
                * 1.0 / PostMetric.views
            ).desc()
        )
    else:
        col = metric_col_map[metric]
        query = query.order_by(col.desc().nulls_last())

    query = query.limit(limit)
    result = await db.execute(query)

    from app.services.analysis import _classify_content

    posts = []
    for post, pm, plat, username in result:
        row = {
            "id": post.id,
            "platform": plat.value,
            "username": username,
            "post_type": post.post_type.value if post.post_type else None,
            "caption": (post.caption or "")[:120],
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "views": pm.views,
            "reach": pm.reach,
            "likes": pm.likes,
            "saves": pm.saves,
            "shares": pm.shares,
            "comments": pm.comments_count,
            "followers_from_post": pm.followers_from_post,
            "profile_visits": pm.profile_visits_from_post,
        }

        if pm.views and pm.views > 0:
            eng = (pm.likes or 0) + (pm.comments_count or 0) + (pm.shares or 0)
            row["engagement_rate"] = round(eng / pm.views * 100, 2)

        clusters = _classify_content(post.caption or "")
        row["content_themes"] = clusters

        posts.append(row)

    if content_theme:
        posts = [p for p in posts if content_theme in p.get("content_themes", [])]

    return {
        "metric": metric,
        "limit": limit,
        "platform": platform,
        "posts": posts,
    }


async def get_post_details(
    db: AsyncSession,
    post_id: int,
    creator_id: int = 1,
) -> dict:
    row = (
        await db.execute(
            select(Post, PlatformAccount)
            .join(PlatformAccount, PlatformAccount.id == Post.account_id)
            .where(
                Post.id == post_id,
                PlatformAccount.creator_id == creator_id,
            )
        )
    ).one_or_none()
    if not row:
        return {"error": f"Post {post_id} not found"}
    post, account = row

    metrics_result = await db.execute(
        select(PostMetric)
        .where(PostMetric.post_id == post_id)
        .order_by(PostMetric.captured_at.desc())
        .limit(1)
    )
    latest_metric = metrics_result.scalar_one_or_none()

    observations = (
        await db.scalars(
            select(ManagerMemory).where(
                ManagerMemory.creator_id == creator_id,
                ManagerMemory.is_active == True,
                ManagerMemory.evidence_post_ids.isnot(None),
            )
        )
    ).all()

    related_obs = []
    for obs in observations:
        if post_id in (obs.evidence_post_ids or []):
            related_obs.append({
                "id": obs.id,
                "type": obs.knowledge_type.value,
                "statement": obs.statement,
                "confidence": obs.confidence,
            })

    from app.services.analysis import _classify_content

    result = {
        "id": post.id,
        "platform": account.platform.value if account else None,
        "username": account.username if account else None,
        "post_type": post.post_type.value if post.post_type else None,
        "caption": post.caption,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "duration_seconds": post.duration_seconds,
        "is_pinned": post.is_pinned,
        "content_themes": _classify_content(post.caption or ""),
        "metrics": None,
        "observations": related_obs,
        "visual_analysis": None,
    }

    if latest_metric:
        result["metrics"] = {
            "views": latest_metric.views,
            "reach": latest_metric.reach,
            "likes": latest_metric.likes,
            "comments": latest_metric.comments_count,
            "shares": latest_metric.shares,
            "saves": latest_metric.saves,
            "followers_from_post": latest_metric.followers_from_post,
            "profile_visits": latest_metric.profile_visits_from_post,
            "avg_watch_time": latest_metric.avg_watch_time_seconds,
            "retention_rate": latest_metric.retention_rate,
            "completion_rate": latest_metric.completion_rate,
        }

    return result


async def search_posts(
    db: AsyncSession,
    creator_id: int = 1,
    query: str | None = None,
    platform: str | None = None,
    theme: str | None = None,
    min_views: int | None = None,
    min_likes: int | None = None,
    limit: int = 20,
) -> dict:
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50

    stmt = (
        select(Post, PostMetric, PlatformAccount.platform, PlatformAccount.username)
        .join(PostMetric, PostMetric.post_id == Post.id)
        .join(PlatformAccount, PlatformAccount.id == Post.account_id)
        .where(PlatformAccount.creator_id == creator_id)
    )

    if platform:
        platform_lower = platform.lower()
        if platform_lower not in ("instagram", "tiktok", "youtube"):
            return {"error": f"Unknown platform: {platform}"}
        stmt = stmt.where(PlatformAccount.platform == Platform(platform_lower))

    if query:
        stmt = stmt.where(Post.caption.ilike(f"%{query}%"))

    if min_views is not None:
        stmt = stmt.where(PostMetric.views >= min_views)

    if min_likes is not None:
        stmt = stmt.where(PostMetric.likes >= min_likes)

    # Theme filtering is post-query (needs caption classification), so fetch
    # all matching posts and filter in Python when a theme is specified.
    fetch_limit = 500 if theme else limit
    stmt = stmt.order_by(Post.published_at.desc().nulls_last()).limit(fetch_limit)

    result = await db.execute(stmt)

    from app.services.analysis import _classify_content

    posts = []
    for post, pm, plat, username in result:
        clusters = _classify_content(post.caption or "")

        if theme and theme not in clusters:
            continue

        posts.append({
            "id": post.id,
            "platform": plat.value,
            "username": username,
            "post_type": post.post_type.value if post.post_type else None,
            "caption": (post.caption or "")[:120],
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "content_themes": clusters,
            "views": pm.views,
            "reach": pm.reach,
            "likes": pm.likes,
            "saves": pm.saves,
            "shares": pm.shares,
            "comments": pm.comments_count,
            "followers_from_post": pm.followers_from_post,
        })

        if len(posts) >= limit:
            break

    return {
        "query": query,
        "platform": platform,
        "theme": theme,
        "count": len(posts),
        "posts": posts,
    }


async def get_manager_memory(
    db: AsyncSession,
    creator_id: int = 1,
    knowledge_type: str | None = None,
    platform: str | None = None,
    limit: int = 30,
) -> dict:
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100

    stmt = (
        select(ManagerMemory)
        .where(
            ManagerMemory.creator_id == creator_id,
            ManagerMemory.is_active == True,
        )
    )

    if knowledge_type:
        kt_upper = knowledge_type.upper()
        valid_types = {t.value.upper(): t for t in KnowledgeType}
        if kt_upper not in valid_types:
            return {"error": f"Invalid knowledge_type '{knowledge_type}'. Valid: fact, observation, hypothesis"}
        stmt = stmt.where(ManagerMemory.knowledge_type == valid_types[kt_upper])

    if platform:
        platform_lower = platform.lower()
        stmt = stmt.where(
            ManagerMemory.category.ilike(f"%{platform_lower}%")
            | ManagerMemory.statement.ilike(f"%{platform_lower}%")
        )

    stmt = stmt.order_by(ManagerMemory.confidence.desc().nulls_last()).limit(limit)
    memories = (await db.scalars(stmt)).all()

    return {
        "count": len(memories),
        "memories": [
            {
                "id": m.id,
                "type": m.knowledge_type.value,
                "category": m.category,
                "statement": m.statement,
                "confidence": m.confidence,
                "sample_size": m.sample_size,
                "evidence_post_ids": m.evidence_post_ids,
                "metrics_considered": m.metrics_considered,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in memories
        ],
    }
