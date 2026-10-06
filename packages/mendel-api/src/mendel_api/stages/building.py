"""④ Your consultant builds it with you (14.7.8.3b, spec §13 of the consultant build).

The walk: after the blueprint is resolved, an overview count; the Pacing fork; then each step in
the blueprint's order, placed at once or stopped on — a fact a rule lacks, a choice no rule
settles, a registry gap under the Dev fork, or *continue* — and the wrap-up. What each step needs
is the build plan's (`mendel_authoring.plan`); this module turns it into rows."""

import logging
from typing import NamedTuple

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from mendel_authoring import commands as c
from mendel_authoring import state as st
from mendel_authoring.blueprint import edges_touching
from mendel_authoring.needs import NeedKind
from mendel_authoring.pacing import Pacing, waits
from mendel_authoring.plan import BuildPlan, PlannedStep, plan_of
from mendel_authoring.types import Command
from mendel_resolver.goal import Goal
from mendel_resolver.router import UnroutableError
from sqlalchemy import select

from mendel_api.authoring.types import (
    Fact,
    FactKind,
    FactSource,
    Narrative,
    Option,
    Phase,
    ProposalState,
    Question,
    Receipt,
    StepProposal,
    TurnState,
)
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)
from mendel_api.services import authoring_ai, declared, registry, session
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
PACING_PROPOSAL = "pacing"


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
    """`resolve`'s work: the blueprint resolved and stored (`stored`), the walk's cursor and
    pacing reset, or the goal found unbuildable (`cant_build`). Any other failure is raised.

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

    with session_scope() as db:
        _swap(
            db,
            session_id,
            version,
            blueprint=blueprint.model_dump(mode="json"),
            registry_digest=blueprint.registry,
            cursor=0,
            pacing=None,
        )
        session_row = db.get(PipelineAuthoringSession, session_id)
        draft = db.get(PipelineDraft, session_row.draft_id)
        draft.goal = goal.model_dump(mode="json")
        if not DraftGraph.model_validate(draft.graph).nodes:
            # The measured profile rides on the graph, because `ir_of` builds its premises from
            # it — without it a tier-3 step re-materialises with nothing to have matched on.
            draft.graph = DraftGraph(profile=goal.profile).model_dump(mode="json")
        return "stored"


def _plan(row) -> tuple[bp.Blueprint, BuildPlan]:
    blueprint = bp.Blueprint.model_validate(row.blueprint)
    return blueprint, plan_of(blueprint, declared.of(registry.stack()))


def step_payload(blueprint, planned: PlannedStep, present: frozenset[str]) -> dict:
    """The stored payload offering one step: the card a person reads, and the options it allows.

    A choice's options are the producer decision's candidates (spec §13.6), never the candidate
    service's; every other step offers only `keep`. `edges` are the wires accepting it adds to
    the steps already in the draft, so the browser can apply an acceptance optimistically."""
    step = blueprint.step(planned.node)
    producer = next((ch for ch in planned.need.choices if ch.key.startswith("producer:")), None)
    others = (
        [str(cand.value) for cand in producer.candidates if cand.value != planned.contract]
        if producer
        else []
    )
    minted = {f"alt_{i}": contract for i, contract in enumerate(others, start=1)}
    contract = registry.stack().registry.get(planned.contract)
    block = StepProposal(
        id=f"step-{planned.node}",
        node=planned.node,
        contract=planned.contract,
        consumes=sorted({port.type_id for port in contract.consumes if port.type_id}),
        produces=sorted({output.type_id for output in contract.produces}),
        reason=step.why.reason,
        tier=int(step.why.tier),
        alternatives=[Option(id=k, label=v) for k, v in minted.items()],
        brief=planned.brief,
        need=planned.need,
        gaps=planned.gaps,
    )
    here = set(present) | {planned.node}
    wires = [
        edge.model_dump(mode="json")
        for edge in edges_touching(blueprint, planned.node)
        if edge.from_node in here and edge.to_node in here
    ]
    return {
        "node": planned.node,
        "block": block.model_dump(mode="json"),
        "options": {bp.KEEP: planned.contract, **minted},
        "edges": wires,
    }


def _offer(db, row, blueprint, planned: PlannedStep) -> str:
    """Store one step's card as `pending`, against the draft as it stands now."""
    draft = db.get(PipelineDraft, row.draft_id)
    present = frozenset(n.id for n in DraftGraph.model_validate(draft.graph).nodes)
    proposal_id = _id()
    db.add(
        PipelineAuthoringProposal(
            id=proposal_id,
            session_id=row.id,
            turn_id=None,
            kind=STEP,
            payload=step_payload(blueprint, planned, present),
            state=ProposalState.PENDING.value,
            chosen_option=None,
            by=None,
            draft_revision=draft.revision,
            created_at=_now(),
            settled_at=None,
        )
    )
    db.flush()
    return proposal_id


def _place(db, row, blueprint, planned: PlannedStep) -> None:
    """Place a step that does not wait: offered and accepted by the engine in one go, so the
    history keeps its card, and the cursor moves on."""
    proposal = db.get(PipelineAuthoringProposal, _offer(db, row, blueprint, planned))
    draft = db.get(PipelineDraft, row.draft_id)
    commit_step(
        db, proposal, draft, blueprint, planned.node, option=bp.KEEP, by="engine",
        registry=registry.stack().registry,
    )
    proposal.state = ProposalState.ACCEPTED.value
    proposal.by = "engine"
    proposal.settled_at = _now()
    row.cursor = row.cursor + 1
    db.flush()


def _open_facts(row) -> set[str]:
    """The facts a person answered *not sure* to: asked once, never again (Review Focus 2)."""
    return {
        f["subject"] for f in row.facts or [] if f.get("source") == FactSource.OPEN.value
    }


def offer_fact(db, row, subject: str) -> None:
    """The fact-first card: gathering's own question for `subject`, without *upload* (spec
    §13.6), answered through `AnswerGap`."""
    from mendel_api.services import gaps as gap_rules
    from mendel_api.stages import gathering

    stack = registry.stack()
    facts = [Fact.model_validate(f) for f in row.facts or []]
    gap = gap_rules.Gap(
        kind=FactKind.MEASUREMENT, subject=subject,
        why="a rule needs it to choose this step's tool",
    )
    options = {
        key: label
        for key, label in gathering._gap_options(gap, stack, facts).items()
        if key != gathering.UPLOAD
    }
    # *Not sure* was offered as the upload; with no upload here, it is offered as itself.
    options.setdefault("not_sure", gathering._UNSURE["not_sure"])
    question = gathering._gap_question(gap, options, stack, row.row_version)
    db.add(
        PipelineAuthoringProposal(
            id=_id(),
            session_id=row.id,
            turn_id=None,
            kind=gathering.GAP,
            payload={
                "subject": subject,
                "kind": FactKind.MEASUREMENT.value,
                "why": gap.why,
                "options": options,
                "block": question.model_dump(mode="json"),
            },
            state=ProposalState.PENDING.value,
            chosen_option=None,
            by=None,
            draft_revision=db.get(PipelineDraft, row.draft_id).revision,
            created_at=_now(),
            settled_at=None,
        )
    )
    db.flush()


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


def settle(
    ctx: Ctx,
    proposal_id: str,
    decision: ProposalState,
    *,
    expected_revision: int,
    by: str,
    chosen_option: str | None = None,
) -> StepOutcome:
    """Accept or reject one step, then walk on (spec §13.6): the arrow is `continue` from a
    step's card and `choose` from a choice; `step` offers what comes next.

    **One transaction from the check to the next card.** **The registry is compared first**: if
    a layer moved since the blueprint was resolved, the card is marked `stale`, the blueprint is
    resolved again, and the walk re-offers the same step from it — `MI0206` — with nothing
    applied. An option chosen against a registry that no longer supplies it is not a choice."""
    contracts = registry.stack().registry
    moved_goal: Goal | None = None
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
        arrow = (
            Command.CONTINUE.value
            if session.rests_at(db, session_row) == "held"
            else Command.CHOOSE.value
        )
        was = session_row.registry_digest
        if (
            proposal.state == ProposalState.PENDING.value
            and bp.registry_digest([settings.registry_root]) != was
        ):
            proposal.state = ProposalState.STALE.value
            proposal.settled_at = _now()
            moved_goal = Goal.model_validate(session_row.goal)
            revision_now = draft.revision
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
            session.check(session_row.id, arrow)
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
            session_row.cursor = session_row.cursor + 1
            db.flush()
            revision_now = draft.revision

    if moved_goal is not None:
        fresh, _ = bp.resolve(moved_goal)
        with session_scope() as db:
            row = db.get(PipelineAuthoringSession, ctx.session_id)
            row.blueprint = fresh.model_dump(mode="json")
            row.registry_digest = fresh.registry
        session.take(ctx, arrow)
        refusal = (
            coded("MI0206", "the registry changed after this step was proposed")
            + f"\n  it was resolved against {was}; it is {fresh.registry}"
            + "\n  nothing was applied — the blueprint was resolved again, and the step waits"
        )
        return StepOutcome(
            st.Settlement(ProposalState.STALE, False, refusal, False),
            revision_now,
            session.pending_id(ctx.session_id),
            session.current_phase(ctx.session_id),
        )
    session.take(ctx, arrow)
    return StepOutcome(
        outcome, revision_now, session.pending_id(ctx.session_id),
        session.current_phase(ctx.session_id),
    )


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
            blueprint, plan = _plan(row)
            present = {n.id for n in graph.nodes}
            # The same step again — unless the person just put it there by hand, in which case the
            # next step the draft does not already hold. Never nothing: a session with no pending
            # proposal and steps left is a session nobody can move forward.
            while row.cursor < len(plan.steps) and plan.steps[row.cursor].node in present:
                row.cursor = row.cursor + 1
            if row.cursor < len(plan.steps):
                reoffered = _offer(db, row, blueprint, plan.steps[row.cursor])
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


@records(c.ChoosePacing)
def _choose_pacing(ctx: Ctx, cmd: c.ChoosePacing) -> None:
    """The pacing question answered: recorded on the session, and the walk goes on."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, cmd.proposal_id)
        if proposal is None or proposal.kind != PACING_PROPOSAL:
            raise ValueError(coded("MI0205", "that proposal is not the pacing question"))
        if cmd.option not in proposal.payload["options"]:
            raise ValueError(
                coded("MI0205", "that is not one of the paces offered")
                + f"\n  it offered: {', '.join(proposal.payload['options'])}"
            )
        ctx.session_id = proposal.session_id
        session.check(proposal.session_id, Command.CHOOSE_PACING.value)
        proposal.state = ProposalState.ACCEPTED.value
        proposal.by = cmd.by
        proposal.chosen_option = cmd.option
        proposal.settled_at = _now()
        db.get(PipelineAuthoringSession, proposal.session_id).pacing = cmd.option
    session.take(ctx, Command.CHOOSE_PACING.value)


@records(c.RecordEdit)
def _edit(ctx: Ctx, cmd: c.RecordEdit) -> tuple[int, str | None]:
    return record_edit(cmd.session_id, DraftGraph.model_validate(cmd.graph), by=cmd.by)


# ── the handlers ─────────────────────────────────────────────────────────────────────────


@handles("resolve")
def resolve(ctx: Ctx) -> str | None:
    """**A command arriving rests here; resuming resolves** (ruling 9 of 14.7.8.1b): the build
    resumes in the same action (`start`)."""
    if ctx.command is not None:
        return None
    try:
        return resolve_blueprint(ctx.session_id, client=ctx.payload.get("client"))
    except ResolverFailed as failed:  # the resolver itself: `failed`, then raised
        ctx.raised = failed.__cause__
        return "cant_build"
    # Anything else raised here (MI0200, MI0201) is a refusal of the request: nothing moves.


@handles("overview")
def overview(ctx: Ctx) -> None:
    """How many steps, and how many need the person, counted off the plan (spec §4.5)."""
    with session_scope() as db:
        _, plan = _plan(db.get(PipelineAuthoringSession, ctx.session_id))
    total, needing = len(plan.steps), len(plan.needing())
    text = f"{total} step{'s' * (total != 1)}; " + (
        "none need you." if needing == 0 else f"{needing} need{'s' * (needing == 1)} you."
    )
    _rows.engine_turn(
        ctx.session_id,
        lambda seq: [Narrative(id=f"overview-{seq}", text=text).model_dump(mode="json")],
    )
    return None


def _pace(ctx: Ctx, pacing: Pacing) -> None:
    with session_scope() as db:
        db.get(PipelineAuthoringSession, ctx.session_id).pacing = pacing.value
    return None


@handles("together")
def together(ctx: Ctx) -> None:
    return _pace(ctx, Pacing.TOGETHER)


@handles("quiet")
def quiet(ctx: Ctx) -> None:
    return _pace(ctx, Pacing.STOP_WHERE_NEEDED)


@handles("ask_pacing")
def ask_pacing(ctx: Ctx) -> None:
    """Pacing is *ask me every time*: the question, as a `Question` the person answers."""
    options = {
        Pacing.TOGETHER.value: "Go through it together",
        Pacing.STOP_WHERE_NEEDED.value: "Set it up, stop only where you need me",
    }
    question = Question(
        id=f"pacing-{ctx.session_id}",
        asks="How should we go through the build?",
        why_open="Pacing is set to ask me every time.",
        options=[Option(id=k, label=v) for k, v in options.items()],
    )
    _rows.propose(
        ctx.session_id,
        kind=PACING_PROPOSAL,
        payload={"options": options, "block": question.model_dump(mode="json")},
    )
    return None


@handles("step")
def step(ctx: Ctx) -> str:
    """The walk (spec §13.6): place every step that does not wait, in this one entry, and leave
    on the first stop. **The need is decided before the gaps** (Review Focus 1 of the 3b plan):
    a step that needs a fact stops on the fact whatever Dev mode says."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        blueprint, plan = _plan(row)
        stops = set(waits(plan, Pacing(row.pacing or Pacing.TOGETHER.value)))
        while row.cursor < len(plan.steps):
            planned = plan.steps[row.cursor]
            need = planned.need
            unasked = [f for f in need.facts if f not in _open_facts(row)]
            if need.kind is NeedKind.FACT and unasked:
                offer_fact(db, row, unasked[0])
                return "needs_fact"
            if any(choice.key.startswith("producer:") for choice in need.choices):
                _offer(db, row, blueprint, planned)
                return "needs_choice"
            if planned.gaps:
                return "a_gap"
            if planned.node in stops or need.kind is not NeedKind.NOTHING:
                _offer(db, row, blueprint, planned)
                return "held"
            _place(db, row, blueprint, planned)
        return "none_left"


@handles("show_gap")
def show_gap(ctx: Ctx) -> None:
    """Dev mode on: the step's card, its gaps marked; it rests on `held` for *Continue*."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        blueprint, plan = _plan(row)
        _offer(db, row, blueprint, plan.steps[row.cursor])
    return None


@handles("route_around")
def route_around(ctx: Ctx) -> str:
    """Dev mode off: **the gap is not shown, the step still is** — the pacing decides, as for any
    step: its card waits under *together*, it is placed at once otherwise. A setting with no
    declared domain is left to the run (issue 252)."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        blueprint, plan = _plan(row)
        planned = plan.steps[row.cursor]
        if planned.node in waits(plan, Pacing(row.pacing or Pacing.TOGETHER.value)):
            _offer(db, row, blueprint, planned)
            return "held"
        _place(db, row, blueprint, planned)
    return "placed"


def with_facts(goal: Goal, facts: list[Fact]) -> Goal:
    """The confirmed goal, with every measured fact it does not already hold added to its
    profile. **Starts from the confirmed goal**, not from gathering's records, so an edit the
    person made on the goal card stands; an open fact stays absent (protocol rule 6)."""
    from comeni_core.declared.measurement import MeasuredEntry

    from mendel_api.stages import gathering

    held = {m.measurement for m in goal.profile.measurements}
    # Through `profile_of`, which validates every entry (invariant 15's one constructor): the
    # goal's own measurements re-entered as they are, then each new fact.
    profile = registry.stack().measurements.profile_of(
        [
            MeasuredEntry(
                m.measurement, m.value, m.source, m.by, tuple(m.pieces), m.evidence
            )
            for m in goal.profile.measurements
        ]
        + [
            MeasuredEntry(
                f.subject,
                f.value,
                gathering._SOURCE[f.source],
                pieces=tuple(f.pieces),
                evidence=gathering._goal_evidence(f.evidence),
            )
            for f in facts
            if f.kind is FactKind.MEASUREMENT
            and f.source is not FactSource.OPEN
            and f.subject not in held
        ]
    )
    return goal.model_copy(update={"profile": profile})


@handles("reresolve")
def reresolve(ctx: Ctx) -> None:
    """A fact answered: the confirmed goal with it, resolved again, the cursor kept."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        goal = with_facts(
            Goal.model_validate(row.goal), [Fact.model_validate(f) for f in row.facts or []]
        )
    fresh, _ = bp.resolve(goal)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        row.goal = goal.model_dump(mode="json")
        row.blueprint = fresh.model_dump(mode="json")
        row.registry_digest = fresh.registry
    return None


@handles("wrap")
def wrap(ctx: Ctx) -> None:
    """The wrap-up (spec §4.4), as a `Receipt`: what you'll get, what you need, who decided."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        _, plan = _plan(row)
        revision = db.get(PipelineDraft, row.draft_id).revision
    w = plan.wrap_up
    needed = [i.id for i in w.inputs] + w.unset
    lines = [
        "You'll get: " + (", ".join(g.id for g in w.gets) or "nothing named") + ".",
        "To run it you need: " + (", ".join(needed) or "nothing more") + ".",
        "Decided: "
        + ", ".join(f"{d.count} at tier {d.tier} by {d.source}" for d in w.decided)
        + ".",
    ]
    _rows.engine_turn(
        ctx.session_id,
        lambda seq: [
            Receipt(
                id=f"wrap-{seq}", summary=" ".join(lines), revision=revision, by="resolver"
            ).model_dump(mode="json")
        ],
    )
    return None
