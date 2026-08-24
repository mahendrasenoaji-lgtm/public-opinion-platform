"""Konfigurasi aplikasi. Semua rahasia lewat environment, tidak ada default produksi."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    opensearch_url: str = Field(default="http://localhost:9200", alias="OPENSEARCH_URL")

    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    # Model abstraction layer. Provider dipilih per deployment, bukan di-hardcode.
    llm_provider: str = Field(default="anthropic", alias="LLM_PROVIDER")
    llm_model: str = Field(default="claude-sonnet-4-6", alias="LLM_MODEL")
    embedding_model: str = Field(default="text-embedding-3-large", alias="EMBEDDING_MODEL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    # Ambang publikasi. Diletakkan di config agar bisa diperketat per deployment,
    # tidak pernah dilonggarkan di bawah nilai ini tanpa persetujuan tertulis.
    min_effective_n: int = 250
    min_aggregate_cell: int = 5

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
