"""Env-driven config. Prefix `WIENER_`, so nothing here can collide with `MENDEL_`."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WIENER_", extra="forbid")

    database_url: str = "postgresql+psycopg://wiener:wiener@localhost:5433/wiener"
    redis_url: str = "redis://localhost:6379/1"
    artifact_root: Path = Path("./var/wiener/artifacts")
    """Where an uploaded pipeline directory lands. **Server-chosen, never client-supplied** —
    the same restraint `mendel_api.services.gates._directory` takes, for the same reason."""
    work_root: Path = Path("./var/wiener/work")
    ingest_base_url: str = "http://127.0.0.1:8099"
    """Where the head process posts its events. Loopback — spec §4."""
    lab_id: str = "local"
    """**Server-chosen, never client-supplied — A178.** §7.1 puts `lab_id` on every table from
    day one and §12.1 makes authentication a W1 requirement that phases 0–2 do not satisfy. A
    tenant column a request can set is not a boundary, so until there is an authenticated
    principal to derive it from, one deployment is one laboratory and this is where it is
    named. The route handlers never read a `lab_id` out of a body or a query string; the day
    authentication lands, this default is replaced by the principal and nothing else moves."""
    container_profile: str = "docker"
    """Which container runtime this site has, named as one of the artifact's own profiles.

    **A run needs two profiles, not one.** The emitted config separates the executor
    (`local`, `k8s`, `awsbatch`) from the runtime (`docker`, `singularity`), and its `k8s`
    profile says so in a comment: `nextflow run . -profile k8s,docker -c site.config`. The
    launcher passed only the executor, so every process would have run without a container and
    every tool would have had to be on the host's PATH.

    Named rather than restated: the artifact already defines what `docker` means, including the
    `-u $(id -u):$(id -g)` that keeps work directories from being root-owned. Site facts say
    *which*, never *what* — `docs/design/execution-boundary.md` §6.
    """
    stream_maxlen: int = 10_000
    """§7.2, and a starting number rather than a measurement — §17 carries it."""


settings = Settings()
