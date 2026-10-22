"""A step's card: what a person reads when the walk stops, and the options it offers (spec §14.4).

The options are fixed when the card is offered: *keep* (the step as the blueprint has it), each
buildable alternative tool as the whole pipeline it gives (`alt_N`), and *tell me* for each fact
its rule lacked (`fact_<measurement>`). The amendment each option stands for is stored with the
card, so answering it applies exactly what the person read — never a recomputed list.
"""

from comeni_core.goal.asked import Goal
from comeni_core.plan.draft import DraftGraph
from comeni_core.spell.routes import OMITTABLE
from mendel_authoring.alternatives import alternatives_of
from mendel_authoring.blueprint import edges_touching
from mendel_authoring.gaps import GapKind
from mendel_authoring.needs import NeedKind
from mendel_authoring.pacing import Stop
from mendel_authoring.plan import BuildPlan, PlannedStep, plan_of
from mendel_authoring.progress import progress_of
from mendel_authoring.reviews import Reviewed
from mendel_resolver.router import UnroutableError

from mendel_api.authoring import envelopes
from mendel_api.authoring.canvas import AlternativePreview
from mendel_api.authoring.types import Option, ProposalState, StepProposal
from mendel_api.models import PipelineAuthoringProposal, PipelineDraft
from mendel_api.services import authoring_canvas, authoring_decisions, declared, registry
from mendel_api.services import blueprint as bp
from mendel_api.stages import _rows

STEP = _rows.STEP
FACT = "fact_"
"""An option id naming a fact a rule lacked: `fact_read_length`. Option ids are bare
identifiers, so the measurement is joined with an underscore, not a colon."""


def plan_of_row(row) -> tuple[bp.Blueprint, BuildPlan]:
    blueprint = bp.Blueprint.model_validate(row.blueprint)
    return blueprint, plan_of(blueprint, declared.of(registry.stack()))


def _resolved(goal: Goal) -> bp.Blueprint:
    return bp.resolve(goal)[0]


def optional_unset(contract, gaps) -> list[str]:
    """The settings with no listed values that the card may say *stay unset*: those whose route
    leaves the tool its own behaviour (`OMITTABLE`, #384). A required one is asked once the step
    is added, so the card must not tell the person it needs nothing from them."""
    optional = {param.name for param in contract.params if param.via in OMITTABLE}
    return [g.subject for g in gaps if g.kind is GapKind.NO_DOMAIN and g.subject in optional]


def step_payload(
    blueprint: bp.Blueprint,
    planned: PlannedStep,
    goal: Goal,
    present: frozenset[str],
    stop: Stop,
    *,
    found=None,
) -> dict:
    """The stored payload offering one step. `edges` are the wires keeping it adds between it and
    the steps already in the draft, so the browser can draw it at once."""
    step = blueprint.step(planned.node)
    found = found if found is not None else alternatives_of(
        blueprint, goal, planned.node, bp.candidates(blueprint, planned.node), _resolved,
        (UnroutableError,),
    )
    buildable = [a for a in found if a.refused is None]
    facts = {f"{FACT}{m}": m for m in planned.need.facts}
    contract = registry.stack().registry.get(planned.contract)
    block = StepProposal(
        id=f"step-{planned.node}",
        node=planned.node,
        contract=planned.contract,
        consumes=sorted({port.type_id for port in contract.consumes if port.type_id}),
        produces=sorted({output.type_id for output in contract.produces}),
        reason=step.why.reason,
        # A step waiting on a fact nobody supplied is tier 4, whatever its tool's tier (#341).
        tier=4 if planned.need.kind is NeedKind.FACT else int(step.why.tier),
        alternatives=[
            Option(
                id=a.id,
                label=a.contract,
                note=a.diff.sentence() if a.diff else f"can't be built here: {a.refused}"[:500],
            )
            for a in found
        ],
        brief=planned.brief,
        need=planned.need,
        gaps=planned.gaps,
        unresolved_settings=optional_unset(contract, planned.gaps),
        stop=stop.value,
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
        "options": {
            bp.KEEP: planned.contract,
            **{a.id: a.contract for a in buildable},
            **facts,
        },
        "amendments": {a.id: a.amendment.model_dump(mode="json") for a in buildable},
        "edges": wires,
    }


def offer(db, row, blueprint: bp.Blueprint, plan: BuildPlan, node: str, stop: Stop, *,
          retained: list[Reviewed], previously_reviewed: frozenset[str]) -> str:
    """Store one step's card as `pending`, against the draft as it stands now, stamped with
    where the step stood in the plan when it was offered."""
    draft = db.get(PipelineDraft, row.draft_id)
    present = frozenset(n.id for n in DraftGraph.model_validate(draft.graph).nodes)
    planned = next(p for p in plan.steps if p.node == node)
    proposal_id = _rows.new_id()
    goal = authoring_decisions.goal(row)
    found = alternatives_of(blueprint, goal, node, bp.candidates(blueprint, node),
                            _resolved, (UnroutableError,))
    stood = progress_of(list(blueprint.order), frozenset(r.node for r in retained),
                        previously_reviewed, node).active
    payload = envelopes.prepare(
        {**step_payload(blueprint, planned, goal, present, stop, found=found),
         "progress": stood.model_dump(mode="json")},
        kind=STEP, draft=draft, session=row)
    context = envelopes.OfferContext.model_validate(payload["context"])
    previews = {
        alt.id: AlternativePreview(
            option_id=alt.id, contract=alt.contract, observed_context=context,
            frame=authoring_canvas.preview_frames(alt.blueprint, context, proposal_id,
                                                 registry.stack()),
        ).model_dump(mode="json") for alt in found if alt.blueprint is not None
    }
    payload["preview_options"] = list(previews)
    db.add(
        PipelineAuthoringProposal(
            id=proposal_id,
            session_id=row.id,
            turn_id=None,
            kind=STEP,
            payload=payload,
            preview_views=previews,
            state=ProposalState.PENDING.value,
            chosen_option=None,
            by=None,
            draft_revision=draft.revision,
            created_at=_rows.now(),
            settled_at=None,
        )
    )
    db.flush()
    return proposal_id
