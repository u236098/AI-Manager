from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, accounts, posts, analytics, content, manager, brand, dashboard
from app.mcp import mcp as mcp_server

_mcp_http_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    stateless_http=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    title="Kobby Manager",
    description="Deterministic analytics platform for Kobby Cooper",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
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

from mcp.server.streamable_http_manager import StreamableHTTPASGIApp
app.mount("/mcp", StreamableHTTPASGIApp(mcp_server.session_manager))


@app.get("/api/health")
async def health():
    return {"status": "ok"}
