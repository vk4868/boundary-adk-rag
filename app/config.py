"""Environment configuration with safe offline defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.ollama_embeddings import validate_loopback_base_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_token: SecretStr | None = None
    app_server_role: str = Field(default="analyst", min_length=1, max_length=64)
    app_allowed_roles: str = "analyst"
    app_allow_adk_cli: bool = False

    app_index_path: Path = Path("data/index-ollama.json")
    app_index_sha256: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$"
    )
    app_audit_path: Path = Path("data/audit/local-events.jsonl")
    app_max_session_turns: int = Field(default=8, ge=1, le=32)
    app_session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)

    app_enable_model_calls: bool = False
    app_model_provider: Literal["disabled", "ollama", "vertex"] = "disabled"
    app_model: str = Field(
        default="granite4.2:8b",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$",
    )
    app_ollama_base_url: str = "http://127.0.0.1:11434"
    app_ollama_num_ctx: int = Field(default=16384, ge=8192, le=32768)
    google_cloud_project: str | None = None
    google_cloud_location: str = Field(
        default="global", pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"
    )

    app_embedding_provider: Literal["lexical", "ollama", "vertex"] = "ollama"
    app_embedding_model: str = "embeddinggemma:latest"
    embedding_location: str = "us-central1"
    app_embedding_dimensions: int = Field(default=768, ge=1, le=4096)
    app_embedding_timeout_ms: int = Field(default=30000, ge=1000, le=120000)
    app_model_timeout_ms: int = Field(default=120000, ge=1000, le=180000)

    app_max_model_calls: int = Field(default=8, ge=5, le=8)
    app_max_tool_calls: int = Field(default=8, ge=1, le=20)
    app_max_input_tokens: int = Field(default=80000, ge=1000, le=500000)
    app_max_output_tokens: int = Field(default=7200, ge=500, le=20000)
    app_max_output_tokens_per_call: int = Field(default=900, ge=128, le=4096)
    app_max_request_seconds: float = Field(default=480, ge=5, le=600)
    app_max_search_results: int = Field(default=8, ge=1, le=20)
    app_max_search_query_chars: int = Field(default=1200, ge=50, le=4000)
    app_max_effective_search_query_chars: int = Field(
        default=7500, ge=1250, le=10000
    )
    app_max_evidence_chars: int = Field(default=32000, ge=1000, le=100000)

    @property
    def allowed_roles(self) -> frozenset[str]:
        return frozenset(
            role.strip() for role in self.app_allowed_roles.split(",") if role.strip()
        )

    @property
    def model_ready(self) -> bool:
        return bool(
            self.app_enable_model_calls
            and self.app_model_provider == "ollama"
        )

    @property
    def auth_ready(self) -> bool:
        return bool(self.app_token and self.app_token.get_secret_value())

    @property
    def audit_model_metadata(self) -> dict[str, str]:
        """Trusted deployment metadata for terminal audit records."""
        return {
            "model": self.app_model,
            "model_provider": self.app_model_provider,
            "model_location": (
                "loopback"
                if self.app_model_provider == "ollama"
                else self.google_cloud_location
            ),
        }

    @field_validator("app_ollama_base_url")
    @classmethod
    def validate_ollama_base_url(cls, value: str) -> str:
        return validate_loopback_base_url(value)

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "Settings":
        if self.app_server_role not in self.allowed_roles:
            raise ValueError("APP_SERVER_ROLE must be present in APP_ALLOWED_ROLES")
        if self.app_enable_model_calls and self.app_model_provider != "ollama":
            raise ValueError(
                "APP_ENABLE_MODEL_CALLS=true requires APP_MODEL_PROVIDER=ollama"
            )
        if self.app_enable_model_calls and self.app_embedding_provider != "ollama":
            raise ValueError(
                "APP_ENABLE_MODEL_CALLS=true requires APP_EMBEDDING_PROVIDER=ollama"
            )
        if self.app_env.lower() == "production" and not self.app_index_sha256:
            raise ValueError("APP_INDEX_SHA256 is required in production")
        if (
            self.app_max_output_tokens_per_call * self.app_max_model_calls
            > self.app_max_output_tokens
        ):
            raise ValueError(
                "per-call output cap multiplied by model-call cap exceeds total output cap"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
