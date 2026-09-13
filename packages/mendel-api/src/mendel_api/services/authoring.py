"""Authoring sessions, turns and proposals, made durable.

**The rules live in `authoring/state.py`; this file holds rows.** Every phase change goes through
`state.advance` and every settlement through `state.settle`, so the diagram in the plan's §2 is
enforced in one place rather than re-derived by each verb here. That is `forge_state.py`'s split
and it earns its keep the same way: the second caller is where a remembered `if` fails.

**Two things are compared on every mutating write**, and they catch different mistakes:

- `expected_revision` against `pipeline_draft.revision` — the client acted on a picture of the
  draft, and the picture is stale. This is the two-tab case, which §2 calls ordinary.
- `row_version` on the session — the *session* moved, even if the draft did not. A model answer
  landing after the person revised their goal is this one, and only this one.

Neither is a timestamp, for the reason `state.settle` records: two writes inside one clock tick
are indistinguishable by time, which is precisely when the comparison matters.

**Nothing here composes a prompt.** `services/authoring_ai.py` owns prompts and admission, and
`services/blueprint.py` owns resolving and committing a step. The one path from this file that
can reach a provider is `start_building` in Spawn mode, and only through a `Client` its caller
passes — so every test here runs against a database and, unless it hands one over, no model.
"""

import secrets
from datetime import UTC, datetime
from typing import NamedTuple

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from mendel_resolver.goal import Goal
from sqlalchemy import select, update

from mendel_api.authoring import state as st
from mendel_api.authoring.types import Mode, Phase, ProposalState, TurnState
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)
from mendel_api.services import authoring_ai, registry
from mendel_api.services import blueprint as bp
from mendel_api.settings import settings


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    """`secrets.token_hex(16)`, exactly as `PipelineDraft` uses.

    Opaque rather than serial for `routes/build.py`'s reason: the API may not take a path, and a
    guessable id is the next-worst thing.
    """
    return secrets.token_hex(16)


def open_session(draft_id: str, *, mode: Mode, who: str) -> str:
    """Start a conversation about a draft, or refuse if one is already open.

    **One session per draft**, which the unique index enforces and this refuses first — the same
    two-mechanism arrangement `forge_state.begin` uses, so a person reads a sentence rather than
    a constraint violation.
    """
    with session_scope() as session:
        if session.get(PipelineDraft, draft_id) is None:
            raise KeyError(draft_id)

        existing = session.scalar(
            select(PipelineAuthoringSession).where(
                PipelineAuthoringSession.draft_id == draft_id
            )
        )
        if existing is not None:
            raise ValueError(
                coded("MI0200", "this draft already has an authoring session")
                + f"\n  it is {existing.id}, in phase {existing.phase}"
            )

        session_id = _id()
        now = _now()
        session.add(
            PipelineAuthoringSession(
                id=session_id,
                draft_id=draft_id,
                mode=mode.value,
                phase=Phase.UNDERSTANDING.value,
                failed_from=None,
                goal=None,
                blueprint={},
                registry_digest="",
                cursor=0,
                row_version=1,
                who=who,
                created_at=now,
                updated_at=now,
            )
        )
    return session_id


def read(session_id: str) -> dict:
    """Everything a browser needs to draw the session, in one read.

    **The checkpoint's shape.** Task 3 asks that restarting the API between writing and reading
    changes nothing, and that is only checkable if one call returns the whole picture: phase,
    transcript, the pending proposal, the confirmed goal, and the draft's revision. Assembling it
    from four endpoints would make the checkpoint a statement about four caches.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)

        turns = db.scalars(
            select(PipelineAuthoringTurn)
            .where(PipelineAuthoringTurn.session_id == session_id)
            .order_by(PipelineAuthoringTurn.seq)
        ).all()
        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        return {
            "id": row.id,
            "draft_id": row.draft_id,
            "mode": row.mode,
            "phase": row.phase,
            "failed_from": row.failed_from,
            "goal": row.goal,
            "cursor": row.cursor,
            "row_version": row.row_version,
            "revision": draft.revision if draft else 0,
            "graph": draft.graph if draft else {},
            "turns": [
                {
                    "seq": t.seq,
                    "role": t.role,
                    "state": t.state,
                    "text": t.text,
                    "blocks": t.blocks,
                    "base_revision": t.base_revision,
                }
                for t in turns
            ],
            "pending_proposal": (
                None
                if pending is None
                else {
                    "id": pending.id,
                    "kind": pending.kind,
                    "payload": pending.payload,
                    "draft_revision": pending.draft_revision,
                }
            ),
        }


def move(session_id: str, event: st.Event, *, row_version: int, **values: object) -> Phase:
    """One phase change, compare-and-swap on the session's own version.

    `state.advance` decides *whether* and `UPDATE … WHERE row_version` decides *whether it is
    still ours*. Both are needed and they catch different mistakes — the first an illegal move,
    the second a legal move applied to a session somebody else already moved.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)

        current = Phase(row.phase)
        came_from = Phase(row.failed_from) if row.failed_from else None
        target = st.advance(current, event, came_from)

        # Cleared on every move that is not *into* failure, so a retried session does not carry
        # the phase of a failure it has already recovered from — `forge_state.move` clears
        # `failed_stage` for exactly this reason, and a stale one sends the next retry wrong.
        failed = st.failed_from(current).value if target is Phase.FAILED else None

        done = db.execute(
            update(PipelineAuthoringSession)
            .where(
                PipelineAuthoringSession.id == session_id,
                PipelineAuthoringSession.row_version == row_version,
            )
            .values(
                phase=target.value,
                failed_from=failed,
                row_version=row_version + 1,
                updated_at=_now(),
                **values,
            )
        )
        if done.rowcount != 1:
            raise ValueError(
                coded("MI0201", "this session moved while you were looking at it")
                + f"\n  you held version {row_version}; it is at {row.row_version}"
                + "\n  re-read it before acting on it"
            )
    return target


def say(session_id: str, text: str) -> int:
    """Record what a person said, and the pending turn that will answer it.

    **Two rows, written together.** The assistant's turn exists as `pending` from the moment the
    person's is accepted, so the transcript can draw the waiting. A browser inventing that
    placeholder locally would lose it on reload, which is the defect this closes rather than the
    tidiness it looks like.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        revision = draft.revision if draft else 0

        seq = _next_seq(db, session_id)
        now = _now()
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq,
                role="person",
                state=TurnState.ANSWERED.value,
                blocks=[],
                text=text,
                base_revision=revision,
                at=now,
            )
        )
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq + 1,
                role="assistant",
                state=TurnState.PENDING.value,
                blocks=[],
                text="",
                base_revision=revision,
                at=now,
            )
        )
        return seq + 1


def _next_seq(db, session_id: str) -> int:
    """The next position in the transcript.

    Derived from the rows rather than counted on the session, because a counter on the session is
    a second source of truth for the same fact. The unique index on `(session_id, seq)` is what
    makes a race here a refusal rather than two turns at one position.
    """
    highest = db.scalar(
        select(PipelineAuthoringTurn.seq)
        .where(PipelineAuthoringTurn.session_id == session_id)
        .order_by(PipelineAuthoringTurn.seq.desc())
        .limit(1)
    )
    return 0 if highest is None else highest + 1


def answer(
    session_id: str,
    seq: int,
    *,
    blocks: list,
    base_revision: int,
    invocation_id: str | None = None,
) -> bool:
    """Fill in a pending assistant turn, unless the draft has moved under it.

    **Returns `False` rather than raising when the answer is late.** A model call that finishes
    after the person revised their goal has not failed — it answered a question that is no longer
    being asked — and the turn is marked `failed` so the transcript says so. Raising would make
    the worker's ordinary case an exception path.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        current = draft.revision if draft else 0

        late = current != base_revision
        done = db.execute(
            update(PipelineAuthoringTurn)
            .where(
                PipelineAuthoringTurn.session_id == session_id,
                PipelineAuthoringTurn.seq == seq,
                PipelineAuthoringTurn.state == TurnState.PENDING.value,
            )
            .values(
                state=TurnState.FAILED.value if late else TurnState.ANSWERED.value,
                blocks=[] if late else blocks,
                ai_invocation_id=invocation_id,
                at=_now(),
            )
        )
        # rowcount 0 is a duplicate delivery: the turn is already answered, and re-answering it
        # would overwrite one account of what happened with another.
        return done.rowcount == 1 and not late


def propose(session_id: str, *, kind: str, payload: dict, turn_id: int | None = None) -> str:
    """Offer something, against the draft as it stands now.

    Refuses a second pending proposal rather than letting the partial unique index do it, so the
    caller reads a sentence. §2's MVP rule is one pending mutation proposal per session.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)

        outstanding = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        if outstanding is not None:
            raise ValueError(
                coded("MI0203", "this session already has a proposal waiting for an answer")
                + f"\n  it is {outstanding.id}"
            )

        proposal_id = _id()
        db.add(
            PipelineAuthoringProposal(
                id=proposal_id,
                session_id=session_id,
                turn_id=turn_id,
                kind=kind,
                payload=payload,
                state=ProposalState.PENDING.value,
                chosen_option=None,
                by=None,
                draft_revision=draft.revision if draft else 0,
                created_at=_now(),
                settled_at=None,
            )
        )
    return proposal_id


def decide(
    proposal_id: str,
    decision: ProposalState,
    *,
    expected_revision: int,
    by: str,
    chosen_option: str | None = None,
) -> st.Settlement:
    """Accept or reject a proposal, or say why it cannot be settled.

    Every refusal path leaves the draft untouched, which is the property Task 3 asks for: *a
    stale proposal never applies to a newer draft*. A stale one is additionally **marked** stale,
    because the person needs to see that the engine withdrew it rather than that they declined
    it — and that write is the one case where a refusal still changes a row.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, proposal_id)
        if row is None:
            raise KeyError(proposal_id)
        session_row = db.get(PipelineAuthoringSession, row.session_id)
        draft = db.get(PipelineDraft, session_row.draft_id)
        revision = draft.revision if draft else 0

        outcome = st.settle(
            current=ProposalState(row.state),
            proposal_revision=row.draft_revision,
            draft_revision=revision,
            expected_revision=expected_revision,
            decision=decision,
        )

        if outcome.state is not ProposalState(row.state):
            row.state = outcome.state.value
            row.settled_at = _now()
            if outcome.applies:
                row.by = by
                row.chosen_option = chosen_option

        if outcome.bumps_revision and draft is not None:
            draft.revision = revision + 1
            draft.updated_at = _now()

    return outcome


# ── the blueprint: resolved once, revealed a step at a time ───────────────────────────────


STEP = "step"
"""The proposal `kind` for a step offered from a blueprint."""


class StepOutcome(NamedTuple):
    """What answering a step proposal did, and what is waiting now.

    §2: *return the new revision and next proposal* — both, from the one transaction that made
    them true, so a browser never has to re-read to learn what it just caused.
    """

    settlement: st.Settlement
    revision: int
    next_proposal: str | None
    phase: Phase


def start_building(session_id: str, *, client=None) -> str | None:
    """Resolve the whole blueprint, store it, and offer its first step. `resolving → building`.

    **The resolve happens outside any transaction**, because it can take most of a second and in
    Spawn may reach a provider — and a row lock held across a model call is a lock held for as
    long as a provider feels like. The session's `row_version` is read first and compared when
    the blueprint is written, so a session that moved while the resolver ran is refused rather
    than overwritten.

    Returns the first proposal's id, or `None` for a blueprint with nothing in it.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        # Refuses with `MI0200` naming what the session can do instead.
        st.advance(Phase(row.phase), st.Event.BLUEPRINT_STORED)
        if row.goal is None:
            raise ValueError(
                coded("MI0200", "this session has no confirmed goal to build from")
                + "\n  accept a goal first; a blueprint resolved from nothing is not a pipeline"
            )
        goal = Goal.model_validate(row.goal)
        mode = Mode(row.mode)
        version = row.row_version

    try:
        blueprint, calls = bp.resolve(goal, mode=mode, client=client)
    except Exception:
        move(session_id, st.Event.BUILD_FAILED, row_version=version)
        raise
    if calls and client is not None:
        authoring_ai.record_calls(calls, client=client, registry=blueprint.registry)

    contracts = registry.stack().registry
    with session_scope() as db:
        _swap(
            db,
            session_id,
            version,
            phase=Phase.BUILDING,
            blueprint=blueprint.model_dump(mode="json"),
            registry_digest=blueprint.registry,
            cursor=0,
        )
        session_row = db.get(PipelineAuthoringSession, session_id)
        draft = db.get(PipelineDraft, session_row.draft_id)
        draft.goal = goal.model_dump(mode="json")
        if not DraftGraph.model_validate(draft.graph).nodes:
            # The measured profile rides on the graph, because `ir_of` builds its premises from
            # it — without it a tier-3 step re-materialises with nothing to have matched on.
            draft.graph = DraftGraph(profile=goal.profile).model_dump(mode="json")

        first = blueprint.after(None)
        if first is None:
            _swap(db, session_id, version + 1, phase=Phase.COMPLETE)
            return None
        return _offer(db, session_id, blueprint, first, revision=draft.revision, registry=contracts)


def settle_step(
    proposal_id: str,
    decision: ProposalState,
    *,
    expected_revision: int,
    by: str,
    chosen_option: str | None = None,
    client=None,
) -> StepOutcome:
    """Accept or reject one step, commit it, and offer the next — or say why not.

    **One transaction from the check to the next proposal.** The draft's graph, its provenance
    sidecar, its revision, the proposal's outcome, the session's cursor and the next proposal are
    written together or not at all; a draft revision that moved without the proposal recording
    it, or the reverse, is two accounts of one click.

    **The registry is compared before anything else.** If a layer moved since the blueprint was
    resolved, the proposal is marked `stale` and the blueprint is resolved again — `MI0206` — and
    nothing about the draft changes. An option chosen against a registry that no longer supplies
    it is not a choice anybody made.
    """
    contracts = registry.stack().registry
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        session_row = db.get(PipelineAuthoringSession, proposal.session_id)
        draft = db.get(PipelineDraft, session_row.draft_id)
        blueprint = bp.Blueprint.model_validate(session_row.blueprint)
        node = proposal.payload["node"]
        phase = Phase(session_row.phase)

        moved = (
            proposal.state == ProposalState.PENDING.value
            and bp.registry_digest([settings.registry_root]) != session_row.registry_digest
        )
        if moved:
            proposal.state = ProposalState.STALE.value
            proposal.settled_at = _now()
            # Plain values, not ORM attributes: everything below runs after this transaction has
            # closed, and reading a detached row's attribute there is a refresh with no session.
            session_id = session_row.id
            was = session_row.registry_digest
            goal = Goal.model_validate(session_row.goal)
            mode = Mode(session_row.mode)
            version = session_row.row_version
            revision = draft.revision
            accepted = {n.id for n in DraftGraph.model_validate(draft.graph).nodes}
        else:
            outcome = st.settle(
                current=ProposalState(proposal.state),
                proposal_revision=proposal.draft_revision,
                draft_revision=draft.revision,
                expected_revision=expected_revision,
                decision=decision,
            )
            if not outcome.applies:
                if outcome.state is not ProposalState(proposal.state):
                    proposal.state = outcome.state.value
                    proposal.settled_at = _now()
                return StepOutcome(outcome, draft.revision, None, phase)

            options: dict[str, str] = proposal.payload["options"]
            option = chosen_option or bp.KEEP
            if decision is ProposalState.ACCEPTED:
                if option not in options:
                    return StepOutcome(
                        st.Settlement(
                            ProposalState(proposal.state),
                            False,
                            coded("MI0205", "that option was never offered for this step")
                            + f"\n  offered: {', '.join(sorted(options))}",
                            False,
                        ),
                        draft.revision,
                        None,
                        phase,
                    )
                graph, provenance = bp.committed(
                    blueprint,
                    DraftGraph.model_validate(draft.graph),
                    DraftProvenance.model_validate(draft.provenance or {}),
                    node,
                    contract_id=options[option],
                    by=by,
                    registry=contracts,
                )
                draft.graph = graph.model_dump(mode="json")
                draft.provenance = provenance.model_dump(mode="json")
                draft.revision = draft.revision + 1
                draft.updated_at = _now()
                proposal.chosen_option = option

            proposal.state = outcome.state.value
            proposal.by = by
            proposal.settled_at = _now()
            db.flush()

            following = blueprint.after(node)
            target = st.advance(
                phase,
                st.Event.PROPOSAL_SETTLED if following else st.Event.NOTHING_LEFT,
            )
            _swap(
                db,
                session_row.id,
                session_row.row_version,
                phase=target,
                cursor=session_row.cursor + 1,
            )
            offered = (
                _offer(db, session_row.id, blueprint, following, revision=draft.revision,
                       registry=contracts)
                if following
                else None
            )
            return StepOutcome(outcome, draft.revision, offered, target)

    # The registry moved. Resolve again outside the transaction, for `start_building`'s reason.
    fresh, calls = bp.resolve(goal, mode=mode, client=client)
    if calls and client is not None:
        authoring_ai.record_calls(calls, client=client, registry=fresh.registry)
    with session_scope() as db:
        _swap(
            db,
            session_id,
            version,
            phase=Phase.BUILDING,
            blueprint=fresh.model_dump(mode="json"),
            registry_digest=fresh.registry,
        )
        again = node if node in fresh.order else next(
            (step for step in fresh.order if step not in accepted), None
        )
        offered = (
            _offer(db, session_id, fresh, again, revision=revision, registry=contracts)
            if again
            else None
        )
    refusal = (
        coded("MI0206", "the registry changed after this step was proposed")
        + f"\n  it was resolved against {was}; it is {fresh.registry}"
        + "\n  nothing was applied — the blueprint was resolved again, and a fresh proposal waits"
    )
    return StepOutcome(
        st.Settlement(ProposalState.STALE, False, refusal, False), revision, offered, Phase.BUILDING
    )


def _swap(db, session_id: str, version: int, *, phase: Phase, **values: object) -> None:
    """Move a session inside an open transaction, compare-and-swap on its version.

    `move` opens its own transaction, which is right for a lone phase change and wrong here,
    where the phase is one of several writes that must land together.
    """
    done = db.execute(
        update(PipelineAuthoringSession)
        .where(
            PipelineAuthoringSession.id == session_id,
            PipelineAuthoringSession.row_version == version,
        )
        .values(
            phase=phase.value,
            failed_from=None,
            row_version=version + 1,
            updated_at=_now(),
            **values,
        )
    )
    if done.rowcount != 1:
        raise ValueError(
            coded("MI0201", "this session moved while the blueprint was being resolved")
            + f"\n  it was at version {version} when the work started"
            + "\n  re-read it before acting on it"
        )


def _offer(db, session_id: str, blueprint, node_id: str, *, revision: int, registry) -> str:
    """Store one step proposal as `pending`, against the draft as it stands now."""
    proposal_id = _id()
    session_row = db.get(PipelineAuthoringSession, session_id)
    draft = db.get(PipelineDraft, session_row.draft_id)
    present = frozenset(node.id for node in DraftGraph.model_validate(draft.graph).nodes)
    db.add(
        PipelineAuthoringProposal(
            id=proposal_id,
            session_id=session_id,
            turn_id=None,
            kind=STEP,
            payload=bp.proposal(blueprint, node_id, registry=registry, present=present),
            state=ProposalState.PENDING.value,
            chosen_option=None,
            by=None,
            draft_revision=revision,
            created_at=_now(),
            settled_at=None,
        )
    )
    db.flush()
    return proposal_id


# ── the transport's verbs: starting, grounding a turn, goals, retrying ────────────────────


UNTITLED = "Untitled analysis"
"""What an authored draft is called until somebody names it.

**Not derived from the prompt.** A first sentence is the likeliest place for a sample name or a
cohort label to appear, and a draft's name is shown in lists and carried into a kept artifact's
directory — §2 already excludes draft labels from what a model is shown, and a name *made from*
the prompt would put the prompt somewhere that exclusion was never meant to reach.
"""


def begin(prompt: str, *, mode: Mode, who: str) -> tuple[str, int]:
    """An empty draft, a session about it, and the first turn — returns the session and the
    pending assistant turn's `seq`.

    Three writes that are one act for a person, and they are made in order so that a failure
    part-way leaves nothing a person could open: the draft exists before the session that points
    at it, and the turn is written last.
    """
    from mendel_api.services import drafts

    draft_id = drafts.create(DraftGraph(), UNTITLED, who)
    session_id = open_session(draft_id, mode=mode, who=who)
    return session_id, say(session_id, prompt)


class TurnContext(NamedTuple):
    """What one model call is grounded on, read in one transaction so the parts agree.

    §2: *ground every authoring call on the confirmed goal, current known step ids and
    contracts, current pending options, registry digest, and bounded tail — not on the transcript
    alone.* Each of those is a field here, and nothing else is, which is why a draft's label is
    not among them.
    """

    phase: Phase
    prompt: str
    tail: list[tuple[str, str]]
    revision: int
    goal: Goal | None
    steps: list[tuple[str, str]]
    options: list[str]
    registry: str | None


def turn_context(session_id: str, seq: int) -> TurnContext | None:
    """The grounding for assistant turn `seq`, or `None` when that turn is not pending.

    `None` is how a duplicate delivery is recognised **before** a model call is spent, which the
    queue's job id alone cannot promise once Redis has forgotten the id.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        turns = db.scalars(
            select(PipelineAuthoringTurn)
            .where(PipelineAuthoringTurn.session_id == session_id)
            .order_by(PipelineAuthoringTurn.seq)
        ).all()
        target = next((t for t in turns if t.seq == seq), None)
        if target is None or target.role != "assistant" or target.state != TurnState.PENDING.value:
            return None

        earlier = [t for t in turns if t.seq < seq]
        person = next((t for t in reversed(earlier) if t.role == "person"), None)
        tail = [
            ("person" if t.role == "person" else "model", _spoken(t))
            for t in earlier
            if t is not person and (t.role == "person" or t.state == TurnState.ANSWERED.value)
        ]
        draft = db.get(PipelineDraft, row.draft_id)
        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        goal = row.goal or (pending.payload.get("goal") if pending is not None else None)
        return TurnContext(
            phase=Phase(row.phase),
            prompt=person.text if person is not None else "",
            tail=[(role, text) for role, text in tail if text],
            revision=draft.revision if draft else 0,
            goal=Goal.model_validate(goal) if goal else None,
            steps=[
                (node.id, node.contract_id)
                for node in DraftGraph.model_validate(draft.graph).nodes
            ]
            if draft
            else [],
            options=sorted(pending.payload.get("options", {})) if pending is not None else [],
            registry=row.registry_digest or None,
        )


def _spoken(turn: PipelineAuthoringTurn) -> str:
    """What an assistant turn *said*, for the tail — the prose of its blocks, never their ids.

    A goal summary is its three sentences; a narrative or a notice is its text. Structured
    blocks — a step proposal, a question's options — are the engine's own vocabulary and reach
    the model through `steps` and `options`, where they are held to admission, rather than as
    prose it could quote back as if it had authored them.
    """
    if turn.role == "person":
        return turn.text
    said = []
    for block in turn.blocks or []:
        if block.get("kind") == "goal_summary":
            said.append(f"{block['have']} {block['do']} {block['get']}")
        elif block.get("kind") in ("narrative", "notice"):
            said.append(block.get("text", ""))
    return " ".join(part for part in said if part)


def current_phase(session_id: str) -> Phase:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        return Phase(row.phase)


def withdraw_pending(session_id: str, *, by: str) -> None:
    """Reject whatever is pending — a goal summary the person has just corrected in prose."""
    with session_scope() as db:
        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        if pending is not None:
            pending.state = ProposalState.REJECTED.value
            pending.by = by
            pending.settled_at = _now()


def decide_goal(
    proposal_id: str, decision: ProposalState, *, expected_revision: int, by: str
) -> tuple[st.Settlement, Phase]:
    """Accept or reject a goal summary. Accepting stores it as the confirmed goal.

    `goal_review → resolving` on accept, `goal_review → understanding` on reject — §2's two
    arrows out of that phase, through `move` so the diagram is enforced where every other move is.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringProposal, proposal_id)
        if row is None:
            raise KeyError(proposal_id)
        session_id = row.session_id
        goal = row.payload.get("goal")

    outcome = decide(proposal_id, decision, expected_revision=expected_revision, by=by)
    if outcome.refusal is not None:
        return outcome, current_phase(session_id)

    with session_scope() as db:
        version = db.get(PipelineAuthoringSession, session_id).row_version
    if decision is ProposalState.ACCEPTED:
        return outcome, move(session_id, st.Event.GOAL_ACCEPTED, row_version=version, goal=goal)
    return outcome, move(session_id, st.Event.GOAL_REVISED, row_version=version)


def retry(session_id: str) -> tuple[Phase, int | None]:
    """Leave `failed` for whichever phase failed. Returns the phase, and a new pending turn's
    `seq` when the retry needs a model to answer again.

    **A new turn rather than re-opening the failed one.** The failed turn is the record that the
    call failed — its notice says why — and overwriting it would erase the one thing a person
    trying to understand a flaky provider needs to see.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        version = row.row_version

    target = move(session_id, st.Event.RETRY, row_version=version)
    if target is not Phase.UNDERSTANDING:
        return target, None

    with session_scope() as db:
        draft = db.get(PipelineDraft, db.get(PipelineAuthoringSession, session_id).draft_id)
        seq = _next_seq(db, session_id)
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq,
                role="assistant",
                state=TurnState.PENDING.value,
                blocks=[],
                text="",
                base_revision=draft.revision if draft else 0,
                at=_now(),
            )
        )
    return target, seq
