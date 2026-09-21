"""Sync platform data into posts, post_metrics, and account snapshots."""
from __future__ import annotations

import re
from datetime import datetime, timezone, date

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.core import (
    AccountMetricSnapshot,
    Platform,
    PlatformAccount,
    Post,
    PostMetric,
    PostType,
    ProfileSnapshot,
)
from app.services.tiktok import TIKTOK_API_URL
from app.services.instagram import fetch_media, fetch_media_insights, fetch_account_insights, _graph_url, _json_or_raise

HASHTAG_RE = re.compile(r"#(\w+)")


async def _fetch_all_tiktok_videos(account: PlatformAccount) -> list[dict]:
    from app.services.encryption import decrypt_token
    token = decrypt_token(account.access_token)
    fields = (
        "id,title,video_description,create_time,duration,"
        "cover_image_url,share_url,like_count,comment_count,share_count,view_count"
    )
    videos: list[dict] = []
    cursor: int | None = None
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            body: dict = {"max_count": 20}
            if cursor is not None:
                body["cursor"] = cursor
            resp = await client.post(
                f"{TIKTOK_API_URL}/video/list/",
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": fields},
                json=body,
            )
            data = resp.json()
            batch = data.get("data", {}).get("videos", [])
            videos.extend(batch)
            if not data.get("data", {}).get("has_more"):
                break
            cursor = data["data"].get("cursor")
            if cursor is None:
                break
    return videos


async def _fetch_tiktok_profile(account: PlatformAccount) -> dict:
    from app.services.encryption import decrypt_token
    token = decrypt_token(account.access_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{TIKTOK_API_URL}/user/info/",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "fields": "open_id,display_name,username,follower_count,"
                "following_count,likes_count,video_count,bio_description,"
                "avatar_url"
            },
        )
        return resp.json().get("data", {}).get("user", {})


def _extract_hashtags(text: str | None) -> list[str]:
    if not text:
        return []
    return HASHTAG_RE.findall(text)


async def sync_tiktok_account(account_id: int, db: AsyncSession) -> dict:
    """Full sync: import all videos + current metrics + profile snapshot."""
    account = await db.get(PlatformAccount, account_id)
    if not account or account.platform != Platform.TIKTOK:
        raise ValueError(f"Account {account_id} is not a TikTok account")

    now = datetime.now(timezone.utc)
    today = date.today()

    profile = await _fetch_tiktok_profile(account)
    videos = await _fetch_all_tiktok_videos(account)

    existing_posts = {
        row.platform_post_id: row
        for row in (
            await db.scalars(
                select(Post).where(
                    Post.account_id == account_id,
                    Post.platform_post_id.in_([v["id"] for v in videos]),
                )
            )
        ).all()
    }

    posts_created = 0
    posts_updated = 0
    metrics_created = 0

    for v in videos:
        vid = v["id"]
        caption = v.get("video_description") or v.get("title") or ""
        published = datetime.fromtimestamp(v["create_time"], tz=timezone.utc)
        hours_age = (now - published).total_seconds() / 3600

        if vid in existing_posts:
            post = existing_posts[vid]
            post.caption = caption
            post.thumbnail_url = v.get("cover_image_url")
            post.duration_seconds = v.get("duration") or None
            posts_updated += 1
        else:
            post = Post(
                account_id=account_id,
                platform_post_id=vid,
                post_type=PostType.TIKTOK_VIDEO,
                caption=caption,
                hashtags=_extract_hashtags(caption),
                media_url=v.get("share_url"),
                thumbnail_url=v.get("cover_image_url"),
                duration_seconds=v.get("duration") or None,
                published_at=published,
                is_pinned=False,
            )
            db.add(post)
            posts_created += 1

        await db.flush()

        metric = PostMetric(
            post_id=post.id,
            captured_at=now,
            hours_after_publish=round(hours_age, 1),
            views=v.get("view_count"),
            likes=v.get("like_count"),
            comments_count=v.get("comment_count"),
            shares=v.get("share_count"),
        )
        db.add(metric)
        metrics_created += 1

    profile_snap = ProfileSnapshot(
        account_id=account_id,
        username=profile.get("username", account.username),
        display_name=profile.get("display_name"),
        bio=profile.get("bio_description"),
        profile_pic_url=profile.get("avatar_url"),
        follower_count=profile.get("follower_count"),
        following_count=profile.get("following_count"),
        post_count=profile.get("video_count"),
    )
    db.add(profile_snap)

    existing_snap = await db.scalar(
        select(AccountMetricSnapshot).where(
            AccountMetricSnapshot.account_id == account_id,
            AccountMetricSnapshot.date == today,
        )
    )
    if not existing_snap:
        account_snap = AccountMetricSnapshot(
            account_id=account_id,
            date=today,
            followers=profile.get("follower_count"),
            following=profile.get("following_count"),
            posts_count=profile.get("video_count"),
            extra={"likes_count": profile.get("likes_count")},
        )
        db.add(account_snap)

    await db.commit()

    return {
        "account": account.username,
        "videos_fetched": len(videos),
        "posts_created": posts_created,
        "posts_updated": posts_updated,
        "metrics_snapshots": metrics_created,
        "profile_snapshot": True,
        "follower_count": profile.get("follower_count"),
        "video_count": profile.get("video_count"),
    }


MEDIA_TYPE_MAP = {
    "IMAGE": PostType.FEED,
    "VIDEO": PostType.REEL,
    "CAROUSEL_ALBUM": PostType.CAROUSEL,
}


async def _fetch_ig_profile(account: PlatformAccount) -> dict:
    from app.services.encryption import decrypt_token
    graph = _graph_url()
    token = decrypt_token(account.access_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{graph}/{account.platform_user_id}",
            params={
                "fields": "username,name,biography,profile_picture_url,followers_count,follows_count,media_count",
                "access_token": token,
            },
        )
        return await _json_or_raise(resp)


async def _fetch_all_ig_media(account: PlatformAccount) -> list[dict]:
    from app.services.encryption import decrypt_token
    graph = _graph_url()
    token = decrypt_token(account.access_token)
    media: list[dict] = []
    fields = "id,caption,media_type,media_url,thumbnail_url,timestamp,like_count,comments_count,permalink"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{graph}/{account.platform_user_id}/media",
            params={"fields": fields, "limit": 50, "access_token": token},
        )
        data = await _json_or_raise(resp)
        media.extend(data.get("data", []))
        while data.get("paging", {}).get("next"):
            resp = await client.get(data["paging"]["next"])
            data = await _json_or_raise(resp)
            media.extend(data.get("data", []))
    return media


async def sync_instagram_account(account_id: int, db: AsyncSession) -> dict:
    """Full sync: import all IG media + current metrics + profile snapshot."""
    account = await db.get(PlatformAccount, account_id)
    if not account or account.platform != Platform.INSTAGRAM:
        raise ValueError(f"Account {account_id} is not an Instagram account")

    now = datetime.now(timezone.utc)
    today = date.today()

    profile = await _fetch_ig_profile(account)
    media_items = await _fetch_all_ig_media(account)

    existing_posts = {
        row.platform_post_id: row
        for row in (
            await db.scalars(
                select(Post).where(
                    Post.account_id == account_id,
                    Post.platform_post_id.in_([m["id"] for m in media_items]),
                )
            )
        ).all()
    }

    posts_created = 0
    posts_updated = 0
    metrics_created = 0

    for m in media_items:
        mid = m["id"]
        caption = m.get("caption") or ""
        published = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")) if m.get("timestamp") else now
        hours_age = (now - published).total_seconds() / 3600
        post_type = MEDIA_TYPE_MAP.get(m.get("media_type", ""), PostType.FEED)

        if mid in existing_posts:
            post = existing_posts[mid]
            post.caption = caption
            post.thumbnail_url = m.get("thumbnail_url") or m.get("media_url")
            posts_updated += 1
        else:
            post = Post(
                account_id=account_id,
                platform_post_id=mid,
                post_type=post_type,
                caption=caption,
                hashtags=_extract_hashtags(caption),
                media_url=m.get("permalink"),
                thumbnail_url=m.get("thumbnail_url") or m.get("media_url"),
                published_at=published,
                is_pinned=False,
            )
            db.add(post)
            posts_created += 1

        await db.flush()

        metric = PostMetric(
            post_id=post.id,
            captured_at=now,
            hours_after_publish=round(hours_age, 1),
            likes=m.get("like_count"),
            comments_count=m.get("comments_count"),
        )
        db.add(metric)
        metrics_created += 1

    profile_snap = ProfileSnapshot(
        account_id=account_id,
        username=profile.get("username", account.username),
        display_name=profile.get("name"),
        bio=profile.get("biography"),
        profile_pic_url=profile.get("profile_picture_url"),
        follower_count=profile.get("followers_count"),
        following_count=profile.get("follows_count"),
        post_count=profile.get("media_count"),
    )
    db.add(profile_snap)

    existing_snap = await db.scalar(
        select(AccountMetricSnapshot).where(
            AccountMetricSnapshot.account_id == account_id,
            AccountMetricSnapshot.date == today,
        )
    )
    if not existing_snap:
        account_snap = AccountMetricSnapshot(
            account_id=account_id,
            date=today,
            followers=profile.get("followers_count"),
            following=profile.get("follows_count"),
            posts_count=profile.get("media_count"),
        )
        db.add(account_snap)

    await db.commit()

    return {
        "account": account.username,
        "platform": "instagram",
        "media_fetched": len(media_items),
        "posts_created": posts_created,
        "posts_updated": posts_updated,
        "metrics_snapshots": metrics_created,
        "profile_snapshot": True,
        "follower_count": profile.get("followers_count"),
        "media_count": profile.get("media_count"),
    }


async def enrich_ig_insights(account_id: int, db: AsyncSession) -> dict:
    """Fetch per-post insights (reach, views, saves, shares, follows, profile_visits)
    for all Instagram posts and update existing PostMetric rows."""
    import asyncio
    import logging

    log = logging.getLogger("kobby.sync")
    account = await db.get(PlatformAccount, account_id)
    if not account or account.platform != Platform.INSTAGRAM:
        raise ValueError(f"Account {account_id} is not an Instagram account")

    posts = (
        await db.scalars(
            select(Post).where(Post.account_id == account_id)
        )
    ).all()

    enriched = 0
    failed = 0
    skipped = 0

    for i, post in enumerate(posts):
        latest_metric = (
            await db.scalars(
                select(PostMetric)
                .where(PostMetric.post_id == post.id)
                .order_by(PostMetric.captured_at.desc())
                .limit(1)
            )
        ).first()

        if not latest_metric:
            skipped += 1
            continue

        if latest_metric.reach is not None:
            skipped += 1
            continue

        is_reel = post.post_type == PostType.REEL

        try:
            from app.services.encryption import decrypt_token
            insights = await fetch_media_insights(
                post.platform_post_id, decrypt_token(account.access_token), is_reel=is_reel
            )
        except Exception as e:
            log.warning("Insights failed for post %s (%s): %s", post.platform_post_id, post.post_type.value, e)
            failed += 1
            continue

        if insights.get("reach") is not None:
            latest_metric.reach = insights["reach"]
        if insights.get("views") is not None:
            latest_metric.views = insights["views"]
        if insights.get("saved") is not None:
            latest_metric.saves = insights["saved"]
        if insights.get("shares") is not None:
            latest_metric.shares = insights["shares"]
        if insights.get("likes") is not None:
            latest_metric.likes = insights["likes"]
        if insights.get("comments") is not None:
            latest_metric.comments_count = insights["comments"]
        if not is_reel:
            if insights.get("follows") is not None:
                latest_metric.followers_from_post = insights["follows"]
            if insights.get("profile_visits") is not None:
                latest_metric.profile_visits_from_post = insights["profile_visits"]
        if is_reel and insights.get("ig_reels_avg_watch_time") is not None:
            latest_metric.avg_watch_time_seconds = insights["ig_reels_avg_watch_time"] / 1000.0

        enriched += 1

        if (i + 1) % 25 == 0:
            await db.flush()
            log.info("Enriched %d/%d posts", i + 1, len(posts))

        await asyncio.sleep(0.3)

    await db.commit()
    return {
        "account": account.username,
        "total_posts": len(posts),
        "enriched": enriched,
        "failed": failed,
        "skipped": skipped,
    }


async def sync_account(account_id: int, db: AsyncSession) -> dict:
    """Route to the correct platform sync."""
    account = await db.get(PlatformAccount, account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")
    if account.platform == Platform.TIKTOK:
        return await sync_tiktok_account(account_id, db)
    if account.platform == Platform.INSTAGRAM:
        return await sync_instagram_account(account_id, db)
    raise ValueError(f"Unsupported platform: {account.platform}")
