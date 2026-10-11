"""④ The walk (14.7.8.3c, spec §14 of the consultant build): **the blueprint decides, the walk
reviews.**

After the blueprint is resolved: an overview count; the Pacing fork, then the Dev fork, both
recorded as one policy; then each step in the blueprint's order, placed quietly or stopped on —
a tier-4 step, a registry gap Dev mode shows, or every step under *together* — and the wrap-up.
A step's card is continued here (`SettleStep`) or changed in `amending` (`Amend`). The draft is
always the blueprint's reviewed steps (`amending.project`), never built up by appending.
"""

import logging
from typing import NamedTuple

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph
from mendel_authoring import commands as c
from mendel_authoring import state as st
from mendel_authoring.draft import drafted, next_step
from mendel_authoring.pacing import Pacing, Policy, stops
from mendel_authoring.types import Command
from mendel_resolver.router import UnroutableError

from mendel_api.authoring.types import (
    Narrative,
    Option,
    Phase,
    ProposalKind,
    ProposalState,
    Question,
    Receipt,
    TurnRole,
    TurnState,
)
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)
from mendel_api.services import authoring_ai, authoring_decisions, decisions, session
from mendel_api.services import blueprint as bp
from mendel_api.services.session import Ctx, handles, records
from mendel_api.settings import settings
from mendel_api.stages import _rows
from mendel_api.stages.building import cards
from mendel_api.stages.building.amending import project, reviewed_of

log = logging.getLogger(__name__)

STEP = cards.STEP
PACING_PROPOSAL = ProposalKind.PACING
ENGINE = "engine"


class StepOutcome(NamedTuple):
    """What answering a step's card did, and what is waiting now — both from the one transaction
    that made them true, so a browser never has to re-read to learn what it just caused."""

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
    """`resolve`'s work: the blueprint resolved and stored (`stored`) with the walk reset and the
    draft projected afresh, or the goal found unbuildable (`cant_build`). Any other failure is
    raised.

    **The resolver runs inside the action's transaction**: it is computation, and a failure
    between resolving and storing leaves nothing half-written (spec §11.2). The session's
    `row_version` is compared when the blueprint is written, so a session that moved while the
    resolver ran is refused rather than overwritten. **The draft is replaced by the projection**
    of the new blueprint: a goal changed after hand edits is confirmed in the browser first
    (`hand_edits` on the session's view, spec §14.9).
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        if not authoring_decisions.confirmed(row.draft_id):
            raise ValueError(
                coded("MI0200", "this session has no confirmed goal to build from")
                + "\n  accept a goal first; a blueprint resolved from nothing is not a pipeline"
            )
        goal = authoring_decisions.goal(row)
        version = row.row_version

    try:
        blueprint, calls = bp.resolve(goal)
    except UnroutableError as unroutable:
        # **A fact about the goal, so it goes in the conversation** (#115).
        _rows.note(session_id, unbuildable(unroutable), code="MI0207")
        return "cant_build"
    except Exception as failure:
        # **The resolver's own failure, whatever its type**: `resolve` lands the session on
        # `failed`, then raises it.
        log.exception("resolving the blueprint for %s failed", session_id)
        raise ResolverFailed(failure) from failure
    if calls and client is not None:
        authoring_ai.record_calls(
            calls, client=client, registry=blueprint.registry, session_id=session_id
        )

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row.blueprint:
            decisions.cascade_reviews(row.draft_id,
                bp.Blueprint.model_validate(row.blueprint), blueprint)
        _rows.swap(
            db,
            session_id,
            version,
            blueprint=blueprint.model_dump(mode="json"),
            registry_digest=blueprint.registry,
        )
        project(db, db.get(PipelineAuthoringSession, session_id), blueprint)
        return "stored"


def start(ctx: Ctx, session_id: str, *, client=None) -> str | None:
    """Resolve the whole blueprint, store it, and walk to its first stop, by resuming the session
    at `resolve` (14.7.8.1). Returns the first card's id, or `None` (nothing to stop on, or a goal
    that could not be built: the session is then `failed`)."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        if session.rests_at(db, row) != "resolve":
            raise ValueError(
                coded("MI0200", f"there is nothing to build from {row.phase}")
                + "\n  a blueprint is resolved only once a goal is confirmed"
            )
    ctx.session_id = session_id
    ctx.resolver_client = client
    session.resume(session_id, ctx=ctx)
    return session.pending_id(session_id)


def _placement(row: PipelineAuthoringSession, draft: PipelineDraft | None, pending) -> dict:
    """Blueprint positions for the steps a person can see — the draft's and the one on offer.

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


def hand_edits(row: PipelineAuthoringSession, draft: PipelineDraft | None) -> str | None:
    """What a person changed by hand since the walk ended, as the receipt would say it, or
    `None`. A goal changed now replaces the draft with the new blueprint's, so the browser asks
    first (spec §14.9)."""
    if draft is None or row.phase != Phase.COMPLETE.value or not row.blueprint:
        return None
    blueprint = bp.Blueprint.model_validate(row.blueprint)
    projected, _ = drafted(
        blueprint, reviewed_of(row), authoring_decisions.goal(row).profile
    )
    return describe_edit(projected, DraftGraph.model_validate(draft.graph))


# ── answering a step's card ─────────────────────────────────────────────────────────────────


def registry_moved(row: PipelineAuthoringSession) -> bool:
    return bp.registry_digest([settings.registry_root]) != row.registry_digest


def re_offer(ctx: Ctx, proposal, row, db) -> StepOutcome:
    """**The registry moved since the card was offered** (`MI0206`): the card is marked stale,
    the blueprint is resolved again from the same goal, and the walk offers its next stop from
    it, with nothing applied. An option chosen against a registry that no longer supplies it is
    not a choice."""
    was = row.registry_digest
    proposal.state = ProposalState.STALE.value
    proposal.settled_at = _rows.now()
    try:
        fresh, _ = bp.resolve(authoring_decisions.goal(row))
    except UnroutableError as unroutable:
        # Final review of Run 2, I2: said by name, never a server error. Nothing is written —
        # the card waits, and the next answer meets the same sentence until the registry or
        # the goal changes.
        raise ValueError(
            unbuildable(unroutable)
            + "\n  the registry changed after this step was proposed, and the goal no longer builds"
        ) from None
    decisions.cascade_reviews(row.draft_id, bp.Blueprint.model_validate(row.blueprint), fresh)
    row.blueprint = fresh.model_dump(mode="json")
    row.registry_digest = fresh.registry
    project(db, row, fresh)
    revision = db.get(PipelineDraft, row.draft_id).revision
    db.flush()
    session.take(ctx, Command.CONTINUE.value)
    refusal = (
        coded("MI0206", "the registry changed after this step was proposed")
        + f"\n  it was resolved against {was}; it is {fresh.registry}"
        + "\n  nothing was applied — the blueprint was resolved again, and the walk goes on"
    )
    return StepOutcome(
        st.Settlement(ProposalState.STALE, False, refusal, False),
        revision,
        session.pending_id(ctx.session_id),
        session.current_phase(ctx.session_id),
    )


def outcome(ctx: Ctx) -> StepOutcome:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        revision = db.get(PipelineDraft, row.draft_id).revision
    return StepOutcome(
        st.Settlement(ProposalState.ACCEPTED, True, None, False),
        revision,
        session.pending_id(ctx.session_id),
        session.current_phase(ctx.session_id),
    )


def settle(ctx: Ctx, proposal_id: str, *, expected_revision: int, by: str) -> StepOutcome:
    """*Continue*: the step kept as the blueprint has it, marked reviewed, and the walk goes on.

    **One transaction from the check to the next card.** Refused when the card is gone, already
    answered (`MI0203`) or not a step's (`MI0205`); a stale revision is `MI0201`/`MI0202`; a moved
    registry re-offers (`MI0206`)."""
    from mendel_api.stages.building.amending import pending_step

    with session_scope() as db:
        proposal = pending_step(db, proposal_id)
        row = db.get(PipelineAuthoringSession, proposal.session_id)
        ctx.session_id = row.id
        draft = db.get(PipelineDraft, row.draft_id)
        if registry_moved(row):
            return re_offer(ctx, proposal, row, db)
        settled = st.settle(
            current=ProposalState(proposal.state),
            proposal_revision=proposal.draft_revision,
            draft_revision=draft.revision,
            expected_revision=expected_revision,
            decision=ProposalState.ACCEPTED,
        )
        if not settled.applies:
            if settled.state is not ProposalState(proposal.state):
                proposal.state = settled.state.value
                proposal.settled_at = _rows.now()
            return StepOutcome(settled, draft.revision, None, Phase(row.phase))
        session.check(row.id, Command.CONTINUE.value)
        decisions.record_review(row.draft_id, bp.Blueprint.model_validate(row.blueprint),
                                proposal.payload["node"], who=by)
        proposal.state = settled.state.value
        proposal.by = by
        proposal.chosen_option = bp.KEEP
        proposal.settled_at = _rows.now()
        project(db, row, bp.Blueprint.model_validate(row.blueprint))
    session.take(ctx, Command.CONTINUE.value)
    return outcome(ctx)


# ── a direct edit ───────────────────────────────────────────────────────────────────────────


def record_edit(session_id: str, graph: DraftGraph, *, by: str) -> int:
    """A direct edit to the session's draft, recorded in the transcript. Returns the new
    revision. Nothing is re-offered: no step's card is pending outside the walk.

    **Refused during the walk** (`MI0217`, issue 255): the draft is then the projection of the
    blueprint, with nowhere to keep a hand edit; a tool or a fact changes on a step's card.
    Editing opens once the walk is done. **The receipt is composed here, from the difference,
    never sent by the browser.**
    """
    from mendel_api.services import draft_mutations

    with session_scope() as db:
        row = draft_mutations.lock_session(db, session_id)
        if row.phase == Phase.BUILDING.value:
            raise ValueError(
                coded("MI0217", "editing opens when the walk is done")
                + "\n  change a step's tool, or tell it a fact, on the step's card"
            )
        draft = db.get(PipelineDraft, row.draft_id)
        before = DraftGraph.model_validate(draft.graph)
        summary = describe_edit(before, graph)
        if summary is None:
            return draft.revision

        draft_mutations.save_in(db, draft, graph=graph)

        seq = _rows.next_seq(db, session_id)
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq,
                role=TurnRole.ASSISTANT,
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
                at=_rows.now(),
            )
        )
        return draft.revision


def describe_edit(before: DraftGraph, after: DraftGraph) -> str | None:
    """One line saying what a direct edit did, or `None` when it did nothing.

    Named in the log's own vocabulary — step ids, upper-cased as the canvas draws them — and only
    what changed: steps, tools, settings and wiring, which is more than `BlueprintDiff` knows
    (it compares tools by step). A position move is not a change: `DraftGraph` has no coordinates.
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
    return settle(ctx, cmd.proposal_id, expected_revision=cmd.expected_revision, by=cmd.by)


@records(c.ChoosePacing)
def _choose_pacing(ctx: Ctx, cmd: c.ChoosePacing) -> None:
    """The pacing question answered: recorded in the walk's policy, and the walk goes on to the
    Dev fork. Refused when it is not the pacing question, or was already answered (issue 259)."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, cmd.proposal_id, with_for_update=True)
        if proposal is None or proposal.kind != PACING_PROPOSAL:
            raise ValueError(coded("MI0205", "that proposal is not the pacing question"))
        if proposal.state != ProposalState.PENDING.value:
            raise ValueError(coded("MI0203", "this proposal has already been settled"))
        _rows.read_offer(db, proposal)
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
        proposal.settled_at = _rows.now()
        row = db.get(PipelineAuthoringSession, proposal.session_id)
        row.pacing = Pacing(cmd.option).value
    session.take(ctx, Command.CHOOSE_PACING.value)


@records(c.RecordEdit)
def _edit(ctx: Ctx, cmd: c.RecordEdit) -> int:
    return record_edit(cmd.session_id, DraftGraph.model_validate(cmd.graph), by=cmd.by)


# ── the handlers ─────────────────────────────────────────────────────────────────────────


@handles("resolve")
def resolve(ctx: Ctx) -> str | None:
    """**A command arriving rests here; resuming resolves** (ruling 9 of 14.7.8.1b)."""
    if ctx.command is not None:
        return None
    try:
        return resolve_blueprint(ctx.session_id, client=ctx.resolver_client)
    except ResolverFailed as failed:  # the resolver itself: `failed`, then raised
        ctx.raised = failed.__cause__
        return "cant_build"


@handles("overview")
def overview(ctx: Ctx) -> None:
    """How many steps, and how many need the person, counted off the plan (spec §4.5)."""
    with session_scope() as db:
        _, plan = cards.plan_of_row(db.get(PipelineAuthoringSession, ctx.session_id))
    total, needing = len(plan.steps), len(plan.needing())
    text = f"{total} step{'s' * (total != 1)}; " + (
        "none need you." if needing == 0 else f"{needing} need{'s' * (needing == 1)} you."
    )
    _rows.engine_turn(
        ctx.session_id,
        lambda seq: [Narrative(id=f"overview-{seq}", text=text).model_dump(mode="json")],
    )
    return None


def _policy(row):
    return Policy(pacing=row.pacing or Pacing.TOGETHER, show_gaps=bool(row.show_gaps))


def _record(ctx: Ctx, **change) -> None:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        policy = _policy(row).model_copy(update=change)
        row.pacing = policy.pacing.value
        row.show_gaps = policy.show_gaps
    return None


@handles("together")
def together(ctx: Ctx) -> None:
    return _record(ctx, pacing=Pacing.TOGETHER)


@handles("quiet")
def quiet(ctx: Ctx) -> None:
    return _record(ctx, pacing=Pacing.STOP_WHERE_NEEDED)


@handles("show_gaps")
def show_gaps(ctx: Ctx) -> None:
    return _record(ctx, show_gaps=True)


@handles("hide_gaps")
def hide_gaps(ctx: Ctx) -> None:
    return _record(ctx, show_gaps=False)


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
    """Place every step that does not stop, **in this one entry**, whatever the pipeline's length
    (issue 258), then project the draft once; leave on the first stop, or at the end.

    **The card is offered after the projection** (issue 263): it records the draft's revision and
    wires against its graph, so both must already hold the steps placed quietly before it."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        blueprint, plan = cards.plan_of_row(row)
        policy = _policy(row)
        reviewed = reviewed_of(row)
        by_node = {planned.node: planned for planned in plan.steps}
        stop = None
        while (node := next_step(blueprint, reviewed)) is not None:
            stop = stops(by_node[node], policy)
            if stop is not None:
                break
            from mendel_authoring.decisions import ActorKind
            from mendel_authoring.reviews import review

            decisions.record_review(row.draft_id, blueprint, node, who=ENGINE,
                                    actor_kind=ActorKind.RESOLVER)
            reviewed.append(review(blueprint, node, ENGINE, actor_kind=ActorKind.RESOLVER))
        project(db, row, blueprint)
        if stop is None:
            return "none_left"
        cards.offer(db, row, blueprint, plan, node, stop)
        return "stops"


@handles("wrap")
def wrap(ctx: Ctx) -> None:
    """The wrap-up (spec §4.4), as a `Receipt`: what you'll get, what you need, who decided —
    read from the final blueprint, which carries a person's tools as theirs (issue 256) — and any
    tool you chose that applies nowhere."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        blueprint, plan = cards.plan_of_row(row)
        revision = db.get(PipelineDraft, row.draft_id).revision
        goal = authoring_decisions.goal(row)
    used = {
        (blueprint.sites.get(s.id), s.module.contract_id) for s in blueprint.pipeline.steps
    }
    inert = [p for p in goal.constraints.producers if (p.site, p.contract) not in used]
    w = plan.wrap_up
    needed = [i.id for i in w.inputs] + w.unset
    lines = [
        "You'll get: " + (", ".join(g.id for g in w.gets) or "nothing named") + ".",
        "To run it you need: " + (", ".join(needed) or "nothing more") + ".",
        "Decided: "
        + ", ".join(f"{d.count} at tier {d.tier} by {d.source}" for d in w.decided)
        + ".",
    ]
    if inert:
        lines.append(
            "Tools you chose that no longer apply: "
            + ", ".join(f"{p.contract} for {p.site.type_id}" for p in inert)
            + "."
        )
    _rows.engine_turn(
        ctx.session_id,
        lambda seq: [
            Receipt(
                id=f"wrap-{seq}", summary=" ".join(lines), revision=revision, by="resolver"
            ).model_dump(mode="json")
        ],
    )
    return None
