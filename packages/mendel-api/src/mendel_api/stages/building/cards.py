"""A step's card: what a person reads when the walk stops, and the options it offers (spec §14.4).

The options are fixed when the card is offered: *keep* (the step as the blueprint has it), each
buildable alternative tool as the whole pipeline it gives (`alt_N`), and *tell me* for each fact
its rule lacked (`fact_<measurement>`). The amendment each option stands for is stored with the
card, so answering it applies exactly what the person read — never a recomputed list.
"""

from comeni_core.goal.asked import Goal
from comeni_core.plan.draft import DraftGraph
from mendel_authoring.alternatives import alternatives_of
from mendel_authoring.blueprint import edges_touching
from mendel_authoring.pacing import Stop
from mendel_authoring.plan import BuildPlan, PlannedStep, plan_of
from mendel_resolver.router import UnroutableError

from mendel_api.authoring import envelopes
from mendel_api.authoring.types import Option, ProposalState, StepProposal
from mendel_api.models import PipelineAuthoringProposal, PipelineDraft
from mendel_api.services import blueprint as bp
from mendel_api.services import declared, registry
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


def step_payload(
    blueprint: bp.Blueprint,
    planned: PlannedStep,
    goal: Goal,
    present: frozenset[str],
    stop: Stop,
) -> dict:
    """The stored payload offering one step. `edges` are the wires keeping it adds between it and
    the steps already in the draft, so the browser can draw it at once."""
    step = blueprint.step(planned.node)
    found = alternatives_of(
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
        tier=int(step.why.tier),
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


def offer(db, row, blueprint: bp.Blueprint, plan: BuildPlan, node: str, stop: Stop) -> str:
    """Store one step's card as `pending`, against the draft as it stands now."""
    draft = db.get(PipelineDraft, row.draft_id)
    present = frozenset(n.id for n in DraftGraph.model_validate(draft.graph).nodes)
    planned = next(p for p in plan.steps if p.node == node)
    proposal_id = _rows.new_id()
    db.add(
        PipelineAuthoringProposal(
            id=proposal_id,
            session_id=row.id,
            turn_id=None,
            kind=STEP,
            payload=envelopes.prepare(
                step_payload(blueprint, planned, Goal.model_validate(row.goal), present, stop),
                kind=STEP, draft=draft, session=row),
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
