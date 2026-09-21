from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from pydantic_settings import BaseSettings
from functools import lru_cache

ASYNCPG_STRIP_PARAMS = {"channel_binding", "sslmode"}


def _clean_url_for_asyncpg(url: str) -> str:
    """Strip query params that asyncpg doesn't understand and convert sslmode to ssl."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    params = parse_qs(parsed.query)
    sslmode = params.pop("sslmode", [None])[0]
    cleaned = {k: v for k, v in params.items() if k not in ASYNCPG_STRIP_PARAMS}
    if sslmode and sslmode == "require":
        cleaned["ssl"] = ["require"]
    new_query = urlencode(cleaned, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://kobby:kobby@127.0.0.1:5432/kobby_manager"
    redis_url: str = "redis://localhost:6379/0"

    # platform credentials
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_graph_version: str = "v26.0"
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""

    secret_key: str = "change-me-in-production"
    oauth_state_ttl_seconds: int = 600

    # Token encryption key (Fernet, 32-byte base64-encoded)
    encryption_key: str = ""

    # Base URL for OAuth callbacks (no trailing slash)
    base_url: str = "http://localhost:8000"

    # Clerk auth (leave empty to disable auth in local dev)
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""

    # ChatGPT MCP OAuth configuration. The resource URL must exactly match
    # the public MCP endpoint used when creating the ChatGPT connection.
    mcp_resource_url: str = ""
    mcp_oauth_client_id: str = "https://chatgpt.com/oauth/client.json"

    # Comma-separated allowed CORS origins (production)
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def async_database_url(self) -> str:
        """Ensure the URL uses the asyncpg driver and strip unsupported params."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return _clean_url_for_asyncpg(url)

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic migrations."""
        url = self.database_url
        if "+asyncpg" in url:
            url = url.replace("+asyncpg", "", 1)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def clerk_issuer_url(self) -> str:
        """Return Clerk's canonical OAuth/OIDC issuer URL."""
        if self.clerk_issuer:
            return self.clerk_issuer.rstrip("/")
        marker = "/.well-known/"
        if marker in self.clerk_jwks_url:
            return self.clerk_jwks_url.split(marker, 1)[0].rstrip("/")
        return ""

    @property
    def canonical_mcp_resource_url(self) -> str:
        """Return the exact public MCP resource identifier."""
        if self.mcp_resource_url:
            return self.mcp_resource_url.rstrip("/") + "/"
        return f"{self.base_url.rstrip('/')}/mcp/"


@lru_cache
def get_settings() -> Settings:
    return Settings()
