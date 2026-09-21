"""TikTok API integration via Display API and Content Posting API."""
from __future__ import annotations
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models.core import PlatformAccount, Platform

TIKTOK_API_URL = "https://open.tiktokapis.com/v2"


async def exchange_code_for_token(code: str, code_verifier: str, creator_id: int, db: AsyncSession) -> dict:
    s = get_settings()
    redirect_uri = "http://localhost:8000/api/auth/tiktok/callback"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TIKTOK_API_URL}/oauth/token/",
            data={
                "client_key": s.tiktok_client_key,
                "client_secret": s.tiktok_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        token_data = resp.json()

        access_token = token_data.get("access_token")
        open_id = token_data.get("open_id")
        refresh_token = token_data.get("refresh_token")

        user_resp = await client.get(
            f"{TIKTOK_API_URL}/user/info/",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "open_id,union_id,avatar_url,display_name,username,follower_count,following_count,likes_count,video_count"},
        )
        user_data = user_resp.json().get("data", {}).get("user", {})

    account = PlatformAccount(
        creator_id=creator_id,
        platform=Platform.TIKTOK,
        platform_user_id=open_id,
        username=user_data.get("username", ""),
        display_name=user_data.get("display_name"),
        access_token=access_token,
        refresh_token=refresh_token,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    return {
        "account_id": account.id,
        "platform": "tiktok",
        "username": account.username,
        "followers": user_data.get("follower_count"),
    }


async def fetch_videos(account: PlatformAccount, max_count: int = 20) -> list[dict]:
    """Fetch user's videos via the TikTok Display API."""
    fields = "id,title,video_description,create_time,duration,cover_image_url,share_url,like_count,comment_count,share_count,view_count"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TIKTOK_API_URL}/video/list/",
            headers={"Authorization": f"Bearer {account.access_token}"},
            params={"fields": fields},
            json={"max_count": max_count},
        )
        data = resp.json()
        return data.get("data", {}).get("videos", [])


async def refresh_access_token(account: PlatformAccount, db: AsyncSession) -> str:
    """Refresh an expired TikTok access token."""
    s = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TIKTOK_API_URL}/oauth/token/",
            data={
                "client_key": s.tiktok_client_key,
                "client_secret": s.tiktok_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": account.refresh_token,
            },
        )
        data = resp.json()
        account.access_token = data["access_token"]
        account.refresh_token = data.get("refresh_token", account.refresh_token)
        await db.commit()
        return account.access_token
