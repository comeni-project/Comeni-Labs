"""Env-driven config, in one place.

Every path the API reads is declared here rather than resolved at a call site, because a
second place that decides where the registry lives is a second answer to that question.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MENDEL_", extra="forbid")

    workspace_root: Path = Path("./workspace")
    registry_root: Path = Path("./registry")
    source_root: Path = Path("./vendor")
    database_url: str = "postgresql+psycopg://mendel:mendel@localhost:5432/mendel"
    redis_url: str = "redis://localhost:6379"


settings = Settings()
