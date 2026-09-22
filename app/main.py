from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp

from app.api import auth, accounts, posts, analytics, content, manager, brand, dashboard, cron
from app.auth import MCPAuthMiddleware
from app.config import get_settings
from app.database import _get_session_factory
from app.mcp import mcp as mcp_server

_mcp_http_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    stateless_http=True,
    host="0.0.0.0",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    title="Kobby Manager",
    description="Deterministic analytics platform for Kobby Cooper",
    version="0.3.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(manager.router, prefix="/api/manager", tags=["manager"])
app.include_router(brand.router, prefix="/api/brand", tags=["brand"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(cron.router, prefix="/api/cron", tags=["cron"])

mcp_asgi = StreamableHTTPASGIApp(mcp_server.session_manager)
app.mount("/mcp", MCPAuthMiddleware(mcp_asgi, _get_session_factory()))


@app.get("/.well-known/oauth-protected-resource")
@app.get("/.well-known/oauth-protected-resource/mcp")
async def mcp_protected_resource_metadata():
    """RFC 9728 metadata used by ChatGPT to discover Clerk OAuth."""
    return {
        "resource": settings.canonical_mcp_resource_url,
        "authorization_servers": [settings.clerk_issuer_url],
        "scopes_supported": ["openid", "profile", "email", "offline_access"],
        "resource_documentation": settings.base_url.rstrip("/"),
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}
