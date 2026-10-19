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
from mendel_authoring import payloads as p
from mendel_authoring.amend import Amendment, ChooseTool, SetFact
from mendel_authoring.diff import diff_of
from mendel_authoring.draft import Reviewed, drafted
from mendel_authoring.types import Command
from mendel_resolver.goal import Goal
from mendel_resolver.router import UnroutableError

from mendel_api.authoring.types import ProposalState, Receipt
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft
from mendel_api.services import authoring_decisions, decisions, draft_mutations, registry, session
from mendel_api.services import blueprint as bp
from mendel_api.services.session import Ctx, handles, records
from mendel_api.stages import _rows
from mendel_api.stages.building.cards import FACT, STEP


def reviewed_of(row) -> list[Reviewed]:
    return decisions.reviews(row.draft_id)


def project(db, row, blueprint: bp.Blueprint) -> None:
    """The draft from the blueprint and the reviewed steps, and the goal with it (issue 254):
    the kept artifact carries every fact and pin it was built from. The revision moves only
    when something changed."""
    goal = authoring_decisions.goal(row)
    draft = db.get(PipelineDraft, row.draft_id)
    graph, provenance = drafted(blueprint, reviewed_of(row), goal.profile)
    draft_mutations.project(db, draft, graph,
                            provenance=provenance.model_dump(mode="json"))


def pending_step(db, proposal_id: str) -> PipelineAuthoringProposal:
    """The step card a command answers: refused if it is gone, already answered (`MI0203` —
    a double click or a second tab), or not a step's card."""
    # **Locked** (final review of Run 2, I3): two answers that really overlap — a double click,
    # two tabs — are serialised here, so the second reads the card answered and is refused.
    identity = db.get(PipelineAuthoringProposal, proposal_id)
    if identity is None:
        raise KeyError(proposal_id)
    draft_mutations.lock_session(db, identity.session_id)
    proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True,
                      populate_existing=True)
    if proposal is None:
        raise KeyError(proposal_id)
    if proposal.state != ProposalState.PENDING.value:
        raise ValueError(coded("MI0203", "this proposal has already been settled"))
    if proposal.kind != STEP:
        raise ValueError(coded("MI0205", "that proposal is not a step's card"))
    _rows.read_offer(db, proposal)
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
        + [MeasuredEntry(measurement, value, ValueSource.SAID)]
    )
    return SetFact(measurement=measurement, value=value, profile=profile)


def unbuildable_change(unroutable: UnroutableError) -> str:
    """MI0207 for a speculative tool choice that cannot be built, before it is applied."""
    missing = ""
    if unroutable.missing is not None:
        type_id, states = unroutable.missing
        missing = f": it would need {type_id}" + (
            f"[{', '.join(sorted(states))}]" if states else ""
        ) + ", and nothing can make it from what you have"
    return coded("MI0207", "that change cannot be built" + missing) + (
        "\n  nothing was changed — keep the step, or choose another answer"
    )


@records(c.Amend)
def amend(ctx: Ctx, cmd: c.Amend):
    """A told fact takes the truthful correction path; a speculative tool swap resolves first.

    Tool choices that cannot be built leave the pending card and selections unchanged. Facts
    stay selected even when resolution is blocked, and the diagram explains how to recover.
    """
    from mendel_api.stages.building import walk

    with session_scope() as db:
        proposal = pending_step(db, cmd.proposal_id)
        row = db.get(PipelineAuthoringSession, proposal.session_id)
        ctx.session_id = row.id
        draft = db.get(PipelineDraft, row.draft_id)
        if ((cmd.expected_draft_revision is not None
                and cmd.expected_draft_revision != draft.revision)
                or (cmd.expected_decision_revision is not None
                    and cmd.expected_decision_revision != draft.decision_revision)
                or (cmd.expected_session_version is not None
                    and cmd.expected_session_version != row.row_version)):
            raise ValueError(coded("MI0201", "this amendment's context changed; reload the card"))
        if walk.registry_moved(row):
            return walk.re_offer(ctx, proposal, row, db)
        amendment = _offered(proposal, cmd.option, cmd.value, authoring_decisions.goal(row))
        if isinstance(amendment, SetFact):
            from mendel_api.stages import correcting

            draft = db.get(PipelineDraft, row.draft_id)
            correction = c.CorrectFact(row.id, amendment.measurement, amendment.value, cmd.by,
                cmd.expected_decision_revision if cmd.expected_decision_revision is not None
                else draft.decision_revision,
                cmd.expected_draft_revision if cmd.expected_draft_revision is not None
                else draft.revision,
                cmd.expected_session_version if cmd.expected_session_version is not None
                else row.row_version)
            correcting.correct(ctx, correction)
            return walk.outcome(ctx)
        session.check(row.id, Command.AMEND.value)
        goal = amendment.apply(authoring_decisions.goal(row))
        try:
            fresh, _ = bp.resolve(goal)
        except UnroutableError as unroutable:
            raise ValueError(unbuildable_change(unroutable)) from None
        before = bp.Blueprint.model_validate(row.blueprint)
        decisions.import_goal(row.draft_id, goal, who=cmd.by)
        decisions.cascade_reviews(row.draft_id, before, fresh)
        if isinstance(amendment, ChooseTool):
            node = next(n for n, site in fresh.sites.items() if site == amendment.pin.site)
            decisions.record_review(row.draft_id, fresh, node, who=cmd.by, proposal_id=proposal.id)
        row.blueprint = fresh.model_dump(mode="json")
        row.registry_digest = fresh.registry
        project(db, row, fresh)
        proposal.state = ProposalState.ACCEPTED.value
        proposal.by = cmd.by
        proposal.actor_kind = "person"
        proposal.chosen_option = cmd.option
        proposal.settled_at = _rows.now()
        said = diff_of(before, fresh).sentence()
    session.take(ctx, Command.AMEND.value, p.Amended(said=said))
    return walk.outcome(ctx)


@handles("amend")
def amend_node(ctx: Ctx) -> str:
    """The change is in: say what it did, as a receipt, and walk on."""
    if not isinstance(ctx.payload, p.Amended):
        raise TypeError("amend requires Amended")
    said = ctx.payload.said
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        revision = db.get(PipelineDraft, row.draft_id).revision
    _rows.engine_turn(
        ctx.session_id,
        lambda seq: [
            Receipt(
                id=f"amend-{seq}", summary=f"Your change {said}.", revision=revision, by="person"
            ).model_dump(mode="json")
        ],
    )
    return "amended"
