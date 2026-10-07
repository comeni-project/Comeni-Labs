"""A change on a step's card, into the goal; the blueprint resolved again; the draft projected
from it (spec §14.3–§14.5 of the consultant build).

**The goal holds every decision.** A tool chosen on a card is a pin in the goal, a fact told is a
measurement in its profile, and the blueprint is `resolve(goal)`; the draft is the blueprint's
reviewed steps. Nothing is appended, so a change that drags steps with it — HISAT2's index in,
STAR's out — leaves nothing behind (issues 253, 254).
"""

from comeni_core.declared.measurement import MeasuredEntry
from comeni_core.diagnostics import coded
from comeni_core.plan.tiers import ValueSource
from mendel_authoring import commands as c
from mendel_authoring.amend import Amendment, ChooseTool, SetFact
from mendel_authoring.diff import diff_of
from mendel_authoring.draft import Reviewed, drafted, kept
from mendel_authoring.types import Command
from mendel_resolver.goal import Goal
from mendel_resolver.router import UnroutableError

from mendel_api.authoring.types import ProposalState, Receipt
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft
from mendel_api.services import blueprint as bp
from mendel_api.services import registry, session
from mendel_api.services.session import Ctx, handles, records
from mendel_api.stages import _rows
from mendel_api.stages.building.cards import FACT, STEP


def reviewed_of(row) -> list[Reviewed]:
    return [Reviewed.model_validate(r) for r in row.reviewed or []]


def project(db, row, blueprint: bp.Blueprint) -> None:
    """The draft from the blueprint and the reviewed steps, and the goal with it (issue 254):
    the kept artifact carries every fact and pin it was built from. The revision moves only
    when something changed."""
    goal = Goal.model_validate(row.goal)
    draft = db.get(PipelineDraft, row.draft_id)
    graph, provenance = drafted(blueprint, reviewed_of(row), goal.profile)
    dumped = graph.model_dump(mode="json")
    if dumped != draft.graph or draft.goal != row.goal:
        draft.graph = dumped
        draft.provenance = provenance.model_dump(mode="json")
        draft.goal = row.goal
        draft.revision = draft.revision + 1
        draft.updated_at = _rows.now()


def pending_step(db, proposal_id: str) -> PipelineAuthoringProposal:
    """The step card a command answers: refused if it is gone, already answered (`MI0203` —
    a double click or a second tab), or not a step's card."""
    proposal = db.get(PipelineAuthoringProposal, proposal_id)
    if proposal is None:
        raise KeyError(proposal_id)
    if proposal.state != ProposalState.PENDING.value:
        raise ValueError(coded("MI0203", "this proposal has already been settled"))
    if proposal.kind != STEP:
        raise ValueError(coded("MI0205", "that proposal is not a step's card"))
    return proposal


def _offered(proposal, option: str, value, goal: Goal) -> Amendment:
    """The amendment the card offered under `option`, **by id**: nothing outside the card's own
    list can be applied, whoever sends it — a person now, a model in part 4."""
    options: dict[str, str] = proposal.payload["options"]
    if option not in options or option == bp.KEEP:
        raise ValueError(
            coded("MI0205", "that option was never offered as a change to this step")
            + f"\n  offered: {', '.join(sorted(o for o in options if o != bp.KEEP))}"
        )
    if option.startswith(FACT):
        return _fact(options[option], value, goal)
    return ChooseTool.model_validate(proposal.payload["amendments"][option])


def _fact(measurement: str, value, goal: Goal) -> SetFact:
    """A fact told on the card, checked against its declaration (`MI0208`) and folded into the
    goal's profile through `profile_of`, the one constructor of a profile (invariant 15)."""
    stack = registry.stack()
    try:
        stack.measurements.check(measurement, value)
    except (ValueError, KeyError, TypeError) as refused:
        raise ValueError(
            coded("MI0208", f"{value!r} does not fit {measurement}") + f"\n  {refused}"
        ) from None
    profile = stack.measurements.profile_of(
        [
            MeasuredEntry(m.measurement, m.value, m.source, m.by, tuple(m.pieces), m.evidence)
            for m in goal.profile.measurements
            if m.measurement != measurement
        ]
        + [MeasuredEntry(measurement, value, ValueSource.GOAL)]
    )
    return SetFact(measurement=measurement, value=value, profile=profile)


def carried_by_pin(
    before: bp.Blueprint, fresh: bp.Blueprint, reviewed: list[Reviewed], goal: Goal
) -> list[Reviewed]:
    """A reviewed step a person's tool replaced keeps its review, under the new step's id: the
    person chose that tool at that site on its card (STAR's card, now HISAT2's step). Only where
    the goal pins the site — a step a fact or a registry change replaced is shown again."""
    now_at = {site: node for node, site in fresh.sites.items()}
    pinned = {pin.site for pin in goal.constraints.producers}
    carried = []
    for entry in reviewed:
        site = before.sites.get(entry.node)
        if entry.node not in fresh.order and site in pinned and site in now_at:
            entry = Reviewed(node=now_at[site], by=entry.by)
        carried.append(entry)
    return carried


@records(c.Amend)
def amend(ctx: Ctx, cmd: c.Amend):
    """One of the card's offered changes (spec §14.5): checked, applied to the goal, and the
    step it decided marked reviewed; then `amend` resolves again and projects the draft."""
    from mendel_api.stages.building import walk

    with session_scope() as db:
        proposal = pending_step(db, cmd.proposal_id)
        row = db.get(PipelineAuthoringSession, proposal.session_id)
        ctx.session_id = row.id
        if walk.registry_moved(row):
            return walk.re_offer(ctx, proposal, row, db)
        amendment = _offered(proposal, cmd.option, cmd.value, Goal.model_validate(row.goal))
        session.check(row.id, Command.AMEND.value)
        row.goal = amendment.apply(Goal.model_validate(row.goal)).model_dump(mode="json")
        if isinstance(amendment, ChooseTool):
            # The person just decided this step; the tool it now holds is theirs, reviewed.
            row.reviewed = [
                *(row.reviewed or []),
                Reviewed(node=proposal.payload["node"], by=cmd.by).model_dump(mode="json"),
            ]
        proposal.state = ProposalState.ACCEPTED.value
        proposal.by = cmd.by
        proposal.chosen_option = cmd.option
        proposal.settled_at = _rows.now()
    session.take(ctx, Command.AMEND.value)
    return walk.outcome(ctx)


@handles("amend")
def amend_node(ctx: Ctx) -> str:
    """Resolve the amended goal; store the blueprint, keep the reviewed steps it still has,
    project the draft, and say what the change did. A goal that cannot be built fails as
    `resolve` does (issue 259)."""
    from mendel_api.stages.building import walk

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        goal = Goal.model_validate(row.goal)
        before = bp.Blueprint.model_validate(row.blueprint)
    try:
        fresh, _ = bp.resolve(goal)
    except UnroutableError as unroutable:
        _rows.note(ctx.session_id, walk.unbuildable(unroutable), code="MI0207")
        return "cant_build"
    except Exception as failure:  # the resolver's own failure: `failed`, then raised
        ctx.raised = failure
        return "cant_build"
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        row.blueprint = fresh.model_dump(mode="json")
        row.registry_digest = fresh.registry
        carried = carried_by_pin(before, fresh, reviewed_of(row), goal)
        row.reviewed = [r.model_dump(mode="json") for r in kept(fresh, carried)]
        project(db, row, fresh)
        revision = db.get(PipelineDraft, row.draft_id).revision
    said = diff_of(before, fresh).sentence()
    _rows.engine_turn(
        ctx.session_id,
        lambda seq: [
            Receipt(
                id=f"amend-{seq}", summary=f"Your change {said}.", revision=revision, by="person"
            ).model_dump(mode="json")
        ],
    )
    return "amended"
