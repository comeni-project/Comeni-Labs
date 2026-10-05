"""Authoring sessions, turns and proposals, made durable.

**The rules live in `authoring/state.py`; this file holds rows.** Every phase change goes through
`state.advance` and every settlement through `state.settle`, so the diagram in the plan's §2 is
enforced in one place rather than re-derived by each verb here. That is `forge_state.py`'s split
and it earns its keep the same way: the second caller is where a remembered `if` fails.

**Two things are compared on every mutating write**, and they catch different mistakes:

- `expected_revision` against `pipeline_draft.revision` — the client acted on a picture of the
  draft, and the picture is stale. This is the two-tab case, which §2 calls ordinary.
- `row_version` on the session — the *session* moved, even if the draft did not. A model answer
  landing after the person revised their goal is this one, and only this one.

Neither is a timestamp, for the reason `state.settle` records: two writes inside one clock tick
are indistinguishable by time, which is precisely when the comparison matters.

**Nothing here composes a prompt.** `services/authoring_ai.py` owns prompts and admission, and
`services/blueprint.py` owns resolving and committing a step. The one path from this file that
can reach a provider is `start_building` in Spawn mode, and only through a `Client` its caller
passes — so every test here runs against a database and, unless it hands one over, no model.
"""

import logging

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftProvenance
from mendel_authoring import commands as c
from mendel_authoring import state as st
from sqlalchemy import select, update

from mendel_api.authoring.types import (
    FactSource,
    Mode,
    Phase,
)
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringSession,
    PipelineDraft,
)
from mendel_api.services import session as session_mod
from mendel_api.services import spawn
from mendel_api.stages import building, describe, gathering, goal, samples
from mendel_api.stages._rows import (  # noqa: F401 — the old names, until Task 10 (plan 1c)
    GAP,
    GOAL,
    STEP,
    decide,
    propose,
    store_goal,
)
from mendel_api.stages._rows import now as _now

log = logging.getLogger(__name__)


# ── forwarding, until the tests call the facade (ruling 9 of plan 1c; gone in Task 10) ─────


def open_session(draft_id: str, *, mode: Mode, who: str) -> str:
    return session_mod.perform(c.OpenSession(draft_id, mode.value, who)).result


def begin(prompt: str, *, mode: Mode, who: str) -> tuple[str, int]:
    return session_mod.perform(c.Begin(prompt, mode.value, who)).result


def say(session_id: str, text: str) -> int:
    return session_mod.perform(c.Say(session_id, text)).result


def answer(session_id, seq, *, blocks, base_revision, invocation_id=None) -> bool:
    return session_mod.perform(
        c.AnswerTurn(session_id, seq, blocks, base_revision, invocation_id)
    ).result


def retry(session_id: str) -> tuple[Phase, int | None]:
    return session_mod.perform(c.Retry(session_id)).result


read, calls = session_mod.read, session_mod.calls
current_phase, pending_id = session_mod.current_phase, session_mod.pending_id
turn_context, TurnContext = describe.turn_context, describe.TurnContext
UNTITLED = describe.UNTITLED


def answer_gap(proposal_id: str, option: str, value, *, by: str) -> Phase:
    return session_mod.perform(c.AnswerGap(proposal_id, option, value, by)).result


def prefill_gap(proposal_id: str, option: str, value, *, note: str) -> None:
    session_mod.perform(c.PrefillGap(proposal_id, option, value, note))


def store_phrasing(session_id: str, subject: str, asked) -> None:
    session_mod.perform(c.StorePhrasing(session_id, subject, asked.model_dump(mode="json")))


def phrasing_failed(session_id: str, subject: str) -> None:
    session_mod.perform(c.PhrasingFailed(session_id, subject))


def offer_next_gap(session_id: str) -> str | None:
    ran = session_mod.perform(c.Resume(session_id)).result
    return session_mod.pending_id(session_id) if ran.at in {"reply", "card"} else None


UPLOAD, STATED_NOTE, READ_NOTE = gathering.UPLOAD, gathering.STATED_NOTE, gathering.READ_NOTE
ALREADY_NOTE, UNREACHABLE_ASK = gathering.ALREADY_NOTE, gathering.UNREACHABLE_ASK
compose_goal, as_goal, to_phrase = gathering.compose_goal, gathering.as_goal, gathering.to_phrase
gap_context, need_listed = gathering.gap_context, gathering.need_listed
offer_gap_or_card = gathering.offer_gap_or_card
_characterisable, _gathered = gathering._characterisable, gathering._gathered
_gap_options, _inspectable = gathering._gap_options, gathering._inspectable


def decide_goal(proposal_id, decision, *, expected_revision, by, edited=None):
    return session_mod.perform(
        c.DecideGoal(
            proposal_id,
            decision.value,
            expected_revision,
            by,
            None if edited is None else edited.model_dump(mode="json"),
        )
    ).result


withdraw_pending = goal.withdraw_pending
store_readback, readback_failed = goal.store_readback, goal.readback_failed
wants_readback, readback_context = goal.wants_readback, goal.readback_context


def answer_with_sample(proposal_id: str, inspection, *, by: str):
    return session_mod.perform(
        c.SampleInspected(proposal_id, inspection.model_dump(mode="json"), by)
    ).result


def answer_with_reading(proposal_id, attempt, reply, *, by, handed_back):
    return session_mod.perform(
        c.ReadingAnswered(proposal_id, attempt, reply.model_dump(mode="json"), by, handed_back)
    ).result


def reading_failed(proposal_id, attempt, state, code) -> None:
    session_mod.perform(c.ReadingFailed(proposal_id, attempt, state, code))


reading_of, start_reading = samples.reading_of, samples.start_reading
check_sample_question, end_hand_back = samples.check_sample_question, samples.end_hand_back
reading_open, STALE_AFTER = samples.reading_open, samples.STALE_AFTER
SampleAnswer = samples.SampleAnswer
_reading, _aged, _set_reading = samples._reading, samples._aged, samples._set_reading


def start_building(session_id: str, *, client=None) -> str | None:
    if client is not None:
        return spawn.start(session_id, client=client)
    return session_mod.perform(c.StartBuilding(session_id)).result


def settle_step(
    proposal_id, decision, *, expected_revision, by, chosen_option=None, client=None
):
    return session_mod.perform(
        c.SettleStep(proposal_id, decision.value, expected_revision, by, chosen_option)
    ).result


def record_edit(session_id, graph, *, by):
    return session_mod.perform(
        c.RecordEdit(session_id, graph.model_dump(mode="json"), by)
    ).result


spawn_forward, SpawnStop, mode_of = spawn.spawn_forward, spawn.SpawnStop, spawn.mode_of
SPAWN_STOP = spawn.SPAWN_STOP
StepOutcome, ResolverFailed = building.StepOutcome, building.ResolverFailed
pending_step_tier = building.pending_step_tier
build_blueprint, describe_edit = building.resolve_blueprint, building.describe_edit
_placement = building._placement


def move(session_id: str, event: st.Event, *, row_version: int, **values: object) -> Phase:
    """One phase change, compare-and-swap on the session's own version.

    **Setup for tests only** (ruling 5 of 14.7.8.1b): nothing under `src/` calls it, which
    `test_authoring_binding.py` holds. It clears `at`, so the node is derived from the phase it
    sets (`session.rests_at`).

    `state.advance` decides *whether* and `UPDATE … WHERE row_version` decides *whether it is
    still ours*. Both are needed and they catch different mistakes — the first an illegal move,
    the second a legal move applied to a session somebody else already moved.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)

        current = Phase(row.phase)
        came_from = Phase(row.failed_from) if row.failed_from else None
        target = st.advance(current, event, came_from)

        # Cleared on every move that is not *into* failure, so a retried session does not carry
        # the phase of a failure it has already recovered from — `forge_state.move` clears
        # `failed_stage` for exactly this reason, and a stale one sends the next retry wrong.
        failed = st.failed_from(current).value if target is Phase.FAILED else None

        done = db.execute(
            update(PipelineAuthoringSession)
            .where(
                PipelineAuthoringSession.id == session_id,
                PipelineAuthoringSession.row_version == row_version,
            )
            .values(
                phase=target.value,
                failed_from=failed,
                at=None,
                row_version=row_version + 1,
                updated_at=_now(),
                **values,
            )
        )
        if done.rowcount != 1:
            raise ValueError(
                coded("MI0201", "this session moved while you were looking at it")
                + f"\n  you held version {row_version}; it is at {row.row_version}"
                + "\n  re-read it before acting on it"
            )
    return target


# ── the blueprint: resolved once, revealed a step at a time ───────────────────────────────


# ── the transport's verbs: starting, grounding a turn, goals, retrying ────────────────────


# ── Spawn: the same proposals, accepted by policy where that is safe ──────────────────────


def ai_for(provenance: DraftProvenance, *, characterised: bool = False):
    """What AI points this installation offers, and which this draft used. For `pipeline.yml`.

    **One function for the preview and for Keep**, so the two cannot disagree about the `ai`
    block — which would make the preview and the kept file differ for a reason nobody edited.
    `available` follows the installation, never the mode (Task 12); `used` is read from the
    sidecar, because it answers which points this draft actually exercised.
    """
    from comeni_core.artifact.pipeline import AiPoint, AiProvenance
    from comeni_core.plan.tiers import ValueSource

    from mendel_api.settings import model_access

    if model_access() is None:
        return AiProvenance(available=[], used=[])
    modelled = any(
        entry.selection is not None and entry.selection.source is ValueSource.MODEL
        for entry in provenance.nodes
    ) or any(entry.settled.source is ValueSource.MODEL for entry in provenance.params)
    # The characteriser (14.7.7): available where a model may read a sample here; used when a
    # fact the session gathered was read by it (`characterised`, from the session's facts).
    reads = _characterisable()
    return AiProvenance(
        available=[AiPoint.PROMPT, AiPoint.TIER_4] + ([AiPoint.CHARACTERISE] if reads else []),
        used=[AiPoint.PROMPT]
        + ([AiPoint.TIER_4] if modelled else [])
        + ([AiPoint.CHARACTERISE] if reads and characterised else []),
    )


def characterised(facts: list[dict] | None) -> bool:
    """Whether any fact a session gathered was read by the AI (14.7.7)."""
    return any(f.get("source") == FactSource.MODEL_READ.value for f in facts or [])


def ai_for_draft(draft_id: str):
    """`ai_for` for a draft an authoring session owns, or `None` for a hand-drawn one."""
    with session_scope() as db:
        owned = db.scalar(
            select(PipelineAuthoringSession).where(
                PipelineAuthoringSession.draft_id == draft_id
            )
        )
        if owned is None:
            return None
        draft = db.get(PipelineDraft, draft_id)
        return ai_for(
            DraftProvenance.model_validate(draft.provenance or {}),
            characterised=characterised(owned.facts),
        )


# ── gathering: the engine asks for what the want needs (14.7.3) ──────────────────────────


# ── the AI reading a sample (14.7.7) ─────────────────────────────────────────────────────────

