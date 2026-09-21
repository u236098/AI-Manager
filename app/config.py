from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://kobby:kobby@127.0.0.1:5432/kobby_manager"
    redis_url: str = "redis://localhost:6379/0"

    # AI layer — OpenAI as sole provider, routed by cost tier
    strategy_provider: str = "openai"
    strategy_model: str = "gpt-5.6-sol"
    analysis_provider: str = "openai"
    analysis_model: str = "gpt-5.6-terra"
    routine_provider: str = "openai"
    routine_model: str = "gpt-5.6-luna"
    vision_provider: str = "openai"
    vision_model: str = "gpt-5.6-terra"
    transcribe_model: str = "gpt-4o-transcribe"

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # platform credentials
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_graph_version: str = "v26.0"
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""

    secret_key: str = "change-me-in-production"
    oauth_state_ttl_seconds: int = 600

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
