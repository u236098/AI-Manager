"""Authentication — OAuth flows for Instagram and TikTok."""
from __future__ import annotations

import hashlib
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.oauth_session import pop_oauth_session, put_oauth_session
from app.services.oauth_state import generate_state, validate_state

router = APIRouter()


def _redirect_uri(provider: str) -> str:
    from app.config import get_settings
    return f"{get_settings().base_url}/api/auth/{provider}/callback"


@router.get("/instagram/connect")
async def instagram_auth_url(
    creator_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Build Meta's current Facebook Login for Business Instagram onboarding URL."""
    from app.config import get_settings

    s = get_settings()
    state = generate_state()
    await put_oauth_session(state, db, provider="instagram", creator_id=creator_id)
    redirect_uri = _redirect_uri("instagram")
    scope = ",".join(
        [
            "instagram_basic",
            "instagram_manage_insights",
            "pages_show_list",
            "pages_read_engagement",
        ]
    )
    params = {
        "client_id": s.meta_app_id,
        "display": "page",
        "extras": '{"setup":{"channel":"IG_API_ONBOARDING"}}',
        "redirect_uri": redirect_uri,
        "response_type": "token",
        "scope": scope,
        "state": state,
    }
    url = f"https://www.facebook.com/{s.meta_graph_version}/dialog/oauth?{urlencode(params)}"
    return {"auth_url": url, "state": state}


@router.get("/instagram/callback", response_class=HTMLResponse)
async def instagram_callback_page():
    """Browser bridge for Meta's implicit response, whose tokens arrive in #fragment."""
    return HTMLResponse(
        """<!doctype html>
<html><head><meta charset="utf-8"><title>Kobby Manager — Instagram</title></head>
<body><p id="status">Completing Instagram connection…</p>
<script>
(async () => {
  const hash = new URLSearchParams(location.hash.slice(1));
  const query = new URLSearchParams(location.search);
  const get = (k) => hash.get(k) || query.get(k);
  const token = get('long_lived_token') || get('access_token');
  const state = get('state');
  const error = get('error_description') || get('error');
  const el = document.getElementById('status');
  if (error) { el.textContent = 'Instagram authorization failed: ' + error; return; }
  if (!token || !state) {
    el.textContent = 'Instagram callback is missing the access token or OAuth state.';
    return;
  }
  const response = await fetch('/api/auth/instagram/complete', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({access_token: token, state})
  });
  const data = await response.json();
  if (!response.ok) { el.textContent = 'Connection failed: ' + (data.detail || JSON.stringify(data)); return; }
  if (data.error) { el.textContent = 'Connection issue: ' + JSON.stringify(data, null, 2); return; }
  el.textContent = 'Instagram connected: @' + (data.username || 'unknown') + '. You can close this tab.';
  history.replaceState(null, '', location.pathname);
})().catch(err => { document.getElementById('status').textContent = 'Connection failed: ' + err; });
</script></body></html>"""
    )


class InstagramComplete(BaseModel):
    access_token: str
    state: str


@router.post("/instagram/complete")
async def instagram_complete(payload: InstagramComplete, db: AsyncSession = Depends(get_db)):
    if not validate_state(payload.state):
        raise HTTPException(403, "Invalid or expired OAuth state — possible CSRF attack")
    session = await pop_oauth_session(payload.state, db)
    if not session or session.get("provider") != "instagram":
        raise HTTPException(403, "OAuth transaction is missing, expired, or already used")

    from app.services.instagram import connect_with_user_token

    return await connect_with_user_token(payload.access_token, int(session["creator_id"]), db)


@router.get("/tiktok/connect")
async def tiktok_auth_url(
    creator_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Build TikTok Desktop OAuth URL using PKCE as required by the sandbox setup."""
    from app.config import get_settings

    s = get_settings()
    state = generate_state()
    code_verifier = secrets.token_urlsafe(64)[:96]
    code_challenge = hashlib.sha256(code_verifier.encode()).hexdigest()
    await put_oauth_session(
        state,
        db,
        provider="tiktok",
        creator_id=creator_id,
        code_verifier=code_verifier,
    )
    redirect_uri = _redirect_uri("tiktok")
    params = {
        "client_key": s.tiktok_client_key,
        "redirect_uri": redirect_uri,
        "scope": "user.info.basic,user.info.profile,user.info.stats,video.list",
        "response_type": "code",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    url = f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"
    return {"auth_url": url, "state": state}


@router.get("/tiktok/callback")
async def tiktok_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if not validate_state(state):
        raise HTTPException(403, "Invalid or expired OAuth state — possible CSRF attack")
    session = await pop_oauth_session(state, db)
    if not session or session.get("provider") != "tiktok":
        raise HTTPException(403, "OAuth transaction is missing, expired, or already used")

    from app.services.tiktok import exchange_code_for_token

    return await exchange_code_for_token(
        code,
        str(session["code_verifier"]),
        int(session["creator_id"]),
        db,
    )
