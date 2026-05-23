from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "نظام إدارة المعرفة القانونية"
    env: Literal["dev", "demo", "test"] = "dev"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://suhaiman:suhaiman@postgres:5432/suhaiman_km"
    jwt_issuer: str = "suhaiman-km-poc"
    jwt_audience: str = "suhaiman-km"
    jwt_private_key: str | None = None
    jwt_public_key: str | None = None
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    openai_api_key: str | None = None
    llm_required: bool = False
    llm_model: str = "gpt-5"
    llm_fallback_model: str = "gpt-4.1"
    llm_timeout_ms: int = 30000


@lru_cache
def get_settings() -> Settings:
    return Settings()
