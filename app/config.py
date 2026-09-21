from pydantic_settings import BaseSettings
from functools import lru_cache


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

    # Comma-separated allowed CORS origins (production)
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def async_database_url(self) -> str:
        """Ensure the URL uses the asyncpg driver."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic migrations."""
        url = self.database_url
        if "+asyncpg" in url:
            url = url.replace("+asyncpg", "", 1)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
