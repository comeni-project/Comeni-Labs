"""④ Your consultant builds it with you (14.7.8.1; plan 1c). **What part 3 keeps**: resolving
the blueprint, offering a step, committing one, re-resolving when the registry moved, and the
canvas's own edits, as small functions part 3 calls. Part 3 replaces this stage's handlers."""

import logging
from typing import NamedTuple

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from mendel_authoring import commands as c
from mendel_authoring import state as st
from mendel_authoring.types import Command
from mendel_resolver.goal import Goal
from mendel_resolver.router import UnroutableError
from sqlalchemy import select

from mendel_api.authoring.types import Phase, ProposalState, TurnState
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)
from mendel_api.services import authoring_ai, registry, session
from mendel_api.services import blueprint as bp
from mendel_api.services.session import Ctx, handles, records
from mendel_api.settings import settings
from mendel_api.stages import _rows
from mendel_api.stages._rows import new_id as _id
from mendel_api.stages._rows import next_seq as _next_seq
from mendel_api.stages._rows import note as _note
from mendel_api.stages._rows import now as _now
from mendel_api.stages._rows import swap as _swap

log = logging.getLogger(__name__)

STEP = _rows.STEP

_TIER = {1: "settled", 2: "settled", 3: "a_rule", 4: "no_rule"}


class StepOutcome(NamedTuple):
    """What answering a step proposal did, and what is waiting now.

    §2: *return the new revision and next proposal* — both, from the one transaction that made
    them true, so a browser never has to re-read to learn what it just caused.
    """

    settlement: st.Settlement
    revision: int
    next_proposal: str | None
    phase: Phase


class ResolverFailed(Exception):
    """The resolver raised: `resolve` takes the `cant_build` arrow, then raises the cause."""


def pending_step_tier(session_id: str) -> int | None:
    """The pending step's tier, which card it is (`offer`, 14.7.8.1), or `None` at the end."""
    with session_scope() as db:
        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
                PipelineAuthoringProposal.kind == STEP,
            )
        )
        return None if pending is None else int(pending.payload["block"]["tier"])


def unbuildable(unroutable: UnroutableError) -> str:
    """MI0207's line, naming what is missing when the resolver said — never its raw message,
    which spells an empty state set as Python's `[]`."""
    if unroutable.missing is None:
        return coded("MI0207", "the confirmed goal cannot be built from what it says you have")
    type_id, states = unroutable.missing
    spelled = f"{type_id}[{', '.join(sorted(states))}]" if states else type_id
    return coded(
        "MI0207",
        f"this goal needs {spelled}, and nothing can make it from what you have — "
        "start again and say that you have one",
    )


def resolve_blueprint(session_id: str, *, client=None) -> str:
    """`resolve`'s work: the blueprint resolved, stored, and its first step offered (`stored`),
    or the goal found unbuildable (`cant_build`). Any other failure is raised.

    **Through the facade (Build) the resolver runs inside the action's transaction**: it is
    computation, and a failure between resolving and storing leaves nothing half-written (spec
    §11.2 of the consultant build). The session's `row_version` is read first and compared when
    the blueprint is written, so a session that moved while the resolver ran is refused rather
    than overwritten.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        if row.goal is None:
            raise ValueError(
                coded("MI0200", "this session has no confirmed goal to build from")
                + "\n  accept a goal first; a blueprint resolved from nothing is not a pipeline"
            )
        goal = Goal.model_validate(row.goal)
        version = row.row_version

    try:
        blueprint, calls = bp.resolve(goal)
    except UnroutableError as unroutable:
        # **A fact about the goal, so it goes in the conversation** (#115). Raised, it reached a
        # person as a toast and nowhere else, and a reload lost the reason entirely.
        _note(session_id, unbuildable(unroutable), code="MI0207")
        return "cant_build"
    except Exception as failure:
        # **The resolver's own failure, whatever its type** (final review of 1b):
        # `NoCandidatesError` and the rule errors are `ValueError`s, and are not a refusal of
        # the request. `resolve` lands the session on `failed`, then raises it.
        log.exception("resolving the blueprint for %s failed", session_id)
        raise ResolverFailed(failure) from failure
    if calls and client is not None:
        authoring_ai.record_calls(
            calls, client=client, registry=blueprint.registry, session_id=session_id
        )

    contracts = registry.stack().registry
    with session_scope() as db:
        _swap(
            db,
            session_id,
            version,
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
        if first is not None:
            offer_step(
                db, session_id, blueprint, first, revision=draft.revision, registry=contracts
            )
        return "stored"


def offer_step(db, session_id: str, blueprint, node_id: str, *, revision: int, registry) -> str:
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


def commit_step(db, proposal, draft, blueprint, node, *, option, by, registry) -> None:
    """Accepting a step: the draft's graph and provenance with it committed, the revision moved,
    and the option recorded on the proposal."""
    options: dict[str, str] = proposal.payload["options"]
    graph, provenance = bp.committed(
        blueprint,
        DraftGraph.model_validate(draft.graph),
        DraftProvenance.model_validate(draft.provenance or {}),
        node,
        contract_id=options[option],
        by=by,
        registry=registry,
    )
    draft.graph = graph.model_dump(mode="json")
    draft.provenance = provenance.model_dump(mode="json")
    draft.revision = draft.revision + 1
    draft.updated_at = _now()
    proposal.chosen_option = option


def reresolve(
    session_id: str, *, node, accepted, was, goal, version, revision, client=None
) -> StepOutcome:
    """The registry moved under a step (MI0206): resolve again, and offer the same step, or the
    next one the draft does not hold. Nothing about the draft changes."""
    contracts = registry.stack().registry
    fresh, calls = bp.resolve(goal)
    if calls and client is not None:
        authoring_ai.record_calls(
            calls, client=client, registry=fresh.registry, session_id=session_id
        )
    with session_scope() as db:
        _swap(
            db,
            session_id,
            version,
            blueprint=fresh.model_dump(mode="json"),
            registry_digest=fresh.registry,
        )
        again = node if node in fresh.order else next(
            (step for step in fresh.order if step not in accepted), None
        )
        offered = (
            offer_step(db, session_id, fresh, again, revision=revision, registry=contracts)
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


def settle(
    ctx: Ctx,
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
        ctx.session_id = session_row.id
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
            # Plain values, not ORM attributes, for `reresolve`.
            stale = dict(
                node=node,
                accepted={n.id for n in DraftGraph.model_validate(draft.graph).nodes},
                was=session_row.registry_digest,
                goal=Goal.model_validate(session_row.goal),
                version=session_row.row_version,
                revision=draft.revision,
            )
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
            session.check(session_row.id, Command.SETTLE_STEP.value)
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
                commit_step(
                    db, proposal, draft, blueprint, node, option=option, by=by,
                    registry=contracts,
                )

            proposal.state = outcome.state.value
            proposal.by = by
            proposal.settled_at = _now()
            db.flush()

            following = blueprint.after(node)
            _swap(db, session_row.id, session_row.row_version, cursor=session_row.cursor + 1)
            offered = (
                offer_step(db, session_row.id, blueprint, following, revision=draft.revision,
                           registry=contracts)
                if following
                else None
            )
            settled_in, revision_now = session_row.id, draft.revision

    if not moved:
        # The next step was offered inside the transaction (`offer_step`), so `offer` finds it.
        session.take(ctx, Command.SETTLE_STEP.value)
        return StepOutcome(outcome, revision_now, offered, session.current_phase(settled_in))
    return reresolve(ctx.session_id, client=client, **stale)


def start(ctx: Ctx, session_id: str, *, client=None) -> str | None:
    """Resolve the whole blueprint, store it, and offer its first step, by resuming the session
    at `resolve` (14.7.8.1). Returns the first proposal's id, or `None` for an empty blueprint
    (or one that could not be built: the session is then `failed`)."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        if session.rests_at(db, row) != "resolve":
            # Resuming anywhere else would rest there quietly: a build asked for from the wrong
            # place is refused by name, as it always was.
            raise ValueError(
                coded("MI0200", f"there is nothing to build from {row.phase}")
                + "\n  a blueprint is resolved only once a goal is confirmed"
            )
    ctx.session_id = session_id
    session.resume(session_id, ctx=ctx, client=client)
    return session.pending_id(session_id)


def _placement(row: PipelineAuthoringSession, draft: PipelineDraft | None, pending) -> dict:
    """Blueprint positions for the steps a person can see — accepted ones and the one on offer.

    **Only those.** The blueprint is the whole pipeline and it is private until revealed; handing
    the browser a coordinate for a step nobody has been shown yet would put the plan on the page
    as a set of empty slots. A step added by hand has no blueprint position and is simply absent
    here, for the canvas to place as it places any hand-drawn node.
    """
    placed = (row.blueprint or {}).get("placed") or {}
    visible = {n["id"] for n in (draft.graph or {}).get("nodes", [])} if draft else set()
    if pending is not None and pending.kind == STEP:
        visible.add(pending.payload.get("node"))
    return {node: {"x": at[0], "y": at[1]} for node, at in placed.items() if node in visible}


def record_edit(session_id: str, graph: DraftGraph, *, by: str) -> tuple[int, str | None]:
    """A direct edit to the session's draft, recorded in the transcript. Returns the new revision
    and the id of a re-offered proposal, if one was pending.

    **The receipt is composed here, from the difference, never sent by the browser.** A receipt is
    a fact the client already knew restated so the log stays complete — and a fact the server can
    derive is one a client cannot misstate. No model is called to narrate it.

    **An edit moves the revision**, because it changes the draft: a proposal offered against the
    old picture would otherwise apply to a pipeline that no longer looks that way. So a pending
    step proposal is marked stale and offered again at the new revision, in the same transaction —
    the session never ends up with nothing to answer because somebody moved a box.
    """
    from mendel_api.services import drafts

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        before = DraftGraph.model_validate(draft.graph)
        prior = DraftProvenance.model_validate(draft.provenance or {})
        summary = describe_edit(before, graph)
        if summary is None:
            return draft.revision, None

        draft.graph = graph.model_dump(mode="json")
        draft.provenance = drafts._restamped(graph, before, prior).model_dump(mode="json")
        draft.revision = draft.revision + 1
        draft.updated_at = _now()

        seq = _next_seq(db, session_id)
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq,
                role="assistant",
                state=TurnState.ANSWERED.value,
                blocks=[
                    {
                        "kind": "receipt",
                        "id": f"receipt-{seq}",
                        "summary": summary,
                        "revision": draft.revision,
                        "by": "person",
                    }
                ],
                text="",
                base_revision=draft.revision,
                at=_now(),
            )
        )

        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        reoffered = None
        if pending is not None and pending.kind == STEP and row.blueprint:
            pending.state = ProposalState.STALE.value
            pending.settled_at = _now()
            db.flush()
            blueprint = bp.Blueprint.model_validate(row.blueprint)
            present = {n.id for n in graph.nodes}
            # The same step again — unless the person just put it there by hand, in which case the
            # next step the draft does not already hold. Never nothing: a session with no pending
            # proposal and steps left is a session nobody can move forward.
            node = pending.payload["node"]
            while node is not None and node in present:
                node = blueprint.after(node)
            if node is not None:
                reoffered = offer_step(
                    db,
                    session_id,
                    blueprint,
                    node,
                    revision=draft.revision,
                    registry=registry.stack().registry,
                )
        return draft.revision, reoffered


def describe_edit(before: DraftGraph, after: DraftGraph) -> str | None:
    """One line saying what a direct edit did, or `None` when it did nothing.

    Named in the log's own vocabulary — step ids, upper-cased as the canvas draws them — and only
    what changed. A position move is not a change: `DraftGraph` has no coordinates.
    """
    was = {n.id: n for n in before.nodes}
    now = {n.id: n for n in after.nodes}
    parts: list[str] = []
    parts += [f"added {i.upper()}" for i in sorted(now.keys() - was.keys())]
    parts += [f"removed {i.upper()}" for i in sorted(was.keys() - now.keys())]
    for i in sorted(now.keys() & was.keys()):
        if now[i].contract_id != was[i].contract_id:
            parts.append(f"swapped {i.upper()} for {now[i].contract_id}")
        old = {p.name: p.value for p in was[i].params}
        for param in now[i].params:
            if old.get(param.name) != param.value:
                parts.append(f"set {i.upper()}.{param.name} to {param.value}")
        for name in sorted(old.keys() - {p.name for p in now[i].params}):
            parts.append(f"cleared {i.upper()}.{name}")
    edges = lambda g: {(e.from_node, e.from_port, e.to_node, e.to_port) for e in g.edges}  # noqa: E731
    if edges(before) != edges(after):
        parts.append("rewired the canvas")
    return ("you " + ", ".join(parts)) if parts else None


# ── the commands ─────────────────────────────────────────────────────────────────────────


@records(c.StartBuilding)
def _start(ctx: Ctx, cmd: c.StartBuilding) -> str | None:
    return start(ctx, cmd.session_id)


@records(c.SettleStep)
def _settle(ctx: Ctx, cmd: c.SettleStep) -> StepOutcome:
    return settle(
        ctx,
        cmd.proposal_id,
        ProposalState(cmd.decision),
        expected_revision=cmd.expected_revision,
        by=cmd.by,
        chosen_option=cmd.chosen_option,
    )


@records(c.RecordEdit)
def _edit(ctx: Ctx, cmd: c.RecordEdit) -> tuple[int, str | None]:
    return record_edit(cmd.session_id, DraftGraph.model_validate(cmd.graph), by=cmd.by)


# ── the handlers ─────────────────────────────────────────────────────────────────────────


@handles("resolve")
def resolve(ctx: Ctx) -> str | None:
    """**A command arriving rests here; resuming resolves** (ruling 9 of 14.7.8.1b). Build
    resumes in the same action (`start`)."""
    if ctx.command is not None:
        return None
    try:
        return resolve_blueprint(ctx.session_id, client=ctx.payload.get("client"))
    except ResolverFailed as failed:  # the resolver itself: `failed`, then raised
        ctx.raised = failed.__cause__
        return "cant_build"
    # Anything else raised here (MI0200, MI0201) is a refusal of the request: nothing moves.


@handles("offer")
def offer(ctx: Ctx) -> str:
    """Which card the pending step is — or the end. The step was offered by whatever came
    before (`resolve_blueprint`, `settle`)."""
    tier = pending_step_tier(ctx.session_id)
    return "nothing_left" if tier is None else _TIER[tier]
