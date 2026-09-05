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

    ai_max_jobs: int = 1
    """How many provider calls the AI worker runs at once.

    **One, and it is correct rather than conservative.** A local Ollama serves one request at a
    time, so a second concurrent call makes both slower rather than either faster; a hosted
    provider has a rate limit the worker cannot see. Raising it is an operator's decision about
    a limit they know, not a default worth tuning — and work waiting in a queue is visible,
    where work failing on a rate limit is a retry storm.
    """
    ai_job_timeout_seconds: int = 900
    """The ceiling on one AI job, and the age at which a claimed adaptation is reclaimed.

    **One setting for both**, because two would have to be kept in a sensible relation by
    whoever edits them: a reclaim threshold below the job timeout sweeps rows that are still
    being worked on, and the symptom is a model call that completes into a row somebody else
    already failed.

    900s is the stub gate's cold-cache figure from `CLAUDE.md`, used here as the longest thing
    this system is known to legitimately wait for. A model fill was measured at 227s.
    """


settings = Settings()
