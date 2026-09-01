"""What Wiener persists. Four tables, and `run_event` is the only one that is not a projection.

`docs/design/wiener.md` §7.1. `run_task` and `run.phase` exist because a dashboard cannot fold
three days of events on every page load — they are a cache with a rebuild path, and
`test_projection_matches_replay` (Task 7) asserts the cache agrees with the fold.
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, Integer, String, Text
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

    # --- what was spawned, so a verb has something to signal -----------------------------
    #
    # **`_spawn` discarded its `Popen` on the line it made it**, so until Plan 6 nothing in
    # Wiener could act on a running pipeline: there was no pid anywhere and cancel had nothing
    # to terminate.
    #
    # **A pid is not an identity.** They are reused, and signalling a recycled one kills a
    # stranger's process — on a laptop, plausibly the user's editor. `pid_started_at` is what
    # makes the pair unique: a process's own start time cannot be reused with its number.
    #
    # **The host matters** because `wiener.md` §12.1 records that the worker holds the host
    # Docker socket. A cancel arriving at a replica that did not spawn this run has nothing to
    # signal, and guessing would signal the wrong process. It refuses and says so.
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pid_started_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    pid_host: Mapped[str | None] = mapped_column(String(200), nullable=True)
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

    # --- derived from the latest attempt, so the table can be ORDERED BY --------------
    #
    # **A191.** `attempts` is JSON and cannot be indexed usefully. The Tasks tab sorts 5,000
    # rows by memory, which is an `ORDER BY` or it is loading 5,000 documents. The projection
    # already computes these when it writes the row, so the cost is three columns and no
    # second source of truth — the JSON stays authoritative and these are its index.
    peak_rss_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    realtime_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    pct_cpu: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- A200. The lab's own words, and the ONLY place in Wiener they are projected ----
    #
    # `[{n, tag, hash, workdir}]`, one per attempt, written from the raw payload by this
    # projection — which lives in `wiener-api` and is impure. **`wiener-core` never sees
    # them**, so `test_the_fold_is_where_the_lab_strings_stop` passes untouched and §8's
    # claim that no lab string can become a span attribute stays STRUCTURAL rather than
    # becoming a rule somebody has to remember.
    #
    # Deliberately NOT indexed. The column exists so a task row can say `sample_07`, not so
    # anybody can search a deployment for a patient.
    labels: Mapped[list] = mapped_column(JSON, default=list)

    # --- the latest attempt's tag, so ONE RUN's tasks can be filtered by it -----------
    #
    # The same A191 argument as the three columns above — `labels` is JSON and a `WHERE` over
    # it is a scan of documents — and the same A200 restraint as the column it indexes:
    # **deliberately NOT indexed.** A191 earned its two indexes by needing to sort a whole
    # deployment's worth of rows; this filter is always inside `(lab_id, run_id)`, which IS
    # indexed, so the scan is bounded by one run's task count rather than by the table.
    #
    # That boundary is the whole argument for it existing. A200 withheld a search across a
    # deployment for a patient, and an unindexed column reachable only under a run id cannot
    # become one: you must already hold the run, whose tags the table renders anyway. Adding
    # an index here would remove exactly that bound, which is why there is a comment instead
    # of an index.
    #
    # `labels` stays authoritative and `TaskOut.tag` still reads it — this is its index, not a
    # second source of truth. Nothing back-fills it, for the reason A191's migration gives.
    tag: Mapped[str | None] = mapped_column(String(200), nullable=True)


class RunIntent(Base):
    """One verb, asked for by a person, and what happened — `wiener.md` §11.

    **This table is the reason cancel is not a `POST /runs/{id}/cancel`.** §11 defines a *closed
    verb vocabulary* — `cancel`, `relaunch`, `retry task N`, `pause`, `apply` — where every one
    is a typed `Intent` that *requires approval by a named human* and leaves an audit line. It
    also calls that surface the one *"that deserves the hardest audit in Wiener"*, and says why
    the vocabulary is what makes the audit finite: **a reviewer checks a list of verbs, not a
    sanitiser.** A first verb shipped without this makes the second one a shortcut's descendant.

    Cancel is the right verb to open with for §11's own reason — *"the only one that needs no
    artifact"* — which is an argument for building the machinery under the cheapest verb, not
    for skipping it.

    §11's audit line is *who · when · why · prior phase · resulting run id*, and all five are
    here. `resulting_run_id` is null for cancel and non-null for relaunch; it exists now rather
    than when relaunch arrives because adding it later means a migration over rows that cannot
    be back-filled.
    """

    __tablename__ = "run_intent"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    lab_id: Mapped[str] = mapped_column(String(32), index=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    """A member of `wiener_core.intent.IntentKind`, stored as its value. **A closed vocabulary
    written down twice would drift**, so the enum is the authority and this column is its
    spelling on disk — the same relationship `run.phase` has with `Phase`."""

    because: Mapped[str] = mapped_column(String(32))
    """A member of `wiener_core.policy.Reason` — **a declared enum, never free text**, which is
    §5.2's rule and the reason that enum exists. `OPERATOR_REQUEST` is what a person clicking
    *cancel* writes; a policy that cancels on its own would write its own reason, and the audit
    would read the same either way without this field.

    Beside `why`, which is the sentence somebody typed. The enum is what a query groups by; the
    sentence is what a reader needs. Collapsing them is how §5.2 says an audit stops being
    answerable."""

    who: Mapped[str] = mapped_column(String(200))
    """**Authentication here, not attribution**, and that is a break with `mendel_api.models`'
    `who`, whose own docstring calls it attribution from `git config user.name`. §11 says
    *approval by a named human*.

    Until accounts exist there is no named human — `WIENER_API_TOKEN` is the only boundary, and
    `submitted_by` is already hardcoded `"operator"`, which `page-5` calls decoration. So this
    records what it actually knows and the API says so rather than inventing a person. **Do not
    read it as an identity until something authenticates one.**"""

    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    why: Mapped[str] = mapped_column(Text, default="")
    """Free text somebody typed to justify a verb. Displayed, never interpreted."""

    prior_phase: Mapped[str] = mapped_column(String(16))
    """What the run was before the verb. **The audit's most load-bearing field**: a cancel on a
    run that was already failing is a different act from one on a healthy run, and the phase
    afterwards cannot distinguish them."""

    resulting_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), default="")
    """What the verb actually did, in a closed set. A request that was accepted and then found
    nothing to signal is not the same as one that stopped a running process, and an audit that
    cannot tell them apart is an audit of intentions rather than of effects."""


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

    # --- what a person called this pipeline, carried across the courier -----------------
    #
    # **The name was never missing; it was dropped in transit.** `mendel_api.models`'
    # `PipelineDraft.name` has held it since Plan 3E, and the browser is the courier between
    # the two services (`wiener.md` §12, A179) — so the name existed at one end, was wanted at
    # the other, and nothing carried it. The run header read `run aa11bb22` while the builder
    # two tabs away called the same thing by a name somebody chose.
    #
    # **Not on `Pipeline`, and that is a decision rather than the easy option.** Putting it in
    # `pipeline.yml` would give CLI-built and air-gapped artifacts names too, at the cost of
    # `SCHEMA_VERSION` 6 -> 7 — a break — and of letting a label somebody typed move a content
    # digest. *Same goal in, same pipeline out* must not depend on what the pipeline was
    # nicknamed. The hole this leaves is real and is the honest one: an artifact uploaded by
    # hand has no name and shows `run <id>`.
    #
    # **Displayed, never interpreted.** It is free text a person typed. It is not a lab string
    # in the §8 sense — it names a pipeline shape, not a sample — but it is user-authored, so
    # it must not reach a span attribute or a log line without the same care.
    name: Mapped[str] = mapped_column(String(200), default="")
