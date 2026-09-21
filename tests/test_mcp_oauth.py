"""ChatGPT MCP OAuth discovery, challenge, and token-policy tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.auth import MCP_SCOPES, _send_error, verify_mcp_token
from app.config import Settings


def test_mcp_resource_and_clerk_issuer_are_derived_from_public_urls():
    settings = Settings(
        _env_file=None,
        base_url="https://kobby-manager.vercel.app/",
        clerk_jwks_url=(
            "https://exact-redbird-5388.clerk.accounts.dev/"
            ".well-known/jwks.json"
        ),
    )

    assert settings.canonical_mcp_resource_url == (
        "https://kobby-manager.vercel.app/mcp/"
    )
    assert settings.clerk_issuer_url == (
        "https://exact-redbird-5388.clerk.accounts.dev"
    )


async def test_protected_resource_metadata_points_to_clerk(monkeypatch):
    import app.main as main

    fake_settings = SimpleNamespace(
        canonical_mcp_resource_url="https://kobby-manager.vercel.app/mcp/",
        clerk_issuer_url="https://exact-redbird-5388.clerk.accounts.dev",
        base_url="https://kobby-manager.vercel.app",
    )
    monkeypatch.setattr(main, "settings", fake_settings)

    metadata = await main.mcp_protected_resource_metadata()

    assert metadata["resource"] == "https://kobby-manager.vercel.app/mcp/"
    assert metadata["authorization_servers"] == [
        "https://exact-redbird-5388.clerk.accounts.dev"
    ]
    assert "offline_access" in metadata["scopes_supported"]


async def test_unauthenticated_mcp_response_advertises_oauth_metadata():
    events = []

    async def send(event):
        events.append(event)

    fake_settings = SimpleNamespace(
        base_url="https://kobby-manager.vercel.app",
    )
    with patch("app.config.get_settings", return_value=fake_settings):
        await _send_error(
            send,
            401,
            "Missing authorization token",
            oauth_error="invalid_token",
        )

    headers = dict(events[0]["headers"])
    challenge = headers[b"www-authenticate"].decode()
    assert events[0]["status"] == 401
    assert "oauth-protected-resource" in challenge
    assert f'scope="{" ".join(MCP_SCOPES)}"' in challenge
    assert 'error="invalid_token"' in challenge


def test_mcp_token_accepts_chatgpt_cimd_audience_and_openid_scope():
    fake_settings = SimpleNamespace(
        clerk_issuer_url="https://issuer.example",
        canonical_mcp_resource_url="https://kobby-manager.vercel.app/mcp/",
        mcp_oauth_client_id="https://chatgpt.com/oauth/client.json",
    )
    claims = {
        "sub": "user_123",
        "aud": "https://chatgpt.com/oauth/client.json",
        "scope": "openid profile email offline_access",
    }

    with (
        patch("app.config.get_settings", return_value=fake_settings),
        patch("app.auth.verify_clerk_token", return_value=claims),
    ):
        assert verify_mcp_token("token") == claims


@pytest.mark.parametrize(
    "claims",
    [
        {
            "sub": "user_123",
            "aud": "wrong-client",
            "scope": "openid profile email",
        },
        {
            "sub": "user_123",
            "aud": "https://chatgpt.com/oauth/client.json",
            "scope": "profile email",
        },
    ],
)
def test_mcp_token_rejects_wrong_audience_or_missing_scope(claims):
    fake_settings = SimpleNamespace(
        clerk_issuer_url="https://issuer.example",
        canonical_mcp_resource_url="https://kobby-manager.vercel.app/mcp/",
        mcp_oauth_client_id="https://chatgpt.com/oauth/client.json",
    )

    with (
        patch("app.config.get_settings", return_value=fake_settings),
        patch("app.auth.verify_clerk_token", return_value=claims),
        pytest.raises(ValueError),
    ):
        verify_mcp_token("token")


async def test_all_mcp_tools_advertise_oauth_security_scheme():
    from app.mcp.server import mcp

    tools = await mcp.list_tools()
    assert len(tools) == 8
    for tool in tools:
        assert tool.meta == {
            "securitySchemes": [
                {
                    "type": "oauth2",
                    "scopes": ["openid", "profile", "email", "offline_access"],
                }
            ]
        }
