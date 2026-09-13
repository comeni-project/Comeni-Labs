"""What the API remembers.

**One table in slice 1, and the restraint is the point.** The registry is files by decision
(issue #43), and `pipeline.yml` is the artifact rather than a projection of rows. What is
genuinely not recoverable from disk is *when a check last ran*, so that is what is stored.

`test_the_registry_is_not_in_the_database` holds it: a second table is a deliberate act
rather than a drift.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
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
    goal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    """The confirmed `Goal`, once a person has accepted one. Null on every draft drawn by hand.

    **An authored draft retains its goal** (§1.9), and this is where. Without it a conversation
    that has already established what somebody wants has to re-derive it from the graph on
    every turn — `materialise.py` does derive one, and a derived goal is a reading of the graph
    rather than a record of what was asked for. Both exist because they answer different
    questions; this is the one a person confirmed.

    Nullable rather than defaulted to `{}`, because *no goal was ever confirmed* and *an empty
    goal was confirmed* are different facts and a default would erase the distinction on every
    row that predates this column."""
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    """Who settled what, per decision rather than per session (§1.8).

    A sidecar rather than fields on the graph's nodes: the browser owns the graph and sends it
    whole, so anything written into it is something the next PUT can overwrite. Provenance is
    the server's record of a mixed session — this node from the resolver, that one a person
    chose, this setting a model answered — and it must survive a client that knows nothing
    about it. Task 4 is what fills it.

    **Empty is a truthful default.** A draft nobody authored conversationally has no mixed
    provenance to record, and `{}` says exactly that."""
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    """Monotonic, and the thing every mutating authoring request is checked against.

    **Not `updated_at`.** Two writes inside one clock tick are indistinguishable by timestamp,
    and the comparison a stale proposal needs is equality against a number the client was shown
    — `AcceptProposal.expected_revision`. `row_version` on `ForgeAdaptation` is the same
    mechanism for the same reason; this one is named `revision` because the browser displays it
    and *revision 4* is what a person is looking at.

    A draft that existed before this column is revision 0, which is correct rather than a
    placeholder: it has had no authoring turn, so nothing has been proposed against it."""


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
    without going through `tests/guards/test_egress.py` first: `guarded` sets `tool_message` to
    `None` for a reason, and a tool's stderr is exactly where a path would appear.

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


# --- the forge's durable workflow -------------------------------------------------------
#
# **Seven tables at once, and the count is the argument.** Every table above had to argue for
# itself against issue #43 — declared data is files — and these do too. The line they stay on
# is this: *accepted* declarations are files, and everything before a human approves one is
# workflow state. A `forge_revision` holds a candidate, which is a draft in the same sense
# `pipeline_draft` is; `land.py` is what turns one into a file, and it is still the only thing
# that writes to a registry.
#
# What would cross the line: a table of contracts, types, roles or rules that a *build* reads.
# The test of which side a row is on is whether deleting the table changes a build's output.
# For all seven, it does not.
#
# **Every foreign key is RESTRICT and none is CASCADE.** The rule is that archiving an
# adaptation never deletes revisions, events, messages or invocation audit — and a cascade is
# how that rule gets broken by somebody deleting a row they thought was only theirs. There are
# no cascades to break it with: a delete that would take history with it fails instead.


class ForgeSourceSnapshot(Base):
    """One catalogue sync, and what came back.

    **The fifth table.** What is not recoverable from disk is *when a source was last read and
    what it said* — the adapters reach nf-core and Docker Hub over the network, and a page
    saying "1,612 tools, synced 20 minutes ago" is reading this row. Nothing else remembers it.

    `etag` is what makes the next sync cheap, and it is a fact about the upstream response
    rather than about us. `ok` plus `error` rather than a state column: a sync either produced
    a snapshot or explains why it did not, and `last_successful_sync_id` is what a page falls
    back to, so a failed refresh does not blank a catalogue that is merely stale.
    """

    __tablename__ = "forge_source_snapshot"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_revision: Mapped[str] = mapped_column(String(200), default="")
    """The commit or digest the catalogue was read at. Empty when the source proves none."""
    etag: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    """A coded refusal — `MF0201`, `MF0206` — never a provider's raw traceback."""
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    """A `SourceCounts` dump. JSON because the six numbers have exact meanings and are read
    together or not at all; six columns would invite reading one."""
    filters: Mapped[list] = mapped_column(JSON, default=list)
    """The `FilterNode` tree, when the source publishes one. PEGiS does; nf-core does not."""
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    """`SyncWarning` dumps. A sync that read 190 tools and could not classify two must be able
    to say so without failing — `MF0205` and `MF0207` are exactly that shape."""
    last_successful_sync_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """The most recent snapshot of this source that succeeded, which may be this one.

    **Not a foreign key, deliberately**: it points at a row in this same table, which buys
    nothing a service-level lookup does not, while making the first row of a source a
    chicken-and-egg problem in every fixture that builds one.
    """


class ForgeCatalogueItem(Base):
    """One tool an upstream source publishes.

    **The sixth table, and the one closest to the line.** It holds tool metadata, which sounds
    exactly like the registry data issue #43 put in files. It is not: this is a *cache of what
    somebody else publishes* — read over the network, replaced on every sync, and read by no
    build. The registry holds what a human approved; this holds what upstream currently says.
    Delete the whole table and a build emits the same bytes, which is the test of which side of
    the line a row is on.

    `id` is `sha256(source + ref)` and therefore stable across syncs, which is what lets an
    adaptation started last week still point at the same item today. `content_digest` is the
    per-tool digest the adapters compute; when it moves, an adaptation built from the old one
    is outdated, and that is the whole of what the plan means by the word.

    `present` rather than a delete: a tool that vanished upstream keeps its row and its
    history. Deleting it would take an approved contract's provenance with it.
    """

    __tablename__ = "forge_catalogue_item"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("forge_source_snapshot.id", ondelete="RESTRICT"), index=True
    )
    """The sync that last saw it — updated in place on each sync, so this is *latest seen*."""
    source: Mapped[str] = mapped_column(String(32), index=True)
    ref: Mapped[str] = mapped_column(String(200), index=True)
    """The source-native id — `samtools/sort`, `fastqc`. Unique together with `source`."""
    display_name: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    """Denormalised out of `metadata` so the catalogue's search is an index rather than a JSON
    scan. The catalogue page puts a search box on ~1,600 rows and expects it to be instant."""
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    """The whole `CatalogueItem` dump.

    **JSON because the shape genuinely varies by source** — PEGiS carries classifications and a
    container digest, nf-core carries structured ports and neither — and shredding a union of
    two sources into columns produces a table that is mostly null and still wrong when a third
    source arrives. The columns beside it are the ones something actually *queries*.

    Named `metadata` in the database and `metadata_json` in Python: `metadata` is taken on a
    SQLAlchemy declarative class.
    """
    content_digest: Mapped[str] = mapped_column(String(64), index=True)
    adaptable: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    unsupported_reason: Mapped[str] = mapped_column(Text, default="")
    present: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    """False once a sync no longer finds it. A total is what the source publishes *now*."""
    last_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """A *source* fact — when upstream last touched the tool — null when it proves none."""
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (Index("ix_forge_catalogue_item_source_ref", "source", "ref", unique=True),)


class ForgeAdaptation(Base):
    """One tool somebody is turning into registry data.

    **The seventh table**, and the centre of the workflow: everything else in this block either
    describes what it was built from or records what happened to it.

    `row_version` is optimistic concurrency and not decoration. Two browser tabs on one
    adaptation is the ordinary case — a reviewer opens the candidate and the diff side by side
    — and without it the second *Approve* silently wins over a *Request changes* that already
    landed. Every transition compares and increments it, in `services/forge_state.py` and
    nowhere else.

    `source_digest` and `registry_digest` are what the candidate was built and validated
    against. They are here rather than only on the revision because approval compares the
    registry digest against the layer *now*, and a layer that moved makes a green verdict a
    statement about something that no longer exists (`MF0301`).

    `who` is ATTRIBUTION, not authentication, exactly as on `QueueVisit`, `PipelineDraft` and
    `GateRun`. Nothing here is a credential and nothing here may become one.
    """

    __tablename__ = "forge_adaptation"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    catalogue_item_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("forge_catalogue_item.id", ondelete="RESTRICT"), index=True
    )
    state: Mapped[str] = mapped_column(String(24), index=True)
    """An `AdaptationState` value. A plain column rather than a native Postgres enum, for the
    reason `GateRun.state` records: adding a member to a Postgres enum is a migration, and
    `mendel_forge.workflow.AdaptationState` is already the closed vocabulary that matters."""
    failed_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    """The state it was in when it failed. Retry resumes *that* stage rather than assuming
    every failure came from the model; `workflow.retry_target` is the rule."""
    current_revision_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """Exactly one current revision.

    **Not a foreign key, and this one is a real trade rather than a convenience.**
    `forge_revision.adaptation_id` points back here, so a pair of real constraints is a cycle
    no insert order satisfies without a deferred constraint or `use_alter`. The cheaper honest
    answer is one FK in the direction that carries the ownership, plus a service that only ever
    sets this to a revision it just wrote for this adaptation.
    `test_the_current_revision_belongs_to_its_adaptation` holds the other half.
    """
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    source_digest: Mapped[str] = mapped_column(String(64), default="")
    registry_digest: Mapped[str] = mapped_column(String(64), default="")
    who: Mapped[str] = mapped_column(String(200), index=True)
    """ATTRIBUTION, not authentication."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        Index(
            "ix_forge_adaptation_one_active",
            "catalogue_item_id",
            unique=True,
            postgresql_where=text("state NOT IN ('published', 'archived')"),
        ),
    )
    """At most one *active* adaptation per catalogue item.

    **A partial unique index where supported, and a service-level refusal everywhere.** The
    index is Postgres-specific and is the half that cannot be raced; `forge_state.begin`
    refuses first, so what a person reads is a sentence rather than a constraint violation.
    Two mechanisms here are not the redundancy `SourceSnapshot.classified` was — they answer at
    different moments, and only the index holds when two requests arrive together.

    The literal state list is `workflow.TERMINAL` spelled in SQL, and the two are held together
    by `test_the_partial_index_names_exactly_the_terminal_states` rather than by this sentence.
    A comment claiming a guard exists is worse than no comment.
    """


class ForgeRevision(Base):
    """One attempt at a candidate — the thing a reviewer actually reads.

    **The eighth table.** A revision is immutable once validation begins, which is why *request
    changes* creates a new one rather than editing this. The superseded attempt stays: the plan
    refuses to call it rejection precisely because the previous candidate has to survive.

    `manifest` holds workspace-*relative* paths only. An absolute host path in a row is a path
    in every API response that renders it and, eventually, in a prompt — the scaffold asserts
    it contains none, and this is that same claim on the storage side.

    `prompt_versions` records which committed prompt files produced this. A candidate whose
    prompt cannot be identified cannot be reproduced or blamed.
    """

    __tablename__ = "forge_revision"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    adaptation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("forge_adaptation.id", ondelete="RESTRICT"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    """1, 2, 3 — what a person calls it. Unique per adaptation."""
    parent_revision_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("forge_revision.id", ondelete="RESTRICT"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(24), index=True)
    """A `RevisionState` value. `validated` means the checks *finished*, not that they passed —
    a candidate that fails its checks is still inspectable, and that is a reviewable state."""
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    """Workspace-relative paths, by role. Never an absolute path — see the class docstring."""
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    """The verdict ladder's summary: which rungs ran, which refused, and their coded
    diagnostics. Stored rather than recomputed, because the layer it was computed against may
    be gone by the time anybody reads it — which is the fact `MF0301` refuses on."""
    green: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    """Denormalised out of `validation`, because approval queries it and the page renders it."""
    unresolved_required: Mapped[int] = mapped_column(Integer, default=0)
    """How many required holes are still open. A precondition of approval, so it is a column."""
    prompt_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        Index("ix_forge_revision_adaptation_ordinal", "adaptation_id", "ordinal", unique=True),
    )


class ForgeEvent(Base):
    """What happened, in order, in words a reviewer may read.

    **The ninth table, and it is the audit rather than a log.** `detail` is *public* detail: it
    is rendered on the adaptation page, so it carries no host path, no credential and no
    provider payload. A stack trace goes to the process log; what goes here is the sentence a
    person needs in order to understand why the adaptation is where it is.

    Append-only by convention and by having no update path in `services/forge_state.py`. A lost
    job must not leave a row running forever, and the recovery writes a `reclaimed` event —
    visible rather than silent, which is the difference between a sweep and a cover-up.
    """

    __tablename__ = "forge_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    adaptation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("forge_adaptation.id", ondelete="RESTRICT"), index=True
    )
    revision_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("forge_revision.id", ondelete="RESTRICT"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)
    """An `EventKind` value — closed, because an audit whose vocabulary any call site may extend
    with a free string is one nothing can query."""
    from_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """The state the adaptation was in before this event, or `None` for one that moved nothing.

    **Added 2026-09-05, when archiving became legal from five states rather than one.** Until
    then every `archived` event came from `review` and the column would have said nothing; now
    an adaptation archived from `scaffolding` and one archived after a failure are the same row
    in history without it, and they are very different stories.

    It is a machine fact and `detail` is a person's sentence, so they are separate columns
    rather than one string with a prefix — the same split Plan 1.14 made when `reason` was
    answering both *why this axis* and *why this answer*, which is how the registry came to cite
    the STAR paper as the reason HISAT2 was chosen (A79/A107).

    Nullable because an event may record something that is not a transition — a message, an
    invocation — and a sentinel like `""` would be a state name that is not one.
    """
    detail: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(200), default="")
    """A person's name, or the worker's. ATTRIBUTION, not authentication."""
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ForgeMessage(Base):
    """A turn of the review conversation.

    **The tenth table.** Chat and mutation are separate verbs, and this table is the structural
    half of that decision: a message has no candidate, no manifest and no path to one. *Request
    changes* writes a `forge_revision`; a question writes a row here and can do nothing else.

    `citations` is the envelope the review prompt requires — an answer cites evidence ids from
    the dossier, and an answer that cannot is one nobody can check. JSON because a citation
    list is small and is read whole, with its message.

    **`content` is free text, and it is the review chat's own text.** It is written by a curator
    and by a model, and it goes back to the model on the next turn by design — that is what
    makes a conversation a conversation. Which door that crossing is, and what may be in it, is
    `tests/guards/test_egress.py`'s to declare, not this docstring's to assume.
    """

    __tablename__ = "forge_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    adaptation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("forge_adaptation.id", ondelete="RESTRICT"), index=True
    )
    revision_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("forge_revision.id", ondelete="RESTRICT"), nullable=True
    )
    """Which candidate was on screen. A question about a type is a question about the revision
    that chose it, and the answer is unreadable a revision later without this."""
    role: Mapped[str] = mapped_column(String(16))
    """A `MessageRole` value — `curator` or `assistant`."""
    state: Mapped[str] = mapped_column(String(16), index=True)
    """A `MessageState` value. A question is `pending` until the AI lane reaches it, and it may
    wait behind an adaptation, so the page has to be able to draw the waiting."""
    content: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(JSON, default=list)
    ai_invocation_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("ai_invocation.id", ondelete="RESTRICT"), nullable=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AiInvocation(Base):
    """One call to a model, and everything needed to judge it afterwards.

    **The eleventh table, and the only one not named `forge_*`** — deliberately. The model
    transport is shared: the builder and Wiener will each grow an agent, and an audit table
    with `forge` in its name would either be copied twice or be a lie the second time. `agent`
    is the column that says whose call it was.

    Every field a response must record is a column here rather than a JSON blob, because these
    are exactly the fields a prompt evaluation aggregates over: which model, which prompt
    version, how long, how many tokens, and did it work.

    **No table in this block holds a provider key**, and this is the one where one would go.
    `provider` and `model` name the lane; the credential lives in the environment and reaches
    `comeni_ai.access` and nothing else. `test_no_forge_table_holds_a_credential` is what says
    so in a way that fails.

    `prompt_digest` is over the *rendered* prompt, so two calls differing only in dossier
    content are distinguishable. `input_digests` carries the source and registry digests the
    call was made against, which is what makes an answer reproducible at all.
    """

    __tablename__ = "ai_invocation"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent: Mapped[str] = mapped_column(String(32), index=True)
    """`forge` today. The builder's and Wiener's agents are why this is a column."""
    purpose: Mapped[str] = mapped_column(String(24), index=True)
    """An `InvocationPurpose` value — one member per committed prompt id."""
    model: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(64), default="")
    prompt_id: Mapped[str] = mapped_column(String(120), index=True)
    prompt_version: Mapped[str] = mapped_column(String(16), default="")
    prompt_digest: Mapped[str] = mapped_column(String(64))
    """Over the rendered prompt, not the template."""
    input_digests: Mapped[dict] = mapped_column(JSON, default=dict)
    """Source and registry digests. What makes the answer reproducible."""
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(String(16), index=True)
    """An `InvocationState` value. `refused` — the answer did not validate — is separate from
    `failed` — the provider did not answer. Folding them hides the finding worth measuring."""
    failure_code: Mapped[str] = mapped_column(String(16), default="")
    """A declared diagnostic code, never a provider's own message."""
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Nullable because a provider supplies them or does not, and a local Ollama lane often
    does not. A zero would be a measurement; a null is the absence of one."""


class PipelineAuthoringSession(Base):
    """One conversation about one draft.

    **The twelfth table, and the argument is the one every table here has had to make: does
    deleting it change a build?** It does not. Delete every row in this table and the three
    below it and `pipeline_draft` still opens, still validates and still keeps — what is lost is
    the *account* of how the graph came to look that way, which is exactly the split issue #43
    drew. Declared data is files; a half-finished conversation is workflow state.

    Deleting the draft is the other direction and is not symmetric: the working copy goes, and
    these rows are what `ondelete="RESTRICT"` refuses to orphan. A session about a draft that no
    longer exists is a transcript nobody can act on, so the delete is refused rather than
    cascaded — `test_no_foreign_key_cascades` is what keeps that true for the whole schema.

    **What is deliberately not here**: contracts, types, roles or vocabulary (issue #43, and
    `test_the_registry_is_not_in_the_database`); a credential of any kind (the provider key
    lives in the environment and reaches `comeni_ai.access` and nothing else); a provider's own
    error text (`failure_code` on `ai_invocation` carries a declared code instead); and any
    runtime sample data, which is invariant 15 and is Wiener's anyway.

    `blueprint` is what the **resolver** produced, stored whole. §1.4 — resolve the whole
    blueprint, reveal it incrementally — so the reveal is a cursor over something already
    computed rather than a series of fresh resolutions that could each answer differently.
    `cursor` is how far the reveal has got.

    `row_version` is optimistic concurrency on the session itself, the same mechanism
    `ForgeAdaptation` documents: two tabs on one conversation is the ordinary case.
    """

    __tablename__ = "pipeline_authoring_session"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), unique=True, index=True
    )
    """**Unique**, because the MVP does not support several sessions on one draft.

    Task 3 asks for this constraint if the design does not support several, and it does not:
    §2 gives a session one phase and one cursor, so two sessions on one draft would be two
    answers to *where are we* with nothing to arbitrate between them. A second conversation is
    a second draft."""
    mode: Mapped[str] = mapped_column(String(8))
    """A `Mode` value — `build` or `spawn`. A plain column rather than a native Postgres enum,
    for the reason `GateRun.state` records: adding a member to a Postgres enum is a migration,
    and `authoring.types.Mode` is already the closed vocabulary that matters."""
    phase: Mapped[str] = mapped_column(String(16), index=True)
    """A `Phase` value. Indexed because sweeping for sessions stuck in `understanding` is how a
    job that never came back is found — `forge_jobs` already sweeps that way."""
    failed_from: Mapped[str | None] = mapped_column(String(16), nullable=True)
    """The phase it was in when it failed, so retry resumes *that* one.

    **§2 draws two arrows out of `failed`** — back to `understanding` and to `resolving` — and
    `phase` alone cannot choose between them. This is `ForgeAdaptation.failed_stage`'s argument
    arriving a second time: retry resumes the stage that failed rather than assuming every
    failure came from the model, and without the column a failed build would be retried as a
    prompt call.

    Nullable, and null is not a sentinel: a session that has never failed has no such phase, and
    `""` would be a phase name that is not one."""
    goal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    """The confirmed `Goal`, mirrored onto `pipeline_draft.goal` when the person accepts it.

    Here as well as there because they answer different questions: this is what *this
    conversation* settled on, and the draft's is what the artifact will be built from. They are
    equal in the ordinary case and must be allowed to differ while a revision is being
    reviewed."""
    blueprint: Mapped[dict] = mapped_column(JSON, default=dict)
    registry_digest: Mapped[str] = mapped_column(String(80), default="")
    """Which layer stack the blueprint was resolved against. A blueprint outlives the registry
    that produced it, and `MF0301`'s lesson one product over: a green answer about a layer that
    has since moved is a statement about something that no longer exists.

    **80, not 64.** It was 64 for a commit, which is a hex digest's length — and a `Digest` is
    `sha256:` plus 64 hex, seventy-one characters. Postgres would have refused the first
    blueprint ever stored, and nothing wrote one until Task 6."""
    cursor: Mapped[int] = mapped_column(Integer, default=0)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    who: Mapped[str] = mapped_column(String(200), index=True)
    """ATTRIBUTION, not authentication, exactly as on `QueueVisit`, `PipelineDraft`,
    `GateRun` and `ForgeAdaptation`."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PipelineAuthoringTurn(Base):
    """One turn of an authoring conversation, in a fixed order.

    **The thirteenth table.** `seq` is what makes the order explicit rather than emergent: two
    turns written inside one clock tick sort arbitrarily by `at`, and a transcript that reorders
    itself on reload is the defect a timestamp ordering hides until the machine is fast enough.
    Unique per session, so the ordering cannot be ambiguous even in principle.

    **A user turn appears immediately and its answer is a separate row**, which is why `state`
    exists. The assistant's turn is written `pending` the moment the person's is accepted, so
    the transcript can draw the waiting instead of the browser inventing a placeholder that
    reload would lose. `failed` is not `answered` with empty content — folding them hides the
    only thing worth measuring about a provider.

    `base_revision` is the draft revision this turn was composed against, so a reply that
    arrives after the draft moved can be recognised as stale rather than applied.
    """

    __tablename__ = "pipeline_authoring_turn"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_authoring_session.id", ondelete="RESTRICT"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    """Explicit order within the session. See the class docstring: `at` is not an ordering."""
    role: Mapped[str] = mapped_column(String(16))
    """`person` or `assistant`. The same distinction `AuthoringRole` draws at the door."""
    state: Mapped[str] = mapped_column(String(16), index=True)
    """A `TurnState` value — `pending`, `answered` or `failed`."""
    blocks: Mapped[list] = mapped_column(JSON, default=list)
    """The assistant's turn as a list of discriminated blocks. Empty while `pending`."""
    text: Mapped[str] = mapped_column(Text, default="")
    """The person's own words. Free text with a real author, and the same kind of field
    `ForgeMessage.content` is — which door carries it and what may be in it is
    `tests/guards/test_egress.py`'s to declare, not this docstring's to assume."""
    base_revision: Mapped[int] = mapped_column(Integer, default=0)
    ai_invocation_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("ai_invocation.id", ondelete="RESTRICT"), nullable=True
    )
    """The audit row for the call that produced this turn. `ai_invocation.agent` is why that
    table is not named `forge_*`: this is the second agent it was built for."""
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (
        Index("ix_pipeline_authoring_turn_order", "session_id", "seq", unique=True),
    )


class PipelineAuthoringProposal(Base):
    """Something the engine offered, and what became of it.

    **The fourteenth table.** A proposal is separate from the turn that carried it because the
    two have different lifetimes: the turn is an immutable line of transcript, and the proposal
    is answered later — possibly after the draft has moved underneath it.

    `state` carries `stale` as a named member rather than as a comparison somebody remembers to
    perform. A proposal made against revision 4 and answered after revision 5 landed was not
    rejected — nobody rejected it — and applying it would write over work done in between.

    `draft_revision` is what that comparison is against, and `chosen_option` records which
    option id won, never a value: the browser posts ids, and a proposal that recorded a *value*
    would be a place for something outside the offered set to enter.

    `by` distinguishes a person from the model for the reason `model_override` exists on all
    three decision kinds — a pipeline an agent assembled must not read as one a person drew by
    hand. That is A130 arriving in a third place.
    """

    __tablename__ = "pipeline_authoring_proposal"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_authoring_session.id", ondelete="RESTRICT"), index=True
    )
    turn_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pipeline_authoring_turn.id", ondelete="RESTRICT"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(24), index=True)
    """A `BlockKind` value — which of the discriminated payloads `payload` holds."""
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    """The block itself, stored whole and validated back through `authoring.types.parse_block`.
    Whole rather than shredded for `PipelineDraft.graph`'s reason: a schema that could hold half
    a proposal would be a second definition of what a proposal is."""
    state: Mapped[str] = mapped_column(String(16), index=True)
    """A `ProposalState` value — `pending`, `accepted`, `rejected` or `stale`."""
    chosen_option: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """An option **id**, never a value. See the class docstring."""
    by: Mapped[str | None] = mapped_column(String(16), nullable=True)
    """`person`, `model` or `resolver`, once answered. Null while pending."""
    draft_revision: Mapped[int] = mapped_column(Integer)
    """The revision this was proposed against. Staleness is equality against this."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_pipeline_authoring_proposal_one_pending",
            "session_id",
            unique=True,
            postgresql_where=text("state = 'pending'"),
        ),
    )
    """At most one pending proposal per session, which is §2's MVP rule made unraceable.

    **A partial unique index where supported, and a service-level refusal everywhere**, exactly
    as `ix_forge_adaptation_one_active` does it: the service answers with a sentence, and the
    index is the half that holds when two requests arrive together. The literal `'pending'` is
    `ProposalState.PENDING` spelled in SQL, and
    `test_the_pending_proposal_index_names_the_pending_state` holds the two together rather than
    this sentence doing it — a comment claiming a guard exists is worse than no comment.
    """
