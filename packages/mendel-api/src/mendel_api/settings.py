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
    """The layer. **One root** since Plan 5A — it used to be two, `registry_root` for the
    declarations and `source_root` for the module code they describe, on two release cadences
    in two repositories. `MD0104` exists to catch a contract drifting from its module and was
    comparing two things nothing kept in step."""
    draft_root: Path = Path("./build/drafts")
    """Where `keep` writes a draft's `pipeline.yml`.

    **The API never receives this path** — invariant 15, and `routes/build.py` says so. A draft
    is addressed by an opaque id; this is where the server chooses to put the artifact it
    writes, which is a different fact from a client naming a file.
    """
    example_goal: Path = Path("./examples/rnaseq-goal.yml")
    """The goal the builder opens on.

    **A setting rather than a constant, because a bare relative path resolves against the
    process's working directory** — which is the repository root under pytest and `/app` in a
    container. It shipped as `Path("examples/rnaseq-goal.yml")`, passed every test, and answered
    500 the first time the stack came up. Checkpoint 1 is what found it.
    """
    database_url: str = "postgresql+psycopg://mendel:mendel@localhost:5432/mendel"
    redis_url: str = "redis://localhost:6379"


settings = Settings()
