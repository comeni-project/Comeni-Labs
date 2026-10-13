"""⑤ Truthful changes select facts first; resolution and dependent reviews follow the diagram."""

import hashlib
import json

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
        from mendel_api.stages import samples

        pending = _rows.pending_of(db, row.id)
        reading = samples._reading(pending.payload.get("block", {})) if pending else None
        if reading is not None and reading.get("state") == "pending":
            raise ValueError(
                coded("MI0215", "a sample is still being read; retry when it finishes")
            )
        if draft.ownership == "manual":
            arrow = Command.FORK_CORRECTION
        session.check(row.id, arrow.value)
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
        if arrow is Command.FORK_CORRECTION:
            existing = existing_fork(db, row, draft, payload)
            if existing:
                return result(existing)
        session.take(ctx, arrow.value, payload)
    return result(ctx.session_id)


@records(c.CorrectFact)
def correct(ctx: Ctx, cmd: c.CorrectFact):
    return _begin(ctx, cmd, Command.CORRECT_FACT, subject=cmd.subject, kind=cmd.kind)


@records(c.ForkCorrection)
def fork(ctx: Ctx, cmd: c.ForkCorrection):
    return _begin(ctx, cmd, Command.FORK_CORRECTION, subject=cmd.subject, kind=cmd.kind)


def fork_key(row, draft, payload):
    values = [
        row.id,
        row.row_version,
        draft.revision,
        draft.decision_revision,
        payload.model_dump(mode="json", exclude={"before", "after"}),
    ]
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def existing_fork(db, row, draft, payload):
    return db.scalar(
        select(PipelineAuthoringSession.id)
        .join(PipelineDraft, PipelineDraft.id == PipelineAuthoringSession.draft_id)
        .where(
            PipelineDraft.forked_from == draft.id,
            PipelineDraft.fork_key == fork_key(row, draft, payload),
        )
    )


@handles("fork_correction")
def fork_correction(ctx: Ctx):
    from comeni_core.plan.draft import DraftGraph

    from mendel_api.stages import describe

    change = _payload(ctx)
    with session_scope() as db:
        parent_session = db.get(PipelineAuthoringSession, ctx.session_id)
        parent = db.get(PipelineDraft, parent_session.draft_id)
        child = PipelineDraft(
            id=_rows.new_id(),
            who=change.who,
            name=(parent.name[:188] + " (corrected)"),
            graph=DraftGraph().model_dump(mode="json"),
            updated_at=_rows.now(),
            ownership="authored",
            forked_from=parent.id,
            fork_key=fork_key(parent_session, parent, change),
            fork_sequence=parent.decision_sequence,
            fork_at=_rows.now(),
            decision_revision=0,
            decision_sequence=0,
            projection_current=False,
        )
        db.add(child)
        db.flush()
        decisions.inherit_in(db, parent, child)
        sid = describe.open_session(child.id, who=change.who, start="fork_correction")
        row = db.get(PipelineAuthoringSession, sid)
        row.extraction = parent_session.extraction
        row.pacing, row.show_gaps = parent_session.pacing, parent_session.show_gaps
        row.blueprint, row.registry_digest = (
            parent_session.blueprint,
            parent_session.registry_digest,
        )
        if change.observation_id:
            decisions.acknowledge_observation(
                child.id,
                change.observation_id,
                "selected" if change.kind == "observation" else "retained",
                who=change.who,
            )
        ctx.session_id = sid
        _rows.say_engine(
            sid,
            f"Your manual pipeline is preserved in draft {parent.id}. "
            "This linked draft applies the correction and starts a fresh review.",
        )
        _rows.engine_turn(
            sid,
            lambda seq: [
                Receipt(
                    id=f"fork-{seq}",
                    summary=f"Manual work preserved in draft {parent.id}; "
                    "the correction is in this new draft.",
                    revision=child.revision,
                    by="person",
                ).model_dump(mode="json")
            ],
        )
    return "forked"


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
            else f"kept your selected answer for {change.subject}"
            if change.kind == "retain"
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
            try:
                declaration = registry.stack().measurements
                declaration.get(change.subject)
                if change.value is not None:
                    declaration.check(change.subject, change.value)
            except (ValueError, KeyError, TypeError) as refused:
                raise ValueError(
                    coded("MI0208", f"that answer does not fit {change.subject}")
                ) from refused
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
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        essential = essential or any(
            i.type_id == change.missing and not i.present and i.origin is FactOrigin.PERSON_SAID
            for i in decisions.read(row.draft_id).inputs
        )
    if essential:
        return "essential_missing"
    from mendel_api.authoring.types import FactKind
    from mendel_api.services import explain, gaps
    from mendel_api.stages import gathering

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        gap = gaps.Gap(
            FactKind.INPUT,
            change.missing,
            "the corrected pipeline needs this input and its required states",
        )
        stack = registry.stack()
        facts = authoring_decisions.facts(row.draft_id)
        options = gathering._gap_options(gap, stack, facts)
        question = gathering._gap_question(gap, options, stack, row.row_version)
        # Explained like gathering's questions (Part I.1): the walk's readers when the missing
        # type is one of its gaps, and what is still open, so a sample promises only those.
        found = gaps.gaps(decisions.goal(row.draft_id).want, facts, stack)
        found = [] if isinstance(found, gaps.Unreachable) else found
        walked = next((g for g in found if g.subject == gap.subject), gap)
        measured, read = gathering._inspectable(stack)
        explained = explain.explanation(
            gap._replace(used_by=walked.used_by), found, stack, measured=measured, read=read,
            characterisable=gathering._characterisable(),
        )
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
                "explain": explained.model_dump(mode="json"),
            },
        )
    return "gather_missing"


_SOURCE_WORDS = {
    "person_said": "you said",
    "measured": "measured",
    "model_read": "read by AI",
    "open": "unknown",
}


def compare_if_needed(ctx: Ctx, continuation):
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        if not decisions.pending_evidence(row.draft_id):
            return False
    ctx.payload = p.SampleAnswered(answered=False, conflicts=True, continuation=continuation)
    return True


def _value_word(value):
    return (
        "unknown"
        if value is None
        else ("yes" if value is True else "no" if value is False else str(value))
    )


@handles("compare_evidence")
def compare_evidence(ctx: Ctx):
    from mendel_api.authoring.types import Option, Question

    if not isinstance(ctx.payload, p.SampleAnswered):
        raise TypeError("evidence comparison needs its closed continuation")
    continuation = ctx.payload.continuation
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, ctx.session_id)
        unseen = decisions.pending_evidence(row.draft_id)
        if not unseen:
            raise ValueError("the evidence comparison has no unanswered observation")
        evidence = unseen[0]
        stale_proposals(db, row.id)
        row.row_version = session.changed_version(db, row.id, row.row_version)
        active = _value_word(evidence["current_value"])
        observed = _value_word(evidence["observed_value"])
        active_source = _SOURCE_WORDS[evidence["current_origin"]]
        observed_source = _SOURCE_WORDS[evidence["observed_origin"]]
        options = {
            "keep_current": f"Keep {active} ({active_source})",
            "use_measurement": f"Use {observed} ({observed_source})",
            "correct": "Use another answer",
            "unknown": "Return to unknown",
        }
        question = Question(
            id=f"disagreement-{row.row_version}",
            asks=f"For {evidence['subject']}, your answer is {active} ({active_source}), "
            f"but this sample says {observed} ({observed_source}). Which should we use?",
            why_open="Evidence never replaces your selected answer automatically.",
            options=[Option(id=k, label=v) for k, v in options.items()],
            exhaustive=True,
        )
        _rows.propose(
            row.id,
            kind="disagreement",
            payload={
                **evidence,
                "continuation": continuation,
                "options": options,
                "block": question.model_dump(mode="json"),
            },
        )
    return "disagree_" + ("gather" if continuation == "stopped" else continuation)


@records(c.AnswerDisagreement)
def answer_disagreement(ctx: Ctx, cmd: c.AnswerDisagreement):
    from mendel_api.authoring import envelopes

    with session_scope() as db:
        proposal = db.get(
            PipelineAuthoringProposal, cmd.proposal_id, with_for_update=True, populate_existing=True
        )
        if proposal is None:
            raise KeyError(cmd.proposal_id)
        if proposal.state != ProposalState.PENDING.value:
            raise ValueError(coded("MI0203", "this evidence question has already been answered"))
        offer = _rows.read_offer(db, proposal)
        if not isinstance(offer, envelopes.DisagreementOffer):
            raise ValueError(coded("MI0205", "that proposal is not an evidence question"))
        envelopes.answer(offer, option=cmd.option, decision_revision=cmd.expected_decision_revision)
        versioned = c.CorrectFact(
            proposal.session_id,
            offer.subject,
            cmd.value,
            cmd.by,
            cmd.expected_decision_revision,
            cmd.expected_draft_revision,
            cmd.expected_session_version,
        )
        row, draft = checked(db, versioned)
        session.check(row.id, Command.ANSWER_DISAGREEMENT.value)
        fresh = next(
            (
                e
                for e in decisions.pending_evidence(draft.id)
                if e["observation_id"] == offer.observation_id
            ),
            None,
        )
        if fresh is None or fresh["current_revision_id"] != offer.current_revision_id:
            raise ValueError(
                coded("MI0201", "the active answer changed; refresh this evidence question")
            )
        if cmd.option == "correct" and cmd.value is None:
            raise ValueError(coded("MI0208", "enter another answer, or choose unknown"))
        kind = {
            "keep_current": "retain",
            "use_measurement": "observation",
            "correct": "measurement",
            "unknown": "measurement",
        }[cmd.option]
        value = (
            offer.observed_value
            if cmd.option == "use_measurement"
            else None
            if cmd.option in ("unknown", "keep_current")
            else cmd.value
        )
        payload = p.Correction(
            subject=offer.subject,
            value=value,
            who=cmd.by,
            kind=kind,
            observation_id=offer.observation_id,
            continuation=offer.continuation,
            before=bp.Blueprint.model_validate(row.blueprint) if row.blueprint else None,
        )
        ctx.session_id = row.id
        if draft.ownership == "manual":
            session.check(row.id, Command.FORK_CORRECTION.value)
            existing = existing_fork(db, row, draft, payload)
            if existing:
                return result(existing)
            session.take(ctx, Command.FORK_CORRECTION.value, payload)
            return result(ctx.session_id)
        proposal.state = ProposalState.ACCEPTED.value
        proposal.by, proposal.chosen_option = cmd.by, cmd.option
        proposal.actor_kind = "person"
        proposal.settled_at = _rows.now()
        decisions.acknowledge_observation(
            draft.id,
            offer.observation_id,
            "selected" if cmd.option == "use_measurement" else "retained",
            who=cmd.by,
        )
        ctx.session_id = row.id
        session.take(ctx, Command.ANSWER_DISAGREEMENT.value, payload)
    return result(ctx.session_id)
