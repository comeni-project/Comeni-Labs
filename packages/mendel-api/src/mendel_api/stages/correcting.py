"""⑤ Truthful changes select facts first; resolution and dependent reviews follow the diagram."""

from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Site
from mendel_authoring import commands as c
from mendel_authoring import payloads as p
from mendel_authoring.decisions import FactOrigin, InputDecision
from mendel_authoring.diff import diff_of
from mendel_authoring.types import Command, Phase, ProposalState
from mendel_resolver.router import UnroutableError, UnroutablePinError
from sqlalchemy import select

from mendel_api.authoring.types import Receipt
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession, PipelineDraft
from mendel_api.services import authoring_decisions, decisions, draft_mutations, registry, session
from mendel_api.services import blueprint as bp
from mendel_api.services.session import Ctx, handles, records
from mendel_api.stages import _rows
from mendel_api.stages.building.amending import project

_CONTINUATION = {
    Phase.GATHERING: "gather",
    Phase.GOAL_REVIEW: "goal",
    Phase.BUILDING: "build",
    Phase.COMPLETE: "complete",
    Phase.STOPPED: "stopped",
}


def checked(db, cmd):
    row = draft_mutations.lock_session(db, cmd.session_id)
    draft = db.get(PipelineDraft, row.draft_id)
    if row.retired:
        raise ValueError(coded("MI0217", "this archived session is read-only"))
    if (
        draft.decision_revision != cmd.expected_decision_revision
        or draft.revision != cmd.expected_draft_revision
        or row.row_version != cmd.expected_session_version
    ):
        raise ValueError(
            coded("MI0201", "the selected facts or draft changed; reload before correcting")
        )
    return row, draft


def stale_proposals(db, sid):
    for proposal in db.scalars(
        select(PipelineAuthoringProposal).where(
            PipelineAuthoringProposal.session_id == sid,
            PipelineAuthoringProposal.state == ProposalState.PENDING.value,
        )
    ):
        proposal.state = ProposalState.STALE.value
        proposal.settled_at = _rows.now()
    db.flush()


def result(sid):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        return {
            "session_id": sid,
            "draft_id": draft.id,
            "phase": row.phase,
            "revision": draft.revision,
            "decision_revision": draft.decision_revision,
            "next_proposal": session.pending_id(sid),
            "projection_current": draft.projection_current,
        }


def _begin(ctx, cmd, arrow, *, subject, kind, states=()):
    with session_scope() as db:
        row, draft = checked(db, cmd)
        session.check(row.id, arrow.value)
        if draft.ownership == "manual":
            raise ValueError(
                coded("MI0217", "correct this manually edited pipeline in a new draft")
            )
        ctx.session_id = row.id
        payload = p.Correction(
            subject=subject,
            value=getattr(cmd, "value", None),
            who=cmd.by,
            kind=kind,
            states=list(states),
            continuation=_CONTINUATION[Phase(row.phase)],
            before=bp.Blueprint.model_validate(row.blueprint) if row.blueprint else None,
        )
        session.take(ctx, arrow.value, payload)
    return result(ctx.session_id)


@records(c.CorrectFact)
def correct(ctx: Ctx, cmd: c.CorrectFact):
    return _begin(ctx, cmd, Command.CORRECT_FACT, subject=cmd.subject, kind=cmd.kind)


@records(c.ReleaseProducer)
def release(ctx: Ctx, cmd: c.ReleaseProducer):
    return _begin(
        ctx, cmd, Command.RELEASE_PRODUCER, subject=cmd.type_id, kind="producer", states=cmd.states
    )


def _payload(ctx):
    if not isinstance(ctx.payload, p.Correction):
        raise TypeError("correction requires its typed values and continuation")
    return ctx.payload


def receipt(ctx, suffix=""):
    change = _payload(ctx)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        value = "unknown" if change.value is None else str(change.value)
        said = (
            f"released the tool choice for {change.subject}"
            if change.kind == "producer"
            else f"{change.subject} is {value}"
        )
        _rows.engine_turn(
            row.id,
            lambda seq: [
                Receipt(
                    id=f"correction-{seq}",
                    summary=f"Your correction: {said}. {suffix}".strip(),
                    revision=draft.revision,
                    by="person",
                ).model_dump(mode="json")
            ],
        )


@handles("correct_fact")
def select_correction(ctx: Ctx):
    change = _payload(ctx)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        previous = draft.decision_revision
        if change.kind == "measurement":
            decisions.set_fact(draft.id, change.subject, change.value, who=change.who)
        elif change.kind == "input":
            if change.value is not None and type(change.value) is not bool:
                raise ValueError(coded("MI0208", "an input answer must say whether you have it"))
            current = decisions.read(draft.id)
            old = next(
                (
                    i
                    for i in current.inputs
                    if i.key == change.subject or i.type_id == change.subject
                ),
                None,
            )
            type_id = old.type_id if old else change.subject
            if type_id not in registry.stack().vocabulary.types:
                raise ValueError(coded("MI0208", f"undeclared input type {type_id}"))
            selected = InputDecision(
                key=old.key if old else type_id,
                type_id=type_id,
                name=old.name if old else None,
                states=old.states if old else [],
                present=change.value is True,
                origin=FactOrigin.OPEN if change.value is None else FactOrigin.PERSON_SAID,
            )
            decisions.set_input(draft.id, selected, who=change.who)
        elif change.kind == "producer":
            decisions.release_producer(
                draft.id,
                Site(type_id=change.subject, states=frozenset(change.states)),
                who=change.who,
            )
        elif change.kind == "retain":
            decisions.retain_fact(draft.id, change.subject, who=change.who)
        elif change.kind == "observation":
            decisions.select_observation(
                draft.id, change.subject, change.observation_id, who=change.who
            )
        stale_proposals(db, row.id)
        row.row_version = session.changed_version(db, row.id, row.row_version)
        row.updated_at = _rows.now()
        if draft.decision_revision != previous:
            draft_mutations.touch(db, draft)
        if (
            change.kind == "input"
            and change.value is False
            and not authoring_decisions.confirmed(draft.id)
        ):
            receipt(ctx, "The pipeline is outdated until this required input is available.")
            return "input_missing"
        if not authoring_decisions.confirmed(draft.id):
            receipt(ctx, "The engine will check what the goal still needs.")
            return "gather_again"
        if draft.decision_revision == previous and draft.projection_current:
            receipt(ctx, "Your selected answer stays.")
            return "retained_" + (
                "gather" if change.continuation == "stopped" else change.continuation
            )
        return "selected"


@handles("resolve_correction")
def resolve_correction(ctx: Ctx):
    change = _payload(ctx)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        try:
            goal = authoring_decisions.goal(row)
            fresh, _ = bp.resolve(goal)
            for pin in goal.constraints.producers:
                was_active = change.before is not None and any(
                    change.before.sites.get(step.id) == pin.site
                    and step.module.contract_id == pin.contract
                    for step in change.before.pipeline.steps
                )
                remains_active = any(
                    fresh.sites.get(step.id) == pin.site and step.module.contract_id == pin.contract
                    for step in fresh.pipeline.steps
                )
                if was_active and not remains_active:
                    raise UnroutablePinError(f"your choice {pin.contract} is no longer reachable")
        except UnroutableError as missing:
            subject = missing.missing[0] if missing.missing else None
            ctx.payload = change.model_copy(
                update={
                    "missing": subject,
                    "missing_states": sorted(missing.missing[1]) if missing.missing else [],
                    "pin_blocked": isinstance(missing, UnroutablePinError),
                }
            )
            _rows.say_engine(
                row.id,
                "Your correction is saved. The previous pipeline is outdated. "
                + (
                    f"This analysis still needs {subject}."
                    if subject
                    else "The corrected goal cannot be reached; "
                    "release a tool choice or correct the inputs."
                ),
            )
            return "blocked"
        ctx.payload = change.model_copy(update={"after": fresh})
        return "resolved"


@handles("cascade_reviews")
def cascade_reviews(ctx: Ctx):
    change = _payload(ctx)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        fresh = change.after
        if change.before is not None:
            decisions.cascade_reviews(row.draft_id, change.before, fresh)
        row.blueprint = fresh.model_dump(mode="json")
        row.registry_digest = fresh.registry
        project(db, row, fresh)
        suffix = (
            diff_of(change.before, fresh).sentence() if change.before else "The build is ready."
        )
        receipt(ctx, suffix + " Affected steps will be reviewed again.")
    return "review_again"


@handles("correction_blocked")
def blocked(ctx: Ctx):
    change = _payload(ctx)
    receipt(ctx, "The correction stays; the previous pipeline is outdated.")
    essential = (
        change.pin_blocked
        or change.missing is None
        or (change.kind == "input" and change.value is False)
    )
    if essential:
        return "essential_missing"
    from mendel_api.authoring.types import FactKind
    from mendel_api.services import gaps
    from mendel_api.stages import gathering

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        gap = gaps.Gap(
            FactKind.INPUT,
            change.missing,
            "the corrected pipeline needs this input and its required states",
        )
        stack = registry.stack()
        options = gathering._gap_options(gap, stack, authoring_decisions.facts(row.draft_id))
        question = gathering._gap_question(gap, options, stack, row.row_version)
        _rows.propose(
            row.id,
            kind=_rows.GAP,
            payload={
                "subject": gap.subject,
                "kind": gap.kind.value,
                "why": gap.why,
                "states": change.missing_states,
                "options": options,
                "block": question.model_dump(mode="json"),
            },
        )
    return "gather_missing"
