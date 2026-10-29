"""What the API remembers.

**One table in slice 1, and the restraint is the point.** The registry is files by decision
(issue #43), and `pipeline.yml` is the artifact rather than a projection of rows. What is
genuinely not recoverable from disk is *when a check last ran*, so that is what is stored.

`test_the_registry_is_not_in_the_database` holds it: a second table is a deliberate act
rather than a drift.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from comeni_core.artifact.gates import Gate
from mendel_authoring.decisions import ActorKind
from mendel_authoring.pacing import Pacing
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, validates

from mendel_api.authoring.types import (
    Phase,
    ProposalKind,
    ProposalState,
    Purpose,
    TurnRole,
    TurnState,
)
from mendel_api.db import Base
from mendel_api.invocations import Agent, InvocationPurpose, InvocationState
from mendel_api.shape_versions import stamp
from mendel_api.shapes import Json


def _one_of(enum: type[StrEnum], length: int, name: str) -> Enum:
    """A `VARCHAR(length)` that holds only `enum`'s values, with a CHECK named
    `ck_<table>_<name>` (issue 274).

    Built from the enum, so a new member changes this and the drift tests ask for the
    migration: `alembic check` by name, `test_each_check_names_exactly_its_enum` by value. Not
    a native Postgres enum, for the reason `GateRun.state` gives. `validate_strings` refuses an
    unknown value in Python, before the database does; `length` keeps the column's width.
    """
    return Enum(enum, native_enum=False, create_constraint=True, validate_strings=True,
                length=length, name=name, values_callable=lambda e: [m.value for m in e])


def _quoted(enum: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum)


class GateState(StrEnum):
    """Where a gate's row is. Queued and running are live (`services.gates.LIVE`); passed and
    failed end it. Here rather than in `services.gates`, which imports this module."""

    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class ReplyCleared(StrEnum):
    """Why a model's reply text is gone though the model answered (Part H)."""

    DELETED = "deleted"
    """Its draft was deleted; the call's record outlives it."""
    RETENTION = "retention"
    """The installation's limit for model replies passed."""


class RetirementReason(StrEnum):
    AMBIGUOUS = "ambiguous"
    OBSOLETE_PROTOCOL = "obsolete_protocol"


class RetentionSweep(Base):
    """One category's share of one pass of the daily sweep (Part H): what retention removed, so a
    laboratory can see that deletion happened. A pass with nothing to do still writes its zeros:
    *nothing was due* is an answer, and silence would read as a sweep that never ran."""

    __tablename__ = "retention_sweep"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    category: Mapped[str] = mapped_column(String(32))
    removed: Mapped[int] = mapped_column(Integer)


class InstallationSetting(Base):
    """One setting chosen in the menu, for the whole installation (spec §8).

    **One row per setting rather than one document**, so two people saving two different
    settings cannot overwrite each other, and each row says who changed it last. `updated_by` is
    attribution, not authentication. No history table: nothing needs one yet.

    A secret's `value` is sealed text (`services/settings_codec.py`), never the secret.
    """

    __tablename__ = "installation_setting"
    shape_version: Mapped[int] = stamp("installation_setting")

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[Any] = mapped_column(Json)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str] = mapped_column(String(200))


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

    `who` is ATTRIBUTION, not authentication.
    """

    __tablename__ = "pipeline_draft"
    shape_version: Mapped[int] = stamp("pipeline_draft")

    decision_revision: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    confirmed_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """The decision revision the goal was confirmed at (*That's right*), or `None` while it
    never was. Recorded rather than inferred from *a want is present* (Part I.0 §6.2): the rows
    hold the want from the first sentence on."""
    decision_sequence: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    projection_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    projection_current: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    who: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    graph: Mapped[dict] = mapped_column(Json)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    provenance: Mapped[dict] = mapped_column(Json, default=dict)
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
    — `AcceptProposal.expected_revision`. It is named `revision` because the browser displays it
    and *revision 4* is what a person is looking at.

    A draft that existed before this column is revision 0, which is correct rather than a
    placeholder: it has had no authoring turn, so nothing has been proposed against it."""
    kept_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """When `keep` last wrote this draft's `pipeline.yml`; null if it never has. **The one record
    of keeping** (issue 277): the file is the artifact, and its existence alone says nothing."""
    kept_graph: Mapped[str | None] = mapped_column(String(71), nullable=True)
    """The fingerprint of the graph that was kept (`drafts.fingerprint`), so the listing can say
    *changed since kept* by content — whichever path edited the graph, and not for a rename."""
    kept_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    """`Pipeline.content_digest()` of the artifact written: the join key to a run."""


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
    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), index=True
    )
    """The draft this gate ran. A key (issue 274): nothing deletes a draft, and a gate cannot
    outlive one by being written against an id that names nothing."""
    who: Mapped[str] = mapped_column(String(200))
    """ATTRIBUTION, not authentication, exactly as on `PipelineDraft`."""
    gate: Mapped[str] = mapped_column(_one_of(Gate, 16, "gate"))
    state: Mapped[str] = mapped_column(_one_of(GateState, 16, "state"), index=True)
    """`queued` | `running` | `passed` | `failed`.

    A plain column rather than a native enum: adding a state to a Postgres enum is a migration,
    and `Gate` in `comeni_core.artifact.gates` is already the closed vocabulary that matters
    here. The service converts on the way out, so nothing downstream sees the string.
    """
    output: Mapped[str] = mapped_column(Text, default="")
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_gate_run_one_live",
            "draft_id",
            unique=True,
            postgresql_where=text("state IN ('queued', 'running')"),
        ),
    )
    """At most one *live* gate per draft (issue 278): two would write over each other's
    `main.nf` and stamp `pipeline.yml` in turn. The SQL spells out `services.gates.LIVE`, held to
    it by `test_the_live_gate_index_names_the_live_states`; `gates.request` refuses first, and
    this is the half that cannot be raced."""


class AiInvocation(Base):
    """One call to a model, and everything needed to judge it afterwards.

    The model transport is shared, so one audit table serves every agent; `agent` says whose
    call it was.

    Every field a response must record is a column here rather than a JSON blob, because these
    are exactly the fields a prompt evaluation aggregates over: which model, which prompt
    version, how long, how many tokens, and did it work.

    **No table holds a provider key**, and this is the one where one would go.
    `provider` and `model` name the lane; the credential lives in the environment and reaches
    `comeni_ai.access` and nothing else. `test_the_model_call_audit_holds_no_credential` is what
    says so in a way that fails.

    `prompt_digest` is over the *rendered* prompt, so two calls differing only in dossier
    content are distinguishable. `input_digests` carries the source and registry digests the
    call was made against, which is what makes an answer reproducible at all.
    """

    __tablename__ = "ai_invocation"
    shape_version: Mapped[int] = stamp("ai_invocation")

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent: Mapped[str] = mapped_column(_one_of(Agent, 32, "agent"), index=True)
    """Whose call: the builder's or the forge's."""
    purpose: Mapped[str] = mapped_column(String(24), index=True)
    """An `InvocationPurpose` for the forge, a `Purpose` for the builder — one member per
    committed prompt id. Held to its agent's set by `ck_ai_invocation_agent_purpose`."""
    model: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(64), default="")
    prompt_id: Mapped[str] = mapped_column(String(120), index=True)
    prompt_version: Mapped[str] = mapped_column(String(16), default="")
    prompt_digest: Mapped[str] = mapped_column(String(64))
    """Over the rendered prompt, not the template."""
    input_digests: Mapped[dict] = mapped_column(Json, default=dict)
    """Source and registry digests. What makes the answer reproducible."""
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(_one_of(InvocationState, 16, "state"), index=True)
    """An `InvocationState` value. `refused` — the answer did not validate — is separate from
    `failed` — the provider did not answer. Folding them hides the finding worth measuring."""
    failure_code: Mapped[str] = mapped_column(String(16), default="")
    """A declared diagnostic code, never a provider's own message."""
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Input tokens the provider served from its prompt cache (#183). Null when it said nothing."""
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Exactly what the model returned, admitted or refused (#182). A level-0 store: a reply can
    echo the person's words, and each future protection level decides whether it is kept."""
    response_cleared: Mapped[str | None] = mapped_column(
        _one_of(ReplyCleared, 16, "response_cleared"), nullable=True
    )
    """Why `response` is empty though the model answered: its draft was deleted, or the
    installation's retention limit passed (Part H). Null while the text is kept."""
    response_cleared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    """The authoring session a builder call belongs to (#191). No foreign key: other agents'
    rows have none, and a deleted session must not take its audit rows with it."""
    reply_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """How the reply's shape was asked for (#194): `in_prompt`, or the provider format the server
    enforced (`ollama`, …). Null on rows written before it was recorded."""
    """Nullable because a provider supplies them or does not, and a local Ollama lane often
    does not. A zero would be a measurement; a null is the absence of one."""

    __table_args__ = (
        # A purpose is scoped by its agent (`Purpose`'s docstring): both declare a `chat`, so
        # the pair is what is closed, not either column alone (issue 274).
        CheckConstraint(
            f"(agent = 'forge' AND purpose IN ({_quoted(InvocationPurpose)})) OR "
            f"(agent = 'builder' AND purpose IN ({_quoted(Purpose)}))",
            name="agent_purpose",
        ),
    )


@event.listens_for(AiInvocation, "before_insert")
def _no_text_for_a_deleted_session(mapper, connection, target) -> None:
    """**A reply that lands after its draft was deleted keeps no text** (Part H, review finding
    2). A model call can be in flight while a person deletes the draft; its row is written when
    the model answers, after the deletion cleared the rows that existed. `FOR SHARE` makes the
    two meet in one order: a deletion in progress is waited for, and one that waits on this
    insert clears it afterwards (`deletion.delete_draft` clears replies after the sessions go).
    """
    if target.session_id is None or target.response is None:
        return
    alive = connection.execute(
        text("SELECT 1 FROM pipeline_authoring_session WHERE id = :s FOR SHARE"),
        {"s": target.session_id},
    ).first()
    if alive is None:
        target.response = None
        target.response_cleared = ReplyCleared.DELETED.value
        target.response_cleared_at = datetime.now(UTC)


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
    `reviewed` is how far the walk has got.

    `row_version` is optimistic concurrency on the session itself: two tabs on one conversation
    is the ordinary case.
    """

    __tablename__ = "pipeline_authoring_session"
    shape_version: Mapped[int] = stamp("pipeline_authoring_session")

    retired: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    retirement_reason: Mapped[str | None] = mapped_column(
        _one_of(RetirementReason, 32, "retirement_reason"), nullable=True
    )
    pacing: Mapped[str | None] = mapped_column(_one_of(Pacing, 32, "pacing"), nullable=True)
    show_gaps: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), unique=True, index=True
    )
    """**Unique**, because the MVP does not support several sessions on one draft.

    Task 3 asks for this constraint if the design does not support several, and it does not:
    §2 gives a session one phase and one cursor, so two sessions on one draft would be two
    answers to *where are we* with nothing to arbitrate between them. A second conversation is
    a second draft."""
    phase: Mapped[str] = mapped_column(_one_of(Phase, 16, "phase"), index=True)
    """A `Phase` value. Indexed because sweeping for sessions stuck in `understanding` is how a
    job that never came back is found."""
    failed_from: Mapped[str | None] = mapped_column(
        _one_of(Phase, 16, "failed_from"), nullable=True
    )
    """The phase it was in when it failed, so retry resumes *that* one.

    **§2 draws two arrows out of `failed`** — back to `understanding` and to `resolving` — and
    `phase` alone cannot choose between them. Retry resumes the stage that failed rather than
    assuming every failure came from the model, and without the column a failed build would be
    retried as a prompt call.

    Nullable, and null is not a sentinel: a session that has never failed has no such phase, and
    `""` would be a phase name that is not one."""
    at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """The protocol node this session rests on (14.7.8.1): `mendel_authoring.protocol`'s id,
    written only by the dispatcher (`services/session.py`). The phase is read off that node.

    **Null on a row from before it existed**, and on a row a test moved by event: the node is
    then derived from the phase, the pending proposal and the pending turn
    (`session.rests_at`), and the first move writes it."""
    blueprint: Mapped[dict] = mapped_column(Json, default=dict)
    registry_digest: Mapped[str] = mapped_column(String(80), default="")
    """Which layer stack the blueprint was resolved against. A blueprint outlives the registry
    that produced it, and `MF0301`'s lesson one product over: a green answer about a layer that
    has since moved is a statement about something that no longer exists.

    **80, not 64.** It was 64 for a commit, which is a hex digest's length — and a `Digest` is
    `sha256:` plus 64 hex, seventy-one characters. Postgres would have refused the first
    blueprint ever stored, and nothing wrote one until Task 6."""
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    who: Mapped[str] = mapped_column(String(200), index=True)
    """ATTRIBUTION, not authentication, exactly as on `PipelineDraft` and `GateRun`."""
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
    shape_version: Mapped[int] = stamp("pipeline_authoring_turn")

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_authoring_session.id", ondelete="RESTRICT"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    """Explicit order within the session. See the class docstring: `at` is not an ordering."""
    role: Mapped[str] = mapped_column(_one_of(TurnRole, 16, "role"))
    """`person` or `assistant`. The same distinction `AuthoringRole` draws at the door."""
    state: Mapped[str] = mapped_column(_one_of(TurnState, 16, "state"), index=True)
    """A `TurnState` value — `pending`, `answered` or `failed`."""
    blocks: Mapped[list] = mapped_column(Json, default=list)
    """The assistant's turn as a list of discriminated blocks. Empty while `pending`."""
    text: Mapped[str] = mapped_column(Text, default="")
    """The person's own words. Free text with a real author — which door carries it and what
    may be in it is
    `tests/guards/test_egress.py`'s to declare, not this docstring's to assume."""
    base_revision: Mapped[int] = mapped_column(Integer, default=0)
    base_decision_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """The decisions as they stood when the person spoke (Part I.0, review I3): a model's heard
    change is recorded only if nothing moved since — a click made while the worker was busy wins.
    `None` on turns written before it existed."""
    ai_invocation_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("ai_invocation.id", ondelete="RESTRICT"), nullable=True
    )
    """The audit row for the call that produced this turn."""
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

    `by` was meant to distinguish a person from the model for the reason `model_override`
    exists on all three decision kinds — a pipeline an agent assembled must not read as one a
    person drew by hand (A130). **It does not yet:** it holds a name (issue 295).
    """

    __tablename__ = "pipeline_authoring_proposal"
    shape_version: Mapped[int] = stamp("pipeline_authoring_proposal")

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_authoring_session.id", ondelete="RESTRICT"), index=True
    )
    turn_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pipeline_authoring_turn.id", ondelete="RESTRICT"), nullable=True
    )
    kind: Mapped[str] = mapped_column(_one_of(ProposalKind, 24, "kind"), index=True)
    """A `BlockKind` value — which of the discriminated payloads `payload` holds."""
    payload: Mapped[dict] = mapped_column(Json, default=dict)
    """The block itself, stored whole and validated back through `authoring.types.parse_block`.
    Whole rather than shredded for `PipelineDraft.graph`'s reason: a schema that could hold half
    a proposal would be a second definition of what a proposal is."""
    @validates("payload")
    def _validated_payload(self, _key, payload):
        from mendel_api.authoring.envelopes import parse

        return parse(payload, kind=payload.get("offer")).model_dump(mode="json")

    preview_views: Mapped[dict | None] = mapped_column(
        Json, nullable=True, deferred=True, deferred_raiseload=True,
    )
    """Immutable derived alternatives. Ordinary reads must not load this large column."""

    @validates("preview_views")
    def _validated_previews(self, _key, value):
        from mendel_api.authoring.canvas import checked_previews

        return None if value is None else checked_previews(value, self.payload, self.id)

    state: Mapped[str] = mapped_column(_one_of(ProposalState, 16, "state"), index=True)
    """A `ProposalState` value — `pending`, `accepted`, `rejected` or `stale`."""
    chosen_option: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """An option **id**, never a value. See the class docstring."""
    actor_kind: Mapped[str | None] = mapped_column(
        _one_of(ActorKind, 16, "actor_kind"), nullable=True
    )
    by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    """Who settled it, once answered: an author's name or a model's id. Null while pending.

    **Not a vocabulary.** It once said `person`, `model` or `resolver`; the writers store a name,
    so whether a person or a model decided is not recorded here (issue 295)."""
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

    **A partial unique index where supported, and a service-level refusal everywhere**: the
    service answers with a sentence, and the
    index is the half that holds when two requests arrive together. The literal `'pending'` is
    `ProposalState.PENDING` spelled in SQL, and
    `test_the_pending_proposal_index_names_the_pending_state` holds the two together rather than
    this sentence doing it — a comment claiming a guard exists is worse than no comment.
    """


class SuggestionState(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"
    STALE = "stale"


class PipelineAuthoringSuggestion(Base):
    """A change the model offered and the person has not yet taken or set aside (Part I.0 §5.3).

    **Its own table, not a proposal**: a session holds one pending proposal — the open question
    or the goal card — and suggestions sit beside it. `change` is a `payloads.DecisionChange` dump;
    `heard` says whether it quoted the person (offered rather than recorded only because the goal
    was already confirmed). Applying one is the person's own change; the model is named by
    `invocation_id`, never recorded as the author.

    **A hand edit is offered here too** (one builder, #395): the engine reads the edit
    (`intent.read_edit`) and each reading is a suggestion with `edit` set — shared by every
    reading of one edit, taken or set aside together — and `says`, the engine's own sentence."""

    __tablename__ = "pipeline_authoring_suggestion"
    shape_version: Mapped[int] = stamp("pipeline_authoring_suggestion")

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_authoring_session.id", ondelete="RESTRICT"), index=True
    )
    change: Mapped[dict] = mapped_column(Json)
    heard: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    state: Mapped[str] = mapped_column(_one_of(SuggestionState, 16, "state"), index=True)
    invocation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    edit: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    says: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# Register draft-owned decisions in the same metadata Alembic and existing consumers read.
from mendel_api.decision_models import (  # noqa: E402, F401
    PipelineAsked,
    PipelineAskedRevision,
    PipelineEvidenceAccess,
    PipelineExclusion,
    PipelineExclusionRevision,
    PipelineFact,
    PipelineFactRevision,
    PipelineInput,
    PipelineInputRevision,
    PipelineObservation,
    PipelineParameter,
    PipelineParameterRevision,
    PipelinePhrasing,
    PipelineProducer,
    PipelineProducerRevision,
    PipelineReview,
    PipelineReviewRevision,
    PipelineRole,
    PipelineRoleRevision,
    PipelineSource,
    PipelineSourceRevision,
    PipelineWant,
    PipelineWantRevision,
)


class DecisionMigrationDisposition(StrEnum):
    ALREADY_ROWS = "already_rows"
    MANUAL = "manual"
    CONFIRMED = "confirmed"
    MANUAL_CONFIRMED = "manual_confirmed"
    GATHERING = "gathering"
    UNDERSTANDING = "understanding"
    AMBIGUOUS_MANUAL = "ambiguous_manual"
    OBSOLETE_PROTOCOL = "obsolete_protocol"


class PipelineDecisionMigration(Base):
    """Frozen legacy provenance; an archive, never a current decision fallback."""

    __tablename__ = "pipeline_decision_migration"
    shape_version: Mapped[int] = stamp("pipeline_decision_migration")
    draft_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("pipeline_draft.id", ondelete="RESTRICT"), primary_key=True
    )
    version: Mapped[str] = mapped_column(String(16))
    disposition: Mapped[str] = mapped_column(
        _one_of(DecisionMigrationDisposition, 24, "disposition")
    )
    reason: Mapped[str | None] = mapped_column(String(24), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict] = mapped_column(Json)


class SyncOutcome(StrEnum):
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"


class CatalogueSync(Base):
    """One sync of an upstream catalogue (forge part 1). A failed one is kept: the page says the
    catalogue is stale and why, and the modules stay as the last good sync left them."""

    __tablename__ = "catalogue_sync"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str] = mapped_column(_one_of(SyncOutcome, 16, "outcome"))
    modules: Mapped[int | None] = mapped_column(Integer, nullable=True)
    problems: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CatalogueModule(Base):
    """One upstream module as the last good sync read it.

    **No state column**: a module's state against the registry is computed on read
    (`mendel_forge.state`), because the registry changes without a sync. The columns are what is
    filtered or sorted; `document` is everything else the source declared. A module gone upstream
    is marked `gone`, never deleted.
    """

    __tablename__ = "catalogue_module"
    shape_version: Mapped[int] = stamp("catalogue_module")

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    path: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    tool_version: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    formats: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    upstream_changed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    search: Mapped[str] = mapped_column(Text)
    document: Mapped[dict] = mapped_column(Json)
    seen_in: Mapped[int] = mapped_column(
        Integer, ForeignKey("catalogue_sync.id", ondelete="RESTRICT"), index=True
    )
    gone: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    __table_args__ = (
        Index("ix_catalogue_module_topics", "topics", postgresql_using="gin"),
        Index("ix_catalogue_module_formats", "formats", postgresql_using="gin"),
        Index("ix_catalogue_module_search", "search", postgresql_using="gin",
              postgresql_ops={"search": "gin_trgm_ops"}),
    )
