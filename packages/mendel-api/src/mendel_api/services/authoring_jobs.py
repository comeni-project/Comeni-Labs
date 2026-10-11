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
from mendel_authoring.types import Command

from mendel_api.authoring.types import (
    AuthoringIntent,
    Narrative,
    Notice,
    NoticeKind,
    Option,
    Phase,
    Question,
    WantUnderstanding,
)
from mendel_api.services import authoring_ai, registry
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
        elif context.phase is Phase.GATHERING and _pending_gap(session_id) is not None:
            _gap_reply(session_id, seq, context)
        else:
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
            request, stack=stack, client=_client(authoring_ai.Purpose.FAMILY), session_id=session_id
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
        client=_client(authoring_ai.Purpose.GOAL),
        session_id=session_id,
    )

    if not outcome.admitted:
        _refused(session_id, seq, context, outcome)
        return

    understood: WantUnderstanding = outcome.reply
    said = ack or understood.ack or ""
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

    # **The engine takes over from here, in both modes** (14.7.3). What the want needs is
    # computed, not asked of a model, and each gap needs a person: nothing is guessed, so Spawn
    # has nothing it could fill in on their behalf (protocol rule 5).
    _perform(
        c.Understood(
            session_id,
            {
            "want": list(understood.want),
            # **The model's constraints are suggestions, never the goal's** (#176): the card offers
            # them and only the ones the person keeps are added.
            "constraints": {},
            "suggested": understood.constraints.model_dump(mode="json"),
                "stated": [s.model_dump(mode="json") for s in understood.stated],
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
        client=_client(authoring_ai.Purpose.ASK),
        session_id=session_id,
    )
    if outcome.admitted:
        _perform(c.StorePhrasing(session_id, subject, outcome.reply.model_dump(mode="json"), stamp))
    else:
        _perform(c.PhrasingFailed(session_id, subject, stamp))
    return f"{session_id}:{subject}"


def _pending_gap(session_id: str) -> dict | None:
    pending = session_mod.read(session_id)["pending_proposal"]
    return pending if pending is not None and pending["kind"] == gathering.GAP else None


def _gap_reply(session_id: str, seq: int, context) -> None:
    """A typed answer to the pending gap, read into one of its ids — or re-offered, never guessed.

    Clicking an option answers without this; typing is the path that needs a model to read words
    back into an id the engine minted (`builder.gap.v1`).
    """
    gap = _pending_gap(session_id)
    options = gap["payload"]["options"]
    request = authoring_ai.compose(
        prompt=context.prompt, turns=context.tail, options=list(options), registry=context.registry
    )
    outcome = authoring_ai.read_gap_reply(
        request,
        question=gap["payload"]["block"]["asks"],
        client=_client(authoring_ai.Purpose.GAP),
        session_id=session_id,
    )
    if not outcome.admitted:
        _refused(session_id, seq, context, outcome)
        return

    reply = outcome.reply
    if reply.unsure:
        listed = "; ".join(label for key, label in options.items() if key != "value")
        _narrate(
            session_id, seq, context, outcome.invocation_id,
            f"I couldn't tell from that. Here are the options: {listed}. Pick one, or say it "
            "another way.",
        )
        return

    option = reply.chose if reply.chose is not None else "value"
    try:
        # **A reading is a suggestion, never an answer** (#171): the gap is pre-filled and the
        # person's click records the fact. The model call is on the turn, so the log still says
        # the reading was a model's.
        session_mod.perform(c.PrefillGap(gap["id"], option, reply.value, gathering.READ_NOTE))
    except ValueError as refused:
        _answer_blocks(
            session_id, seq, context, outcome.invocation_id,
            [Notice(id=f"notice-{seq}", notice=NoticeKind.REFUSAL, text=str(refused)[:2000],
                    code=authoring_ai._code_in(str(refused))).model_dump(mode="json")],
        )
        return

    said = options.get(option, option) if reply.value is None else str(reply.value)
    _narrate(
        session_id, seq, context, outcome.invocation_id,
        f"I read that as {said} — confirm it above, or pick another answer.",
    )


def _narrate(session_id: str, seq: int, context, invocation_id, text: str) -> None:
    _answer_blocks(
        session_id, seq, context, invocation_id,
        [Narrative(id=f"said-{seq}", text=text).model_dump(mode="json")],
    )


def _answer_blocks(session_id: str, seq: int, context, invocation_id, blocks: list) -> None:
    _answered(
        session_id, seq, blocks=blocks, base_revision=context.revision, invocation_id=invocation_id
    )


def _follow_up(session_id: str, seq: int, context) -> None:
    request = authoring_ai.compose(
        prompt=context.prompt,
        turns=context.tail,
        goal=context.goal,
        steps=context.steps,
        options=context.options,
        registry=context.registry,
    )
    outcome = authoring_ai.follow_up(
        request, client=_client(authoring_ai.Purpose.CHAT), session_id=session_id
    )
    if not outcome.admitted:
        _refused(session_id, seq, context, outcome)
        return

    intent: AuthoringIntent = outcome.reply
    # **Only where the diagram still draws the revision** (final review of 1b): the card may have
    # been accepted while the model read, and then nothing is withdrawn and nothing re-read.
    if (
        intent.revise
        and context.phase is Phase.GOAL_REVIEW
        and session_mod.allows(session_id, Command.REVISED.value)
    ):
        # A goal revision re-enters understanding with the person's corrected words, and the
        # summary they were correcting is withdrawn rather than left pending beside the new one.
        _perform(c.Revised(session_id, "person"))
        _understand(session_id, seq, context, intent.revise)
        return

    _answered(
        session_id,
        seq,
        blocks=[_block_for(seq, intent, context.phase).model_dump(mode="json")],
        base_revision=context.revision,
        invocation_id=outcome.invocation_id,
    )


def _block_for(seq: int, intent: AuthoringIntent, phase: Phase):
    """One admitted intent as the block a person reads. **Nothing here mutates the draft.**

    A chosen option or a proposed setting is *shown* — the person still presses the control that
    applies it, which is a deterministic request with a revision behind it. A model reading
    *use HISAT2* correctly is not a model applying it.
    """
    if intent.explain:
        return Narrative(id=f"reply-{seq}", text=intent.explain, refers_to=intent.refers_to)
    if intent.chose:
        return Narrative(
            id=f"reply-{seq}", text=f"You picked `{intent.chose}` — confirm it on the card."
        )
    if intent.setting is not None:
        value = intent.setting.chose or intent.setting.value
        return Narrative(
            id=f"reply-{seq}",
            text=(
                f"Proposed: `{intent.setting.setting}` on `{intent.setting.node}` = `{value}`. "
                f"{intent.setting.because}"
            ).strip()[:2000],
            refers_to=[intent.setting.node],
        )
    if intent.proceed:
        return Narrative(id=f"reply-{seq}", text="Carrying on with the next step.")
    if intent.revise:
        return Notice(
            id=f"reply-{seq}",
            notice=NoticeKind.VALIDATION,
            text=(
                "Changing the goal once the pipeline is being built is not available in this "
                f"version (the session is {phase.value}). Start a new session with the new goal."
            ),
        )
    return Notice(id=f"reply-{seq}", notice=NoticeKind.REFUSAL, text=intent.unsupported or "")


def _refused(session_id: str, seq: int, context, outcome) -> None:
    """A refusal, a missing model, or an unreachable one — as a notice, with its code."""
    code = outcome.code or "MA0004"
    first_line = (outcome.refusal or "").splitlines()[0] if outcome.refusal else code
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

