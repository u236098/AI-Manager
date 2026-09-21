"""Instagram Graph API integration (Facebook Login for Business route)."""
from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.core import Platform, PlatformAccount


def _graph_url() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_version}"


async def _json_or_raise(resp: httpx.Response) -> dict:
    data = resp.json()
    if resp.is_error or data.get("error"):
        message = data.get("error", {}).get("message") or resp.text
        raise RuntimeError(f"Meta Graph API error: {message}")
    return data


async def connect_with_user_token(user_token: str, creator_id: int, db: AsyncSession) -> dict:
    """Discover the connected Page + Instagram professional account and persist it.

    Meta's Business Login flow already returns a long-lived user token. The user
    token is retained for Instagram Graph API reads; the Page token returned by
    /me/accounts is used only while discovering the linked Instagram account.
    """
    graph = _graph_url()
    import logging
    log = logging.getLogger("kobby.instagram")

    async with httpx.AsyncClient(timeout=30) as client:
        me_resp = await client.get(
            f"{graph}/me",
            params={"fields": "id,name", "access_token": user_token},
        )
        me_data = me_resp.json()
        log.warning("META /me response: %s", me_data)

        pages_resp = await client.get(
            f"{graph}/me/accounts",
            params={
                "fields": "id,name,access_token,instagram_business_account",
                "access_token": user_token,
            },
        )
        pages_data = pages_resp.json()
        log.warning("META /me/accounts response: %s", {k: v for k, v in pages_data.items() if k != "data"})
        log.warning("META /me/accounts pages count: %d", len(pages_data.get("data", [])))
        for p in pages_data.get("data", []):
            log.warning("  Page: id=%s name=%s ig=%s", p.get("id"), p.get("name"), p.get("instagram_business_account"))
        if pages_data.get("error"):
            return {
                "error": "Meta API error on /me/accounts",
                "detail": pages_data["error"].get("message"),
                "me": me_data,
                "raw_pages_response": pages_data,
            }

        pages = pages_data.get("data", [])
        linked = [p for p in pages if p.get("instagram_business_account", {}).get("id")]
        if not linked:
            return {
                "error": "No Facebook Page with a linked Instagram professional account",
                "me": me_data,
                "pages_returned": len(pages),
                "pages": [
                    {"id": p.get("id"), "name": p.get("name"), "has_ig": bool(p.get("instagram_business_account"))}
                    for p in pages
                ],
                "hint": "Check that pages_show_list permission was granted and that a Page is linked to an IG professional account",
            }

        if len(linked) > 1:
            return {
                "selection_required": True,
                "pages": [
                    {
                        "page_id": p["id"],
                        "page_name": p.get("name"),
                        "instagram_account_id": p["instagram_business_account"]["id"],
                    }
                    for p in linked
                ],
            }

        page = linked[0]
        ig_account_id = page["instagram_business_account"]["id"]
        profile_resp = await client.get(
            f"{graph}/{ig_account_id}",
            params={
                "fields": "username,name,biography,profile_picture_url,followers_count,follows_count,media_count",
                "access_token": user_token,
            },
        )
        profile = await _json_or_raise(profile_resp)

    existing = await db.scalar(
        select(PlatformAccount).where(
            PlatformAccount.platform == Platform.INSTAGRAM,
            PlatformAccount.platform_user_id == ig_account_id,
        )
    )
    if existing:
        account = existing
        account.creator_id = creator_id
        account.username = profile.get("username", account.username)
        account.display_name = profile.get("name")
        account.access_token = user_token
        account.is_active = True
    else:
        account = PlatformAccount(
            creator_id=creator_id,
            platform=Platform.INSTAGRAM,
            platform_user_id=ig_account_id,
            username=profile.get("username", ""),
            display_name=profile.get("name"),
            access_token=user_token,
        )
        db.add(account)

    await db.commit()
    await db.refresh(account)
    return {
        "account_id": account.id,
        "platform": "instagram",
        "username": account.username,
        "followers": profile.get("followers_count"),
        "facebook_page_id": page["id"],
        "facebook_page_name": page.get("name"),
    }


async def fetch_media(account: PlatformAccount, limit: int = 50) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_graph_url()}/{account.platform_user_id}/media",
            params={
                "fields": "id,caption,media_type,media_url,thumbnail_url,timestamp,like_count,comments_count,permalink",
                "limit": limit,
                "access_token": account.access_token,
            },
        )
        data = await _json_or_raise(resp)
        return data.get("data", [])


INSIGHTS_CAROUSEL_FEED = "reach,saved,shares,likes,comments,views,follows,profile_visits"
INSIGHTS_REEL = "reach,saved,shares,likes,comments,views,ig_reels_avg_watch_time,total_interactions"


async def fetch_media_insights(media_id: str, access_token: str, is_reel: bool = False) -> dict:
    metric_str = INSIGHTS_REEL if is_reel else INSIGHTS_CAROUSEL_FEED
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_graph_url()}/{media_id}/insights",
            params={
                "metric": metric_str,
                "access_token": access_token,
            },
        )
        data = await _json_or_raise(resp)
        metrics = {}
        for item in data.get("data", []):
            metrics[item["name"]] = item["values"][0]["value"] if item.get("values") else None
        return metrics


async def fetch_account_insights(account: PlatformAccount) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_graph_url()}/{account.platform_user_id}/insights",
            params={
                "metric": "reach,impressions,profile_views,follower_count",
                "period": "day",
                "access_token": account.access_token,
            },
        )
        data = await _json_or_raise(resp)
        metrics = {}
        for item in data.get("data", []):
            values = item.get("values", [])
            if values:
                metrics[item["name"]] = values[-1]["value"]
        return metrics
