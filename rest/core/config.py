# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""FastAPI configuration module."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration object."""

    model_config = SettingsConfigDict(extra="allow", env_file=".env", case_sensitive=True)

    PROJECT_NAME: str = "Afsoon"
    BACKEND_CORS_ORIGINS: list[str] | str = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        """Validate CORS origins."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        if isinstance(v, (list, str)):
            return v
        raise ValueError(v)


settings = Settings()
