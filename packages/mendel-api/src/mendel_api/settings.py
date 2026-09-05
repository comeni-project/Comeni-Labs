"""Env-driven config, in one place.

Every path the API reads is declared here rather than resolved at a call site, because a
second place that decides where the registry lives is a second answer to that question.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:  # a settings module every route imports must not pull in a transport
    from comeni_ai import ModelAccess


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

    ai_context_tokens: int = 32_000
    """What the configured model can hold. The dossier is budgeted against it — see
    `mendel_forge.ai.context.Budget`, which reserves room for the answer because a context
    window is shared between the prompt and the response."""

    ai_max_jobs: int = 1
    """How many provider calls the AI worker runs at once.

    **`COMENI_AI_MAX_CONCURRENT_JOBS` wins when it is set** — `access.py` declares that name as
    part of the shared configuration surface and says so on the constant: *read by the AI
    worker, not by this package. Declared here so a second consumer does not invent a second
    spelling.* `MENDEL_AI_MAX_JOBS` still works, and costs nothing to keep; an operator writing
    one `.env` for a lane writes `COMENI_AI_*` throughout.

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

    **Distinct from `COMENI_AI_TIMEOUT_SECONDS`, which is one HTTP request to a provider.**
    This is the ceiling on a whole job — an analysis, an implementation and two repairs — and
    the age at which a claimed adaptation is reclaimed. Folding them would make a slow provider
    look like a dead worker.
    """

    @model_validator(mode="after")
    def _the_shared_name_wins(self) -> "Settings":
        """`COMENI_AI_MAX_CONCURRENT_JOBS` over `MENDEL_AI_MAX_JOBS` when both are set.

        The direction `access.DEPRECATED` already chose, and for its reason: an installation
        that sets both gets the shared name, which is the only direction that cannot silently
        un-migrate somebody.
        """
        shared = os.environ.get("COMENI_AI_MAX_CONCURRENT_JOBS", "").strip()
        if shared:
            object.__setattr__(self, "ai_max_jobs", int(shared))
        return self


settings = Settings()


def model_access() -> "ModelAccess | None":
    """How to reach the configured model, or `None` when none is.

    **One spelling for the whole lane, and it is `comeni-ai`'s.** `mendel-api` declared
    `MENDEL_AI_MODEL` and `MENDEL_AI_BASE_URL` of its own while `comeni_ai.access` declared
    `COMENI_AI_MODEL`, `COMENI_AI_API_KEY` and `COMENI_AI_BASE_URL` as *the* shared surface —
    two answers to "which model", with an operator's `.env` obliged to know which consumer read
    which. That is the drift the package rename was for, arriving one layer up.

    **It is also what makes the hosted lane a configuration change rather than a code change**
    (invariant 13): a key belongs to a provider and a base URL to a local endpoint, and
    `from_env` is the one place both are read. A `MENDEL_AI_API_KEY` would have been a *third*
    home for a credential, on a settings object that is printed in a traceback.

    **`os.environ` at call time, not at import.** A worker holding one would ignore a changed
    environment on restart, which is the one moment an operator most expects it to be read —
    the argument `_client` already makes about not caching a module global.
    """
    from comeni_ai import ModelAccess

    return ModelAccess.from_env(os.environ)
