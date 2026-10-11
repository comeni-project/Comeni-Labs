"""② The engine gathers what it needs: the needs, a question at a time, the answers, and the
model's words for each question (14.7.8.1; plan 1c). Moved from `services/authoring.py`."""

import hashlib
import json
import logging

from comeni_core.declared.measurement import MeasurementKind
from comeni_core.diagnostics import coded
from comeni_core.goal.profile import Evidence
from comeni_core.review.answer import ValueSource
from mendel_authoring import commands as c
from mendel_authoring import interpret
from mendel_authoring import payloads as p
from mendel_authoring import state as st
from mendel_authoring.types import Command
from mendel_resolver.goal import Goal
from sqlalchemy import select

from mendel_api.authoring.types import (
    AskedGap,
    Fact,
    FactKind,
    FactSource,
    GoalSummary,
    Option,
    Phase,
    ProposalState,
    Question,
    TurnRole,
)
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
    PipelinePhrasing,
)
from mendel_api.services import authoring_decisions, decisions, gaps, registry, session
from mendel_api.services.session import Ctx, handles, records
from mendel_api.stages import _jobs, _rows
from mendel_api.stages._rows import GOAL, propose
from mendel_api.stages._rows import engine_turn as _engine_turn
from mendel_api.stages._rows import now as _now
from mendel_api.stages._rows import say_engine as _say
from mendel_api.stages._rows import swap as _swap

log = logging.getLogger(__name__)

READS = ("to_phrase", "gap_context", "compose_goal", "as_goal", "_inspectable", "phrasing_context")
"""What a job may read of this stage directly (ruling 2 of plan 1c); every change is a command."""

GAP = _rows.GAP


_INPUT_OPTIONS = {
    "have_it": "I have it",
    "cant_share": "I have it, but can't share it",
    "dont_have": "I don't have one",
}


_UNSURE = {"not_sure": "Not sure", "cant_share": "I can't share it"}


_SOURCE = {
    FactSource.PERSON_SAID: ValueSource.GOAL,
    FactSource.MODEL_READ: ValueSource.MODEL,
    FactSource.MEASURED: ValueSource.MEASURED,
}
"""A fact's source as the profile records it. An `OPEN` fact never reaches the profile, which is
what makes it tier 4."""


UPLOAD = "upload"
"""The option that opens an upload. **The click is not an answer**: the sample is (#134)."""


def _inspectable(stack) -> tuple[dict[str, set[str]], set[str]]:
    """Each measurement a trusted inspector measures, with the input types its formats read;
    and every input type a trusted format reads."""
    from mendel_api.services import measurers

    pieces = measurers.usable_pieces(stack)
    measured: dict[str, set[str]] = {}
    for measure in pieces.measures.values():
        for fmt in pieces.formats.values():
            if fmt.record == measure.record:
                measured.setdefault(measure.measures, set()).update(fmt.reads)
    read = {t for fmt in pieces.formats.values() for t in fmt.reads}
    return measured, read


def _answer_of(proposal: PipelineAuthoringProposal, facts: list[dict]) -> str | None:
    """What was said to an answered gap, for the log: the typed value, or the option's label.
    `None` for anything that is not a gap (issue 169)."""
    if proposal.kind != GAP or proposal.chosen_option is None:
        return None
    if proposal.chosen_option == UPLOAD and proposal.payload.get("kind") == FactKind.INPUT.value:
        # An input a sample answered: the person has it, and the sample showed what it is. The
        # option's label would crowd the question out of its line (issue 232). The AI reading
        # it says so (14.7.7).
        subject = proposal.payload.get("subject")
        read_by_ai = any(
            f.get("subject") == subject and f.get("source") == FactSource.MODEL_READ.value
            for f in facts
        )
        return _INPUT_OPTIONS["have_it"] + (" · read by AI" if read_by_ai else "")
    if proposal.chosen_option in ("value", UPLOAD):
        # A sample's answer is what it measured, never the label of the option that opened it.
        subject = proposal.payload.get("subject")
        said = next((f.get("value") for f in facts if f.get("subject") == subject), None)
        if said is True or said is False:
            return "yes" if said else "no"
        return None if said is None else str(said)
    return (proposal.payload.get("options") or {}).get(proposal.chosen_option)


def _gap_options(gap: gaps.Gap, stack, facts: list[Fact]) -> dict[str, str]:
    """The closed answers to one gap, as option id → label. The engine mints every id."""
    measured, read = _inspectable(stack)
    if gap.kind is FactKind.INPUT:
        # A sample nothing here reads is read by the AI (14.7.7), so the upload is offered
        # wherever the AI may read one — not only where a format reads the type.
        if gap.subject in read or _characterisable():
            have, *rest = _INPUT_OPTIONS.items()
            return dict([have, (UPLOAD, "I have it, and I'll upload a sample"), *rest])
        return dict(_INPUT_OPTIONS)
    measurement = stack.measurements.get(gap.subject)
    if measurement.kind is MeasurementKind.ENUM:
        options = {value: value for value in measurement.values}
    elif measurement.kind is MeasurementKind.BOOLEAN:
        options = {"yes": "Yes", "no": "No"}
    else:
        unit = f" ({measurement.unit})" if measurement.unit else ""
        options = {"value": f"Type it{unit}"}
    has = {f.subject for f in facts if f.kind is FactKind.INPUT}
    # Keyed on what the measuring formats read, not on the measurement's `describes:`, which
    # `read_length` leaves unset.
    if measured.get(gap.subject, set()) & has:
        # **Not sure becomes measurable**: a person who does not know can upload a sample and
        # have it measured, so *not sure* is offered as that (spec §1). **Only when what they
        # have is something an inspector reads** (issue 227, decided A): an upload of a BAM
        # would end in *nothing reads this type yet*, and *not sure* stays.
        return {
            **options,
            UPLOAD: "Not sure: upload a sample and I'll measure it",
            "cant_share": _UNSURE["cant_share"],
        }
    return {**options, **_UNSURE}


def _gap_question(gap: gaps.Gap, options: dict[str, str], stack, seq: int) -> Question:
    """The engine's own wording. A model rephrases it for the person in 14.7.3.6."""
    if gap.kind is FactKind.INPUT:
        asks = f"This analysis needs {gap.subject}. Do you have one?"
    else:
        described = stack.measurements.get(gap.subject).description or gap.subject
        asks = f"{described}?"
    return Question(
        id=f"gap-{seq}",
        asks=asks,
        why_open=gap.why,
        options=[Option(id=key, label=label) for key, label in options.items()],
        exhaustive=True,
    )


def _gathered(session_id: str) -> tuple[dict, list[Fact], int]:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        extracted = authoring_decisions.extracted(row)
        wanted = extracted.model_dump(mode="json") if extracted else {}
        current = decisions.goal(row.draft_id)
        if current.want:
            wanted = {**wanted, "want": current.want,
                      "constraints": current.constraints.model_dump(mode="json")}
        return wanted, authoring_decisions.facts(row.draft_id), row.row_version


def as_goal(stored: dict | None) -> Goal | None:
    """Parse the composed current snapshot or the derived goal card."""
    return Goal.model_validate(stored) if stored is not None else None


def _goal_evidence(evidence: dict | None) -> Evidence | None:
    """Only the counts the goal's `Evidence` declares. A measure's other evidence (`min`,
    `max`, `pairs`) stays on the session's fact and the card; the goal is reachable from the
    doors and carries counts only."""
    counts = {k: evidence[k] for k in ("records", "rows", "share") if k in (evidence or {})}
    return Evidence(**counts) if counts else None


def compose_goal(session_id: str) -> Goal:
    """The want, and everything gathering learned, as the `Goal` the resolver runs on.

    **An open fact is absent, not empty.** A measurement nobody knows is left out of the
    profile, and the tiers carry every decision that reads it as tier 4 (protocol rule 6).
    """
    wanted, _facts, _ = _gathered(session_id)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        current = decisions.goal(row.draft_id)
    # The card proposes the extracted want. It is selected only by confirmation.
    if current.want:
        return current
    return current.model_copy(update={"want": wanted.get("want", []),
                                      "constraints": Goal.model_validate({
                                          "constraints": wanted.get("constraints") or {}}
                                      ).constraints})


UNREACHABLE_ASK = "Nothing here can produce what you asked for. What result do you want?"
"""The engine's question when nothing can make a model-chosen want (#202). **It names no type**:
the type was the model's guess, not the person's word, and types declare no description."""


def need_listed(session_id: str) -> bool:
    """`list_needs`: can anything make the want? **A dead end asks** (#202): the person is asked
    what they want, and the want is cleared so their reply is read from the top."""
    wanted, facts, version = _gathered(session_id)
    stack = registry.stack()
    found = gaps.gaps(wanted.get("want", []), facts, stack)

    if isinstance(found, gaps.Unreachable):
        # **A dead end asks** (#202). Only a model's want reaches here — a goal edited on the
        # card is admitted and goes straight to resolving — so the person is asked what they
        # want, and the want is cleared so their reply is read from the top.
        # **The type stays out of the transcript**: it was the model's guess, so the person sees
        # the code and the question, and the server log says which type (review, #202).
        log.info(
            "MI0209 session %s: nothing in the registry can make %s", session_id, found.subject
        )
        _engine_turn(
            session_id,
            lambda seq: [
                {"kind": "notice", "id": f"notice-{seq}", "notice": "validation",
                 "text": coded("MI0209", "nothing here can make the result read from what you "
                               "said"),
                 "code": "MI0209"},
                Question(
                    id=f"question-{seq}-1",
                    asks=UNREACHABLE_ASK,
                    why_open="nothing here makes the result read from what you said",
                    options=[],
                    exhaustive=False,
                ).model_dump(mode="json"),
            ],
        )
        _rows.store_extraction(session_id, None)
        return False

    return True


def offer_gap_or_card(session_id: str) -> str:
    """`next_gap`: offer the next thing the want needs (`a_gap`), or the goal card
    (`nothing_missing`)."""
    wanted, facts, version = _gathered(session_id)
    stack = registry.stack()
    found = gaps.gaps(wanted.get("want", []), facts, stack)

    if not found:
        goal = compose_goal(session_id)
        inputs = ", ".join(h.type_id for h in goal.have) or "nothing"
        summary = GoalSummary(
            id=f"goal-{version}",
            goal=goal,
            have=f"You have: {inputs}.",
            do="The engine builds it from what you said.",
            readback_pending=_model_configured(),
            suggested=(wanted.get("suggested") or {}).get("required_states") or [],
            get=f"You get: {', '.join(goal.want)}.",
        )
        propose(
            session_id,
            kind=GOAL,
            payload={
                "block": summary.model_dump(mode="json"),
                "goal": goal.model_dump(mode="json"),
                "options": {"accept": "accept"},
            },
        )
        return "nothing_missing"

    gap = found[0]
    options = _gap_options(gap, stack, facts)
    question = _gap_question(gap, options, stack, version)
    heard = next(
        (
            c
            for c in wanted.get("stated") or []
            if c.get("kind") == gap.kind.value and c.get("subject") == gap.subject
        ),
        None,
    )
    if heard is not None and (fill := _candidate_option(gap.kind, heard.get("value"), options)):
        question = _prefilled(question, *fill, note=STATED_NOTE)
    cached, phrased = cached_phrasing(session_id, gap.subject)
    if phrased is not None:
        question = _phrased(question, AskedGap.model_validate(phrased), gap.kind, options)
    elif _model_configured() and not cached:
        question = question.model_copy(update={"phrasing": "pending"})
    propose(
        session_id,
        kind=GAP,
        payload={
            "subject": gap.subject,
            "kind": gap.kind.value,
            "why": gap.why,
            "options": options,
            "block": question.model_dump(mode="json"),
        },
    )
    return "a_gap"


STATED_NOTE = "you mentioned it"
"""The note on an option a stated candidate pre-fills (#170)."""


READ_NOTE = "read from your reply"
"""The note on an option a model's reading of a typed reply pre-fills (#171)."""


def _candidate_option(kind: FactKind, value, options: dict[str, str]):
    """The option (and typed value) a candidate stands for, or `None` if none of the gap's."""
    if kind is FactKind.INPUT:
        return ("have_it", None) if "have_it" in options else None
    if "value" in options and not isinstance(value, bool):
        return "value", value
    chosen = ("yes" if value else "no") if isinstance(value, bool) else str(value)
    return (chosen, None) if chosen in options else None


def _prefilled(question: Question, option: str, value, *, note: str) -> Question:
    """The question with one answer suggested — marked, noted, and still only a suggestion."""
    return question.model_copy(
        update={
            "options": [
                o.model_copy(update={"recommended": o.id == option,
                                     "note": note if o.id == option else None})
                for o in question.options
            ],
            "value": value if option == "value" else None,
        }
    )


def prefill_gap(proposal_id: str, option: str, value, *, note: str) -> None:
    """Suggest one answer on the pending gap, without answering it (#171).

    A model's reading of the person's words is a suggestion the person confirms with a click;
    only `answer_gap` records a fact. Held first like an answer: an option the gap did not offer
    is MI0205, a value its declaration refuses is MI0208, and nothing is written then.
    """
    stack = registry.stack()
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        if proposal.kind != GAP or proposal.state != ProposalState.PENDING.value:
            raise ValueError(coded("MI0205", "there is no question about your data waiting"))
        payload = dict(proposal.payload)
        if option not in payload["options"]:
            raise ValueError(
                coded("MI0205", "that is not one of the answers this question offered")
                + f"\n  it offered: {', '.join(payload['options'])}"
            )
        if option == UPLOAD:
            # A reading of words is a value or an answer, never an upload: the person's
            # confirming click would then be refused (review of #134).
            raise ValueError(coded("MI0205", "a reading cannot answer with an upload"))
        if option == "value":
            try:
                stack.measurements.check(payload["subject"], value)
            except (ValueError, KeyError, TypeError) as refused:
                raise ValueError(
                    coded("MI0208", f"{value!r} does not fit {payload['subject']}")
                    + f"\n  {refused}"
                ) from None
        question = Question.model_validate(payload["block"])
        payload["block"] = _prefilled(question, option, value, note=note).model_dump(mode="json")
        proposal.payload = payload


ALREADY_NOTE = "from what you said earlier"
"""The note on an option a phrasing call heard the person already give (#167)."""


def _characterisable() -> bool:
    """Whether the AI may read a sample here (14.7.7). The seam is `characterise.available`."""
    from mendel_api.services import characterise

    return characterise.available()


def _model_configured() -> bool:
    """Whether a model can phrase questions. The one seam a test replaces."""
    from mendel_api.settings import model_access

    return model_access() is not None


def _phrased(question: Question, asked: AskedGap, kind: FactKind, options: dict) -> Question:
    """The question in the model's words, options untouched; `already` pre-fills only when
    nothing is suggested yet (a stated candidate, heard first, wins)."""
    question = question.model_copy(update={"asks": asked.asks, "phrasing": "done"})
    if any(o.recommended for o in question.options):
        return question
    if asked.already_value is not None and "value" in options:
        return _prefilled(question, "value", asked.already_value, note=ALREADY_NOTE)
    if asked.already_option is not None and asked.already_option in options:
        return _prefilled(question, asked.already_option, None, note=ALREADY_NOTE)
    return question


def phrasing_context(session_id, subject):
    context = gap_context(session_id, subject)
    if context is None:
        return None
    wanted, _facts, _version = _gathered(session_id)
    digest = hashlib.sha256(json.dumps({"question": context, "want": wanted.get("want"),
        "constraints": wanted.get("constraints"), "registry": registry.digest()},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        return p.ContextStamp(decision_revision=draft.decision_revision, context_digest=digest)


def cached_phrasing(session_id, subject):
    stamp = phrasing_context(session_id, subject)
    if stamp is None:
        return False, None
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        cached = db.get(PipelinePhrasing, (row.draft_id, subject,
                                          stamp.decision_revision, stamp.context_digest))
        return (cached is not None, cached.asked if cached else None)


def store_phrasing(session_id: str, subject: str, asked: AskedGap | None, stamp) -> None:
    """Store wording only for the selected revision and semantic context it read."""
    if stamp is None or stamp != phrasing_context(session_id, subject):
        return
    stamp = p.ContextStamp(*stamp)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        key = (row.draft_id, subject, stamp.decision_revision, stamp.context_digest)
        cached = db.get(PipelinePhrasing, key)
        data = asked.model_dump(mode="json") if asked else None
        if cached is None:
            db.add(PipelinePhrasing(draft_id=row.draft_id, subject=subject,
                decision_revision=stamp.decision_revision, context_digest=stamp.context_digest,
                asked=data))
        else:
            cached.asked = data
        pending = _pending_gap(db, session_id)
        if pending is not None and pending.payload.get("subject") == subject:
            payload = dict(pending.payload)
            question = Question.model_validate(payload["block"])
            payload["block"] = (_phrased(question, asked, FactKind(payload["kind"]),
                                         payload["options"]) if asked else question.model_copy(
                                             update={"phrasing": "none"})).model_dump(mode="json")
            pending.payload = payload


def phrasing_failed(session_id: str, subject: str, stamp) -> None:
    store_phrasing(session_id, subject, None, stamp)


def _pending_gap(db, session_id: str):
    pending = db.scalar(select(PipelineAuthoringProposal).where(
        PipelineAuthoringProposal.session_id == session_id,
        PipelineAuthoringProposal.state == ProposalState.PENDING.value))
    return pending if pending is not None and pending.kind == GAP else None


def to_phrase(session_id: str) -> list[str]:
    """The subjects worth phrasing now: the question on offer and the next one (#186), minus any
    already phrased. Empty with no model, or outside gathering."""
    if session.current_phase(session_id) is not Phase.GATHERING:
        return []
    return _unphrased(session_id)


def _unphrased(session_id: str) -> list[str]:
    """`to_phrase` without asking the phase: `ask` is in gathering by being entered, and the
    dispatcher writes the phase only once the session rests (plan 1c)."""
    if not _model_configured():
        return []
    wanted, facts, _ = _gathered(session_id)
    found = gaps.gaps(wanted.get("want", []), facts, registry.stack())
    if isinstance(found, gaps.Unreachable):
        return []
    return [g.subject for g in found[:2] if not cached_phrasing(session_id, g.subject)[0]]


def gap_context(session_id: str, subject: str) -> dict | None:
    """What `builder.ask.v1` is given about one question, or `None` if it is no longer needed."""
    wanted, facts, version = _gathered(session_id)
    stack = registry.stack()
    found = gaps.gaps(wanted.get("want", []), facts, stack)
    if isinstance(found, gaps.Unreachable):
        return None
    gap = next((g for g in found if g.subject == subject), None)
    if gap is None:
        return None
    options = _gap_options(gap, stack, facts)
    described = (
        stack.measurements.get(subject).description
        if gap.kind is FactKind.MEASUREMENT
        else f"an input the analysis reads: {subject}"
    )
    with session_scope() as db:
        first = db.scalar(
            select(PipelineAuthoringTurn)
            .where(
                PipelineAuthoringTurn.session_id == session_id,
                PipelineAuthoringTurn.role == TurnRole.PERSON,
            )
            .order_by(PipelineAuthoringTurn.seq)
            .limit(1)
        )
    return {
        "subject": subject,
        "kind": gap.kind.value,
        "asks": _gap_question(gap, options, stack, version).asks,
        "description": described or subject,
        "options": options,
        "facts": "; ".join(
            f"{f.subject}: {f.value if f.value is not None else f.source.value}" for f in facts
        ),
        "first_sentence": first.text if first is not None else "",
    }


def _fact_for(kind: FactKind, subject: str, option: str, value) -> Fact:
    """What one answer means. Nothing is guessed: *not sure* and *can't share* are `OPEN`."""
    if kind is FactKind.INPUT:
        # *I have it, but can't share it* is still having it: the input is real.
        return Fact(kind=kind, subject=subject, source=FactSource.PERSON_SAID)
    if option in _UNSURE:
        return Fact(kind=kind, subject=subject, source=FactSource.OPEN)
    said = {"yes": True, "no": False, "value": value}.get(option, option)
    return Fact(kind=kind, subject=subject, value=said, source=FactSource.PERSON_SAID)


@records(c.AnswerGap)
def _answer_gap(ctx: Ctx, cmd: c.AnswerGap) -> Phase:
    """Record one answer to a gap and offer the next, or stop honestly on a missing input.

    Held before anything is written: an option the gap did not offer is MI0205, and a typed value
    the measurement's declaration refuses is MI0208. **The draft's revision does not move** — a
    gap answer changes what the engine knows, not the pipeline — so the settlement is checked by
    `st.settle` (a duplicate answer is MI0203) against the proposal's own revision.
    """
    proposal_id, option, value, by = cmd.proposal_id, cmd.option, cmd.value, cmd.by
    stack = registry.stack()
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        if proposal.kind != GAP:
            raise ValueError(coded("MI0205", "that proposal is not a question about your data"))
        payload = _rows.read_offer(db, proposal).model_dump(mode="json")
        if option not in payload["options"]:
            raise ValueError(
                coded("MI0205", "that is not one of the answers this question offered")
                + f"\n  it offered: {', '.join(payload['options'])}"
            )
        if option == UPLOAD:
            raise ValueError(
                coded("MI0205", "upload a sample to answer this; the click is not one")
            )
        kind, subject = FactKind(payload["kind"]), payload["subject"]
        if option == "value":
            try:
                if value is None:
                    raise ValueError("no value was given")
                stack.measurements.check(subject, value)
            except (ValueError, KeyError) as refused:
                raise ValueError(
                    coded("MI0208", f"{value!r} does not fit {subject}") + f"\n  {refused}"
                ) from None

        settled = st.settle(
            current=ProposalState(proposal.state),
            proposal_revision=proposal.draft_revision,
            draft_revision=proposal.draft_revision,
            expected_revision=proposal.draft_revision,
            decision=ProposalState.ACCEPTED,
        )
        if settled.refusal is not None:
            raise ValueError(settled.refusal)
        session.check(proposal.session_id, Command.ANSWER_GAP.value)
        if ((payload.get("block") or {}).get("reading") or {}).get("state") == "pending":
            # The person answered while the AI read (issue 241): the reading ends, unspent.
            from mendel_api.stages import samples  # samples imports this module

            samples._set_reading(db, proposal, None)
        proposal.state = ProposalState.ACCEPTED.value
        proposal.by = by
        proposal.chosen_option = option
        proposal.settled_at = _now()

        session_id = ctx.session_id = proposal.session_id
        row = db.get(PipelineAuthoringSession, session_id)
        stops = kind is FactKind.INPUT and option == "dont_have"
        if stops:
            from mendel_authoring.decisions import InputDecision

            decisions.set_input(row.draft_id, InputDecision(
                key=subject, type_id=subject, present=False), who=by)
        else:
            authoring_decisions.record(row.draft_id,
                                      _fact_for(kind, subject, option, value).model_copy(
                    update={"states": payload.get("states", [])} if kind is FactKind.INPUT
                    else {}), who=by)
        _swap(db, session_id, row.row_version)

    # `_fact_for` decides what an answer means, so it decides the arrow too: *I have it, but
    # can't share it* is still having the input (`said`), *not sure* is `left_open`.
    if stops:
        kind_of = "no_input"
    elif _fact_for(kind, subject, option, value).source is FactSource.OPEN:
        kind_of = "left_open"
    else:
        kind_of = "said"
    session.take(ctx, Command.ANSWER_GAP.value, p.GapAnswered(answered=kind_of))
    if stops:
        _say(
            session_id,
            f"This analysis needs {subject}, and without one it cannot be built. Nothing was "
            "built. Start again when you have one, or describe a different analysis.",
        )
    return session.current_phase(session_id)



# ── the commands ─────────────────────────────────────────────────────────────────────────


@records(c.PrefillGap)
def _prefill(ctx: Ctx, cmd: c.PrefillGap) -> None:
    prefill_gap(cmd.proposal_id, cmd.option, cmd.value, note=cmd.note)


@records(c.StorePhrasing)
def _store_phrasing(ctx: Ctx, cmd: c.StorePhrasing) -> None:
    store_phrasing(cmd.session_id, cmd.subject, AskedGap.model_validate(cmd.asked), cmd.stamp)


@records(c.PhrasingFailed)
def _phrasing_failed(ctx: Ctx, cmd: c.PhrasingFailed) -> None:
    phrasing_failed(cmd.session_id, cmd.subject, cmd.stamp)


@records(c.Resume)
def _resume(ctx: Ctx, cmd: c.Resume) -> interpret.Ran:
    return session.resume(cmd.session_id, ctx=ctx)


# ── the handlers ─────────────────────────────────────────────────────────────────────────


@handles("list_needs")
def list_needs(ctx: Ctx) -> str:
    return "listed" if need_listed(ctx.session_id) else "unreachable"


@handles("next_gap")
def next_gap(ctx: Ctx) -> str:
    return offer_gap_or_card(ctx.session_id)


@handles("answered")
def answered(ctx: Ctx) -> str:
    """Which of the three the answer was: `answer_gap` recorded it, and says which."""
    if not isinstance(ctx.payload, p.GapAnswered):
        raise TypeError("answered requires GapAnswered")
    return ctx.payload.answered


@handles("ask")
def ask(ctx: Ctx) -> None:
    """The question on offer and the next, phrased while the person reads (#167, #186; ruling 6
    of plan 1c). Passes straight through to `reply`."""
    queue_phrasing(ctx)
    return None


@handles("suggest")
def suggest(ctx: Ctx) -> None:
    """Typed words answering a question: the model reads them into a suggestion (#171). The turn
    `Say` wrote is queued. Passes straight back to `reply`."""
    from mendel_api.stages import describe

    ctx.queue(_jobs.turn(ctx.session_id, describe.newest_pending(ctx.session_id)))
    return None


def queue_phrasing(ctx: Ctx) -> None:
    for subject in _unphrased(ctx.session_id):
        ctx.queue(_jobs.phrase(ctx.session_id, subject))
