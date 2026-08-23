"""What the API remembers.

**One table in slice 1, and the restraint is the point.** The registry is files by decision
(issue #43), and `pipeline.yml` is the artifact rather than a projection of rows. What is
genuinely not recoverable from disk is *when a check last ran*, so that is what is stored.

`test_the_registry_is_not_in_the_database` holds it: a second table is a deliberate act
rather than a drift.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from mendel_api.db import Base


class SourceCheck(Base):
    __tablename__ = "source_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    checked: Mapped[int] = mapped_column(Integer)
    drifted: Mapped[int] = mapped_column(Integer)
    skipped: Mapped[int] = mapped_column(Integer)


class QueueVisit(Base):
    """When a curator last looked at the queue.

    **The second table, and the first one's docstring said that would be a deliberate act.**
    This is that act. What is not recoverable from disk is when a person last looked — the
    registry is files, the drafts are files, and neither records a reader.

    `who` is ATTRIBUTION, not authentication. It comes from `git config user.name` through
    `identity.default_author()`, so a shared installation gives every curator the same
    baseline unless they configure git differently. Real accounts replace this column's
    source and nothing else.
    """

    __tablename__ = "queue_visit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    who: Mapped[str] = mapped_column(String(200), index=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PipelineDraft(Base):
    """A graph somebody is still drawing.

    **The third table, and the first one's docstring said that would be a deliberate act.**
    This is that act. Issue #43 decided *declared* data is files — contracts, rules,
    vocabularies — because those need diff, blame, review, signature and merge, which are the
    five things a cited registry sells. **A draft needs none of them until it is landed**, and
    `POST /drafts/{id}/keep` is landing: it validates, refuses anything illegal, and writes the
    `pipeline.yml` that is the actual artifact.

    `id` is `secrets.token_hex(16)` rather than a serial. `routes/build.py` states why the API
    cannot take a path — invariant 15, no input accepts a sample identifier, a filename or a
    path — and an opaque id is the alternative that does not become one. A serial would be
    guessable, which is the next-worst thing.

    `graph` is a JSON column holding a `DraftGraph`. Stored **whole** rather than shredded into
    node and edge tables: the client owns the working graph and sends it whole, and a schema
    that could hold half a graph would be a second definition of what a graph is.

    `who` is ATTRIBUTION, not authentication, exactly as on `QueueVisit`.
    """

    __tablename__ = "pipeline_draft"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    who: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    graph: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GateRun(Base):
    """A gate somebody asked for, and what came back.

    **The fourth table.** The first one's docstring said a second would be a deliberate act,
    and every one since has had to argue for itself. This one holds what the artifact cannot:
    `Pipeline.gate` records the strongest gate a pipeline *passed*, and says nothing about who
    asked, when, or what Nextflow printed on the way to failing. A person watching a 900s stub
    run needs all three, and none of them is recoverable from disk.

    **`output` is a tool's own text** — the same kind of field `GateFailure.tool_message`
    already is on the egress surface, with a real author who is not us. It is stored and shown
    to the person who asked for the gate. It must never be folded into an egress payload
    without going through `tests/test_egress.py` first: `guarded` sets `tool_message` to `None`
    for a reason, and a tool's stderr is exactly where a path would appear.

    **This is not run history.** `docs/design/execution-boundary.md` §2 — a gate is Mendel's
    artifact checking itself on data somebody else published; a *run* takes a laboratory's
    samplesheet, belongs to Wiener, and has no row here. The day one of these carries an input
    path, the boundary has moved without anybody deciding to move it.
    """

    __tablename__ = "gate_run"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(32), index=True)
    who: Mapped[str] = mapped_column(String(200))
    """ATTRIBUTION, not authentication, exactly as on `QueueVisit` and `PipelineDraft`."""
    gate: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), index=True)
    """`queued` | `running` | `passed` | `failed`.

    A plain column rather than a native enum: adding a state to a Postgres enum is a migration,
    and `Gate` in `comeni_core.artifact.gates` is already the closed vocabulary that matters
    here. The service converts on the way out, so nothing downstream sees the string.
    """
    output: Mapped[str] = mapped_column(Text, default="")
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
