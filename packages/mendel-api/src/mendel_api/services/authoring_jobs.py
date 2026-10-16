"""The builder's AI-queue jobs: answering a turn, phrasing, reading back, characterising.

**Only what calls a provider lives here, and only the AI worker runs it.** Accepting a step, a
goal, or a retry into Build is an ordinary request — §2: *do not put a button click behind the
slow queue*. What is queued is a model call: understanding prose, answering a follow-up,
phrasing a question, reading a goal back, reading a sample.

**Every enqueue names its job by what the work is about.** `builder:turn:<session>:<seq>`, so a
redeploy re-delivering a job collides at the queue rather than producing a second answer — and
the job checks the turn is still pending before it spends a call, so a delivery that slips past
the queue's memory costs nothing either. *Exactly once* is those two together, never either one.

**A job never raises for a refusal.** A refused answer, a missing model and a provider that did
not answer each end as a `notice` block with a declared code in the transcript, because the
transcript is what the person reads. An exception would end the job in a log nobody opens and
leave the turn spinning.
"""

import logging

from comeni_ai import Client
from mendel_authoring import commands as c
from mendel_authoring.interpret import Refused

from mendel_api.authoring.types import (
    ChatReply,
    Narrative,
    Notice,
    NoticeKind,
    Option,
    Phase,
    Question,
    Understanding,
)
from mendel_api.db import session_scope
from mendel_api.services import (
    authoring_ai,
    authoring_decisions,
    decisions,
    known,
    registry,
    replies,
    suggestions,
)
from mendel_api.services import session as session_mod
from mendel_api.settings import model_access, settings
from mendel_api.stages import describe, gathering, goal
from mendel_api.stages._jobs import ANSWER, CHARACTERISE, PHRASE, READ_BACK

log = logging.getLogger(__name__)


AI_JOBS = frozenset({ANSWER, PHRASE, READ_BACK, CHARACTERISE})
"""The builder's jobs that reach a provider — `forge_jobs.AI_JOBS`, one agent over.

**Declared by the module that owns them**, and the AI worker's allowlist is held equal to the
union of every owner's set. A single list in `ai_worker.py` would let a job arrive on it without
the module that defines it ever saying it calls a model.
"""

GOAL = goal.GOAL
"""The proposal `kind` for a goal summary awaiting confirmation."""

UNREACHABLE = frozenset({"MI0106", "MA0002", "MA0003", "MA0007"})
"""Codes meaning *no answer could be had*, as opposed to *the answer was not acceptable*.

The first set moves the session to `failed`, where `retry` is the verb; the second leaves it
where it is with a notice, because the person can simply say it differently. Folding them would
either make a missing model look like something rephrasing fixes, or make one badly-shaped answer
stop a whole session.
"""


def _client(purpose: "authoring_ai.Purpose") -> Client | None:
    """The model for this call's purpose, or `None`. The one seam a test replaces to hand over
    a fake. **Every call names its purpose** (14.7.5.4): Settings → Models says which model
    answers it."""
    access = model_access("builder", purpose)
    return Client(access) if access is not None else None


# ── answering a turn ──────────────────────────────────────────────────────────────────────


async def answer_authoring_turn(ctx: dict, session_id: str, seq: int) -> str:
    """Answer one pending assistant turn. **This is what crosses egress door 1.**"""
    context = describe.turn_context(session_id, seq)
    if context is None:
        # Already answered, or already failed as late. A duplicate delivery must not spend a call.
        return f"{session_id}:{seq} was not pending"

    # **What the commands below ask for is queued once this is done** (plan 1c): the first
    # question's phrasing when the want is understood, the card's read-back.
    async with session_mod.queued_after():
        # **One handler per turn, chosen by the phase the turn was asked in** (#201). Choosing by
        # the phase afterwards ran the follow-up on a turn `_understand` had already answered
        # with a question: a second, wasted call.
        if context.phase is Phase.UNDERSTANDING:
            _understand(session_id, seq, context, context.prompt)
        else:
            # A typed answer to the open question is a fact like any other (#307): the memory
            # tells `chat.v3` which question is open.
            _follow_up(session_id, seq, context)
    return f"{session_id}:{seq}"


NO_FAMILY_FITS = "Which kind of result do you want?"
"""The engine's own question when the family call chose nothing and asked nothing (#194)."""


def _understand(session_id: str, seq: int, context, prompt: str) -> None:
    request = authoring_ai.compose(prompt=prompt, turns=context.tail, registry=context.registry)
    stack = registry.stack()
    ack, families = None, None
    if len(stack.vocabulary.types) >= settings.family_step_from:
        # **The type in two steps** (#194): the families first, then each chosen family whole.
        chosen = authoring_ai.choose_families(
            request, stack=stack, memory=known.text(session_id),
            client=_client(authoring_ai.Purpose.FAMILY), session_id=session_id,
        )
        if not chosen.admitted:
            _refused(session_id, seq, context, chosen)
            return
        ack, families = chosen.reply.ack, list(chosen.reply.families)
        if chosen.reply.fits != "yes" or not families:
            # **The verdict decides, not the list** (#202): families beside a `no` are ignored,
            # and a `yes` naming nothing would show the goal call nothing.
            # **No family fits: ask, never pick the nearest.** The goal call is not made, and
            # the person's answer is read again from the top, still in `understanding`.
            _ask_which_result(
                session_id, seq, context, ack, chosen.reply.unclear, chosen.invocation_id
            )
            return

    outcome = authoring_ai.understand(
        request,
        stack=stack,
        families=families,
        memory=known.text(session_id),
        client=_client(authoring_ai.Purpose.GOAL),
        session_id=session_id,
    )

    if not outcome.admitted:
        _refused(session_id, seq, context, outcome)
        return

    understood: Understanding = outcome.reply
    said = ack or understood.say or ""
    blocks = [Narrative(id=f"want-{seq}", text=said).model_dump(mode="json")]
    for index, asked in enumerate(understood.questions, start=1):
        # **The engine mints the option ids here** — `AskedQuestion` carries labels only, so the
        # set a later `chose` is checked against is one this server issued.
        blocks.append(
            Question(
                id=f"question-{seq}-{index}",
                asks=asked.asks,
                why_open=asked.why_open,
                options=[
                    Option(id=f"q{index}_{choice}", label=label)
                    for choice, label in enumerate(asked.choices, start=1)
                ],
                exhaustive=asked.exhaustive,
            ).model_dump(mode="json")
        )

    if not _answered(
        session_id,
        seq,
        blocks=blocks,
        base_revision=context.revision,
        invocation_id=outcome.invocation_id,
    ):
        return
    if understood.questions:
        # **An ambiguous want waits for the person's reply**, still in `understanding`, and that
        # reply is read again from the top. Gathering for a want nobody settled would ask about
        # inputs to an analysis they may not want.
        _perform(c.AskedBack(session_id))
        return

    # **The engine takes over from here** (14.7.3): what the want needs is computed, not asked
    # of a model. What the model heard, quoting the person, is recorded; what it suggests waits
    # for a click (#307).
    issued = replies.issue(
        understood, turns=replies.person_turns(session_id), stack=stack,
        invocation_id=outcome.invocation_id, first_reading=True,
    )
    _perform(
        c.Understood(
            session_id,
            {
                "heard": [change.model_dump(mode="json") for change in issued.heard],
                "suggested": [change.model_dump(mode="json") for change in issued.suggested],
            },
        )
    )  # `understood` runs on to the first question (`list_needs`, `next_gap`): 14.7.8.1


def _ask_which_result(
    session_id: str, seq: int, context, ack: str, unclear: str | None, invocation_id: str | None
) -> None:
    blocks = [
        Narrative(id=f"want-{seq}", text=ack).model_dump(mode="json"),
        Question(
            id=f"question-{seq}-1",
            asks=unclear or NO_FAMILY_FITS,
            why_open="none of the kinds of result on offer fits what you said",
            options=[],
            exhaustive=False,
        ).model_dump(mode="json"),
    ]
    _answered(
        session_id,
        seq,
        blocks=blocks,
        base_revision=context.revision,
        invocation_id=invocation_id,
    )
    _perform(c.AskedBack(session_id))


async def characterise_sample(
    ctx: dict, session_id: str, proposal_id: str, attempt: int, text: str, binary_before: bool,
    decision_revision=None, session_version=None,
) -> str:
    """Read a sample nothing here reads, through door 6 (14.7.7). A failure is a reading state."""
    from mendel_api.services import characterise

    try:
        async with session_mod.queued_after():
            state = characterise.read_sample(
                session_id, proposal_id, attempt, str(text), binary_before, client_for=_client,
                decision_revision=decision_revision, session_version=session_version,
            )
    except Exception:
        # **Never left pending** (issue 241): whatever broke, the card says the AI didn't
        # answer and the person may try again. `reading_failed` checks the attempt.
        log.exception("reading %s:%s failed", proposal_id, attempt)
        _perform(c.ReadingFailed(proposal_id, attempt, "no_answer", "MA0007"))
        state = "no_answer"
    return f"{proposal_id}:{attempt}:{state}"


async def read_back_authoring_goal(ctx: dict, session_id: str, proposal_id=None) -> str:
    """Read the composed goal back to the person (#176). A failure leaves the engine's sentence."""
    if proposal_id is not None and session_mod.pending_id(session_id) != proposal_id:
        return f"{session_id}: outdated goal card"
    if not goal.wants_readback(session_id):
        return f"{session_id}: no card waiting for a read-back"
    stamp = goal.readback_context_stamp(session_id)
    outcome = authoring_ai.read_back(
        authoring_ai.compose(prompt="", registry=registry.digest()),
        goal=goal.readback_context(session_id),
        memory=known.text(session_id),
        client=_client(authoring_ai.Purpose.READBACK),
        session_id=session_id,
    )
    if outcome.admitted:
        _perform(c.StoreReadback(session_id, outcome.reply.text, stamp))
    else:
        _perform(c.ReadbackFailed(session_id, stamp))
    return f"{session_id}: read back"


async def phrase_authoring_gap(ctx: dict, session_id: str, subject: str,
                               decision_revision=None, context_digest=None) -> str:
    """Phrase one gathering question for the person (#167). A failure leaves the engine's words."""
    gap = gathering.gap_context(session_id, subject)
    if gap is None:
        return f"{session_id}:{subject} is no longer asked"
    stamp = gathering.phrasing_context(session_id, subject)
    if (decision_revision is not None and
            (stamp is None or stamp.decision_revision != decision_revision
             or stamp.context_digest != context_digest)):
        return f"{session_id}:{subject}: outdated question context"
    request = authoring_ai.compose(
        prompt=gap["first_sentence"], options=list(gap["options"]), registry=registry.digest()
    )
    outcome = authoring_ai.phrase_gap(
        request,
        gap=gap,
        stack=registry.stack(),
        memory=known.text(session_id),
        client=_client(authoring_ai.Purpose.ASK),
        session_id=session_id,
    )
    if outcome.admitted:
        _perform(c.StorePhrasing(session_id, subject, outcome.reply.model_dump(mode="json"), stamp))
    else:
        _perform(c.PhrasingFailed(session_id, subject, stamp))
    return f"{session_id}:{subject}"


def _narrate(session_id: str, seq: int, context, invocation_id, text: str) -> None:
    _answer_blocks(
        session_id, seq, context, invocation_id,
        [Narrative(id=f"said-{seq}", text=text).model_dump(mode="json")],
    )


def _answer_blocks(session_id: str, seq: int, context, invocation_id, blocks: list) -> None:
    _answered(
        session_id, seq, blocks=blocks, base_revision=context.revision, invocation_id=invocation_id
    )


def _open_subject(session_id: str) -> str | None:
    """The subject id of the gathering question waiting for an answer, if one is (#324)."""
    pending = session_mod.read(session_id).get("pending_proposal")
    if pending is None or pending["kind"] != "gap":
        return None
    return pending["payload"].get("subject")


def _follow_up(session_id: str, seq: int, context) -> None:
    """Typed words anywhere after the want is read (`chat.v3`, #307): something to say, and the
    changes they ask for. **Before the goal is confirmed** a heard change is recorded, through
    the correction path that routes its consequence; a suggested one waits for a click. **After**,
    every change is offered: a model's amendment is shown before it moves anything."""
    stack = registry.stack()
    request = authoring_ai.compose(
        prompt=context.prompt,
        turns=context.tail,
        goal=context.goal,
        steps=context.steps,
        options=context.options,
        registry=context.registry,
    )
    outcome = authoring_ai.follow_up(
        request, stack=stack, memory=known.text(session_id),
        open_question=_open_subject(session_id),
        client=_client(authoring_ai.Purpose.CHAT), session_id=session_id,
    )
    if not outcome.admitted:
        _refused(session_id, seq, context, outcome)
        return

    reply: ChatReply = outcome.reply
    draft_id, wanted = _draft_and_wants(session_id)
    issued = replies.issue(
        reply, turns=replies.person_turns(session_id), stack=stack,
        invocation_id=outcome.invocation_id, wanted=wanted,
    )
    blocks = []
    if reply.say:
        blocks.append(Narrative(id=f"reply-{seq}", text=reply.say).model_dump(mode="json"))
    if outcome.refusal:
        # What admission set aside (#326), named the way a refusal names it (#325).
        blocks.append(Notice(
            id=f"notice-{seq}", notice=NoticeKind.VALIDATION,
            text=_set_aside_text(outcome.refusal), code=outcome.code,
        ).model_dump(mode="json"))
    for index, asked in enumerate(reply.questions, start=1):
        if not asked.choices:
            # **No choices, no card** (#327): a card marked *every option* with nothing to choose
            # stayed open after the goal moved on. Said instead; they answer in their own words.
            blocks.append(Narrative(id=f"question-{seq}-{index}",
                                    text=asked.asks).model_dump(mode="json"))
            continue
        blocks.append(Question(
            id=f"question-{seq}-{index}", asks=asked.asks, why_open=asked.why_open,
            options=[Option(id=f"q{index}_{n}", label=label)
                     for n, label in enumerate(asked.choices, start=1)],
            exhaustive=asked.exhaustive,
        ).model_dump(mode="json"))
    if not _answered(session_id, seq, blocks=blocks or [
            Narrative(id=f"reply-{seq}", text=_noted(issued)).model_dump(mode="json")],
            base_revision=context.revision, invocation_id=outcome.invocation_id):
        return

    if authoring_decisions.confirmed(draft_id):
        for change, heard in [*((c, True) for c in issued.heard),
                              *((c, False) for c in issued.suggested)]:
            suggestions.offer(session_id, change, heard=heard, invocation_id=change.invocation_id)
    else:
        # **Only if nothing moved since the person spoke** (Review Focus 2 of plan A): a click
        # that landed while the model read wins, and the reading is offered instead.
        current = not _moved_since(draft_id, context)
        for index, change in enumerate(issued.heard):
            # The first is held to the spoken-at revision itself, so a click landing between the
            # check and the write is refused by the command's own version check (review I3).
            expected = context.decision_revision if index == 0 else None
            if not (current and _record(session_id, draft_id, change, expected)):
                suggestions.offer(session_id, change, heard=True,
                                  invocation_id=change.invocation_id)
        for change in issued.suggested:
            suggestions.offer(session_id, change, heard=False,
                              invocation_id=change.invocation_id)
    if reply.proceed:
        _proceed(session_id)


def _draft_and_wants(session_id: str):
    from mendel_api.models import PipelineAuthoringSession

    with session_scope() as db:
        draft_id = db.get(PipelineAuthoringSession, session_id).draft_id
    wanted = frozenset(w.type_id for w in decisions.read(draft_id).wants if w.present)
    return draft_id, wanted


def _moved_since(draft_id: str, context) -> bool:
    from mendel_api.models import PipelineDraft

    with session_scope() as db:
        return db.get(PipelineDraft, draft_id).decision_revision != context.decision_revision


def _record(session_id: str, draft_id: str, change, expected: int | None = None) -> bool:
    """One heard change through the correction path, at the versions as they stand now."""
    from mendel_api.models import PipelineAuthoringSession, PipelineDraft

    with session_scope() as db:
        draft = db.get(PipelineDraft, draft_id)
        row = db.get(PipelineAuthoringSession, session_id)
        decided = draft.decision_revision if expected is None else expected
        versions = (decided, draft.revision, row.row_version)
    try:
        session_mod.perform(c.Change(session_id, change.model_dump(mode="json"), "model",
                                     *versions))
    except (Refused, ValueError) as refused:
        log.info("a heard change was offered instead: %s", str(refused).splitlines()[0])
        return False
    return True


def _proceed(session_id: str) -> None:
    """*Go on*: the waiting step is settled, as its card's *continue* would. Elsewhere there is
    nothing to continue, and nothing happens."""
    view = session_mod.read(session_id)
    pending = view.get("pending_proposal")
    if pending is None or pending["kind"] != "step":
        return
    _perform(c.SettleStep(pending["id"], view["revision"], "person"))


def _noted(issued) -> str:
    if issued.heard or issued.suggested:
        return "Noted."
    return "I could not tell what to change from that; say it another way."


def _set_aside_text(refusal: str) -> str:
    """The first line, then each indented line admission wrote, joined (#325)."""
    first, *rest = refusal.splitlines()
    named = [line.strip()[:200] for line in rest if line.startswith("  ") and line.strip()]
    return (f"{first}: {'; '.join(named)}" if named else first)[:2000]


def _refused(session_id: str, seq: int, context, outcome) -> None:
    """A refusal, a missing model, or an unreachable one — as a notice, with its code."""
    code = outcome.code or "MA0004"
    # **What was refused** (issue 325): admission lists each id it could not accept on an
    # indented line beneath its sentence. Those lines name registry ids and the model's own
    # values, so they are kept; any other refusal stays its first line.
    first_line = _set_aside_text(outcome.refusal) if outcome.refusal else code
    _answered(
        session_id,
        seq,
        blocks=[
            Notice(
                id=f"notice-{seq}",
                notice=NoticeKind.REFUSAL,
                text=first_line[:2000],
                code=code,
            ).model_dump(mode="json")
        ],
        base_revision=context.revision,
        invocation_id=outcome.invocation_id,
    )
    if code in UNREACHABLE:
        _failed(session_id)


def _perform(command: object) -> bool:
    """A job's completion is a command (spec §3.2), through the facade (plan 1c). **Refused
    means the session moved on** while the model worked, and the completion is ignored (spec §8),
    never a failed job. Whether it ran."""
    try:
        session_mod.perform(command)
    except Refused as refused:
        log.info("%s ignored: %s", type(command).__name__, str(refused).splitlines()[0])
        return False
    return True


def _answered(session_id: str, seq: int, *, blocks, base_revision, invocation_id=None) -> bool:
    """Fill in the pending turn (`AnswerTurn`): `False` when it was late or already answered."""
    return session_mod.perform(
        c.AnswerTurn(session_id, seq, blocks, base_revision, invocation_id)
    ).result


def _failed(session_id: str) -> None:
    """The model could not be reached. The session fails only where the diagram draws it."""
    _perform(c.ProviderFailed(session_id))

