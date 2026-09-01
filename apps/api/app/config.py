"""Konfigurasi aplikasi. Semua rahasia lewat environment, tidak ada default produksi."""

import hashlib
import hmac
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

    # Kredensial konektor Phase 2. Kosong = konektornya membalas 503 dengan
    # pesan yang menyebut env var ini, bukan gagal senyap.
    youtube_api_key: str | None = Field(default=None, alias="YOUTUBE_API_KEY")
    x_bearer_token: str | None = Field(default=None, alias="X_BEARER_TOKEN")

    # Kunci untuk meng-hash identitas akun di mentions (services/ingestion.py).
    # Kosongkan dan nilainya diturunkan dari jwt_secret — lihat author_salt().
    author_hash_salt: str | None = Field(default=None, alias="AUTHOR_HASH_SALT")

    # Ambang publikasi. Diletakkan di config agar bisa diperketat per deployment,
    # tidak pernah dilonggarkan di bawah nilai ini tanpa persetujuan tertulis.
    min_effective_n: int = 250
    min_aggregate_cell: int = 5

    cors_origins: list[str] = ["http://localhost:3000"]

    def author_salt(self) -> str:
        """Salt untuk hash author, dengan turunan sebagai jaring pengaman.

        Kalau `AUTHOR_HASH_SALT` tidak diset, nilainya DITURUNKAN dari
        `jwt_secret` lewat HMAC dengan pemisah domain — bukan dipakai apa
        adanya. Alasannya: deployment yang sudah jalan tidak boleh mendadak
        gagal ingest hanya karena ada env var baru, tapi juga tidak boleh
        memakai salt konstan yang sama di semua deployment (hash dari daftar
        handle publik bisa dibalik lewat pencocokan kamus kalau saltnya
        diketahui).

        Konsekuensi yang perlu diketahui operator: menyetel AUTHOR_HASH_SALT
        setelah ada data akan mengubah semua author_hash berikutnya, sehingga
        akun yang sama terhitung sebagai dua akun berbeda sebelum dan sesudah
        pergantian. Setel sekali di awal, atau tidak sama sekali.
        """
        if self.author_hash_salt:
            return self.author_hash_salt
        return hmac.new(
            self.jwt_secret.encode(), b"author-hash-salt", hashlib.sha256
        ).hexdigest()


@lru_cache
def get_settings() -> Settings:
    return Settings()
