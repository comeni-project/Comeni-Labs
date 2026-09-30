"""The builder's AI-queue jobs: answering a turn, and resolving a Spawn blueprint.

**Only what calls a provider lives here, and only the AI worker runs it.** Accepting a step, a
goal, or a retry into Build is an ordinary request — §2: *do not put a button click behind the
slow queue*. What is queued is a model call: understanding prose, answering a follow-up, and
resolving a Spawn blueprint whose tier-4 questions a model answers.

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

from mendel_api import jobs
from mendel_api.authoring import state as st
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
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import authoring, authoring_ai, registry
from mendel_api.settings import model_access, settings

log = logging.getLogger(__name__)

ANSWER = "answer_authoring_turn"
BUILD = "build_authoring_blueprint"
PHRASE = "phrase_authoring_gap"
READ_BACK = "read_back_authoring_goal"

AI_JOBS = frozenset({ANSWER, BUILD, PHRASE, READ_BACK})
"""The builder's jobs that reach a provider — `forge_jobs.AI_JOBS`, one agent over.

**Declared by the module that owns them**, and the AI worker's allowlist is held equal to the
union of every owner's set. A single list in `ai_worker.py` would let a job arrive on it without
the module that defines it ever saying it calls a model.
"""

GOAL = authoring.GOAL
"""The proposal `kind` for a goal summary awaiting confirmation. Declared in `authoring`, which
now offers the card itself when gathering finds nothing missing."""

UNREACHABLE = frozenset({"MI0106", "MA0002", "MA0003", "MA0007"})
"""Codes meaning *no answer could be had*, as opposed to *the answer was not acceptable*.

The first set moves the session to `failed`, where `retry` is the verb; the second leaves it
where it is with a notice, because the person can simply say it differently. Folding them would
either make a missing model look like something rephrasing fixes, or make one badly-shaped answer
stop a whole session.
"""


def _client() -> Client | None:
    """The configured lane, or `None`. The one seam a test replaces to hand over a fake."""
    access = model_access()
    return Client(access) if access is not None else None


async def enqueue_turn(session_id: str, seq: int) -> bool:
    return await jobs.enqueue(
        ANSWER,
        session_id,
        seq,
        job_id=jobs.job_id_for("builder", "turn", session_id, str(seq)),
        queue=jobs.AI_QUEUE,
    )


async def enqueue_build(session_id: str, row_version: int) -> bool:
    """Keyed on the session's version, so a retry after a failure is a new job and a double
    click on one version is the same one."""
    return await jobs.enqueue(
        BUILD,
        session_id,
        job_id=jobs.job_id_for("builder", "build", session_id, str(row_version)),
        queue=jobs.AI_QUEUE,
    )


# ── answering a turn ──────────────────────────────────────────────────────────────────────


async def answer_authoring_turn(ctx: dict, session_id: str, seq: int) -> str:
    """Answer one pending assistant turn. **This is what crosses egress door 1.**"""
    context = authoring.turn_context(session_id, seq)
    if context is None:
        # Already answered, or already failed as late. A duplicate delivery must not spend a call.
        return f"{session_id}:{seq} was not pending"

    # **One handler per turn, chosen by the phase the turn was asked in** (#201). Choosing by the
    # phase afterwards ran the follow-up on a turn `_understand` had already answered with a
    # question: a second, wasted call.
    if context.phase is Phase.UNDERSTANDING:
        _understand(session_id, seq, context, context.prompt)
    elif context.phase is Phase.GATHERING and _pending_gap(session_id) is not None:
        _gap_reply(session_id, seq, context)
    else:
        _follow_up(session_id, seq, context)
    if authoring.current_phase(session_id) is Phase.GATHERING:
        # The question now on offer and the next one, phrased while the person reads (#186).
        await enqueue_phrasing(session_id)
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
            request, stack=stack, client=_client(), session_id=session_id
        )
        if not chosen.admitted:
            _refused(session_id, seq, context, chosen)
            return
        ack, families = chosen.reply.ack, list(chosen.reply.families)
        if not families:
            # **No family fits: ask, never pick the nearest.** The goal call is not made, and
            # the person's answer is read again from the top, still in `understanding`.
            _ask_which_result(
                session_id, seq, context, ack, chosen.reply.unclear, chosen.invocation_id
            )
            return

    outcome = authoring_ai.understand(
        request, stack=stack, families=families, client=_client(), session_id=session_id
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

    if not authoring.answer(
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
        return

    # **The engine takes over from here, in both modes** (14.7.3). What the want needs is
    # computed, not asked of a model, and each gap needs a person: nothing is guessed, so Spawn
    # has nothing it could fill in on their behalf (protocol rule 5).
    authoring.move(
        session_id,
        st.Event.WANT_RETURNED,
        row_version=_version(session_id),
        goal={
            "want": list(understood.want),
            # **The model's constraints are suggestions, never the goal's** (#176): the card offers
            # them and only the ones the person keeps are added.
            "constraints": {},
            "suggested": understood.constraints.model_dump(mode="json"),
            "stated": [c.model_dump(mode="json") for c in understood.stated],
        },
    )
    authoring.offer_next_gap(session_id)


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
    authoring.answer(
        session_id,
        seq,
        blocks=blocks,
        base_revision=context.revision,
        invocation_id=invocation_id,
    )


async def enqueue_phrasing(session_id: str) -> None:
    """Queue `builder.ask.v1` for the question on offer and the next one (#167, #186).

    **Keyed on the question's subject**, so a second call — another answer, a retry, a reload —
    collides at the queue instead of phrasing twice. Nothing is queued with no model configured.
    """
    for subject in authoring.to_phrase(session_id):
        await jobs.enqueue(
            PHRASE,
            session_id,
            subject,
            job_id=jobs.job_id_for("builder", "phrase", session_id, subject),
            queue=jobs.AI_QUEUE,
        )
    if authoring.wants_readback(session_id):
        # The card is on offer: its read-back, once per card (#176).
        await jobs.enqueue(
            READ_BACK,
            session_id,
            job_id=jobs.job_id_for(
                "builder", "readback", session_id, authoring.pending_id(session_id) or ""
            ),
            queue=jobs.AI_QUEUE,
        )


async def read_back_authoring_goal(ctx: dict, session_id: str) -> str:
    """Read the composed goal back to the person (#176). A failure leaves the engine's sentence."""
    if not authoring.wants_readback(session_id):
        return f"{session_id}: no card waiting for a read-back"
    outcome = authoring_ai.read_back(
        authoring_ai.compose(prompt="", registry=registry.digest()),
        goal=authoring.readback_context(session_id),
        client=_client(),
        session_id=session_id,
    )
    if outcome.admitted:
        authoring.store_readback(session_id, outcome.reply.text)
    else:
        authoring.readback_failed(session_id)
    return f"{session_id}: read back"


async def phrase_authoring_gap(ctx: dict, session_id: str, subject: str) -> str:
    """Phrase one gathering question for the person (#167). A failure leaves the engine's words."""
    gap = authoring.gap_context(session_id, subject)
    if gap is None:
        return f"{session_id}:{subject} is no longer asked"
    request = authoring_ai.compose(
        prompt=gap["first_sentence"], options=list(gap["options"]), registry=registry.digest()
    )
    outcome = authoring_ai.phrase_gap(
        request, gap=gap, stack=registry.stack(), client=_client(), session_id=session_id
    )
    if outcome.admitted:
        authoring.store_phrasing(session_id, subject, outcome.reply)
    else:
        authoring.phrasing_failed(session_id, subject)
    return f"{session_id}:{subject}"


def _pending_gap(session_id: str) -> dict | None:
    pending = authoring.read(session_id)["pending_proposal"]
    return pending if pending is not None and pending["kind"] == authoring.GAP else None


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
        client=_client(),
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
        authoring.prefill_gap(gap["id"], option, reply.value, note=authoring.READ_NOTE)
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
    authoring.answer(
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
    outcome = authoring_ai.follow_up(request, client=_client(), session_id=session_id)
    if not outcome.admitted:
        _refused(session_id, seq, context, outcome)
        return

    intent: AuthoringIntent = outcome.reply
    if intent.revise and context.phase is Phase.GOAL_REVIEW:
        # A goal revision re-enters understanding with the person's corrected words, and the
        # summary they were correcting is withdrawn rather than left pending beside the new one.
        authoring.withdraw_pending(session_id, by="person")
        authoring.move(session_id, st.Event.GOAL_REVISED, row_version=_version(session_id))
        _understand(session_id, seq, context, intent.revise)
        return

    authoring.answer(
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
    authoring.answer(
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
        phase = authoring.current_phase(session_id)
        if (phase, st.Event.PROVIDER_FAILED) in st.TRANSITIONS:
            authoring.move(session_id, st.Event.PROVIDER_FAILED, row_version=_version(session_id))


def _version(session_id: str) -> int:
    with session_scope() as db:
        return db.get(PipelineAuthoringSession, session_id).row_version


# ── a Spawn blueprint ─────────────────────────────────────────────────────────────────────


async def build_authoring_blueprint(ctx: dict, session_id: str) -> str:
    """Resolve a Spawn session's blueprint, with its tier-4 questions put to the model.

    Queued rather than run in the request because a model call can take minutes; a Build
    blueprint makes no call and is resolved inline by the route instead. A resolver failure
    moves the session to `failed` inside `start_building`, where `retry` picks it up.
    """
    try:
        authoring.start_building(session_id, client=_client())
        authoring.spawn_forward(session_id)
    except ValueError as refused:
        log.warning("blueprint for %s refused: %s", session_id, str(refused).splitlines()[0])
    return session_id

