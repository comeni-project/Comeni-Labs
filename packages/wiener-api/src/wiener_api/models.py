"""What Wiener persists. Four tables, and `run_event` is the only one that is not a projection.

`docs/design/wiener.md` §7.1. `run_task` and `run.phase` exist because a dashboard cannot fold
three days of events on every page load — they are a cache with a rebuild path, and
`test_projection_matches_replay` (Task 7) asserts the cache agrees with the fold.
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from wiener_api.db import Base


class Run(Base):
    """A run somebody asked for. **Not a gate** — `docs/design/execution-boundary.md` §3: a
    gate runs Mendel's own artifact on public data and lives in `mendel-api`'s `gate_run`."""

    __tablename__ = "run"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lab_id: Mapped[str] = mapped_column(String(32), index=True)
    """**On every table from day one** — `docs/design/wiener.md` §7.1, decided 2026-08-23.
    Cheap now; a migration touching every table later. The named cost is that a filter you can
    forget is a leak, which is why Step 7a adds a guard rather than a convention."""
    artifact_id: Mapped[str] = mapped_column(String(32), index=True)
    submitted_by: Mapped[str] = mapped_column(String(200))
    """ATTRIBUTION, not authentication — and §12.1 says that is a gap in W1, not a design."""
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    phase: Mapped[str] = mapped_column(String(16), index=True)
    executor: Mapped[str] = mapped_column(String(16), default="local")
    ingest_secret: Mapped[str] = mapped_column(String(64))
    """Generated at launch and carried in the head process's weblog URL — §13.1."""
    nextflow_run_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunEventRow(Base):
    """The record. Every projection is derivable from these rows and nothing else."""

    __tablename__ = "run_event"

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lab_id: Mapped[str] = mapped_column(String(32), index=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(24))
    at_ms: Mapped[int] = mapped_column(BigInteger)
    payload: Mapped[dict] = mapped_column(JSON)
    """The ADMITTED event, not the raw body — §4.4."""
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RunTask(Base):
    __tablename__ = "run_task"

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lab_id: Mapped[str] = mapped_column(String(32), index=True)
    task_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    process: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    attempts: Mapped[list] = mapped_column(JSON, default=list)
    latest_exit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_change_ms: Mapped[int] = mapped_column(BigInteger)


class RunArtifact(Base):
    """A gated pipeline directory somebody uploaded. Wiener owns it — §12."""

    __tablename__ = "run_artifact"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lab_id: Mapped[str] = mapped_column(String(32), index=True)
    uploaded_by: Mapped[str] = mapped_column(String(200))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    digest: Mapped[str] = mapped_column(String(71))
    pipeline_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(Text, default="")
