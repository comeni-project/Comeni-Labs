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
    GoalSummary,
    GoalUnderstanding,
    Mode,
    Narrative,
    Notice,
    NoticeKind,
    Option,
    Phase,
    ProposalState,
    Question,
)
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession
from mendel_api.services import authoring, authoring_ai, registry
from mendel_api.settings import model_access

log = logging.getLogger(__name__)

ANSWER = "answer_authoring_turn"
BUILD = "build_authoring_blueprint"

AI_JOBS = frozenset({ANSWER, BUILD})
"""The builder's jobs that reach a provider — `forge_jobs.AI_JOBS`, one agent over.

**Declared by the module that owns them**, and the AI worker's allowlist is held equal to the
union of every owner's set. A single list in `ai_worker.py` would let a job arrive on it without
the module that defines it ever saying it calls a model.
"""

GOAL = "goal"
"""The proposal `kind` for a goal summary awaiting confirmation."""

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

    if context.phase is Phase.UNDERSTANDING:
        _understand(session_id, seq, context, context.prompt)
    else:
        _follow_up(session_id, seq, context)
    return f"{session_id}:{seq}"


def _understand(session_id: str, seq: int, context, prompt: str) -> None:
    request = authoring_ai.compose(prompt=prompt, turns=context.tail, registry=context.registry)
    outcome = authoring_ai.understand(request, stack=registry.stack(), client=_client())

    if not outcome.admitted:
        _refused(session_id, seq, context, outcome)
        return

    understood: GoalUnderstanding = outcome.reply
    summary = GoalSummary(
        id=f"goal-{seq}",
        goal=understood.goal,
        have=understood.have,
        do=understood.do,
        get=understood.get,
    )
    blocks = [summary.model_dump(mode="json")]
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
    authoring.propose(
        session_id,
        kind=GOAL,
        payload={
            "block": summary.model_dump(mode="json"),
            "goal": understood.goal.model_dump(mode="json"),
            "options": {"accept": "accept"},
        },
    )
    authoring.move(session_id, st.Event.GOAL_RETURNED, row_version=_version(session_id))

    # **Spawn shows the goal and proceeds when it is valid; it pauses only on a question.**
    # §1.2's table. A goal with an open question — the grouping question above all — stops here
    # for a person exactly as Build does; one with none is accepted by the policy and built.
    if authoring.mode_of(session_id) is Mode.SPAWN and not understood.questions:
        pending = authoring.pending_id(session_id)
        if pending is not None:
            outcome, phase = authoring.decide_goal(
                pending, ProposalState.ACCEPTED, expected_revision=context.revision, by="model"
            )
            if outcome.refusal is None and phase is Phase.RESOLVING:
                authoring.start_building(session_id, client=_client())
                authoring.spawn_forward(session_id)


def _follow_up(session_id: str, seq: int, context) -> None:
    request = authoring_ai.compose(
        prompt=context.prompt,
        turns=context.tail,
        goal=context.goal,
        steps=context.steps,
        options=context.options,
        registry=context.registry,
    )
    outcome = authoring_ai.follow_up(request, client=_client())
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

