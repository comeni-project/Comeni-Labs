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

import contextlib
import logging
from datetime import datetime
from typing import NamedTuple

from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph, DraftProvenance
from mendel_authoring import commands as c
from mendel_authoring import state as st
from mendel_authoring.interpret import Refused
from mendel_authoring.types import Command
from mendel_resolver.goal import Goal
from mendel_resolver.router import UnroutableError
from sqlalchemy import select, update

from mendel_api.authoring.types import (
    Fact,
    FactKind,
    FactSource,
    Mode,
    Phase,
    ProposalState,
    SampleReading,
    TurnState,
)
from mendel_api.db import session_scope
from mendel_api.models import (
    PipelineAuthoringProposal,
    PipelineAuthoringSession,
    PipelineAuthoringTurn,
    PipelineDraft,
)
from mendel_api.services import authoring_ai, registry
from mendel_api.services import blueprint as bp
from mendel_api.services import session as session_mod
from mendel_api.settings import settings
from mendel_api.stages import describe, gathering, goal
from mendel_api.stages._rows import (  # noqa: F401 — the old names, until Task 10 (plan 1c)
    GAP,
    GOAL,
    STEP,
    decide,
    propose,
    store_goal,
)
from mendel_api.stages._rows import new_id as _id
from mendel_api.stages._rows import next_seq as _next_seq
from mendel_api.stages._rows import note as _note
from mendel_api.stages._rows import now as _now
from mendel_api.stages._rows import swap as _swap

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


class StepOutcome(NamedTuple):
    """What answering a step proposal did, and what is waiting now.

    §2: *return the new revision and next proposal* — both, from the one transaction that made
    them true, so a browser never has to re-read to learn what it just caused.
    """

    settlement: st.Settlement
    revision: int
    next_proposal: str | None
    phase: Phase


class ResolverFailed(Exception):
    """The resolver raised: `resolve` takes the `cant_build` arrow, then raises the cause."""


def pending_step_tier(session_id: str) -> int | None:
    """The pending step's tier, which card it is (`offer`, 14.7.8.1), or `None` at the end."""
    with session_scope() as db:
        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
                PipelineAuthoringProposal.kind == STEP,
            )
        )
        return None if pending is None else int(pending.payload["block"]["tier"])


def start_building(session_id: str, *, client=None) -> str | None:
    """Resolve the whole blueprint, store it, and offer its first step, by resuming the session
    at `resolve` (14.7.8.1). Returns the first proposal's id, or `None` for an empty blueprint
    (or one that could not be built: the session is then `failed`)."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        if session_mod.rests_at(db, row) != "resolve":
            # Resuming anywhere else would rest there quietly: a build asked for from the wrong
            # place is refused by name, as it always was.
            raise ValueError(
                coded("MI0200", f"there is nothing to build from {row.phase}")
                + "\n  a blueprint is resolved only once a goal is confirmed"
            )
    session_mod.resume(session_id, client=client)
    return pending_id(session_id)


def build_blueprint(session_id: str, *, client=None) -> str:
    """`resolve`'s work: the blueprint resolved, stored, and its first step offered (`stored`),
    or the goal found unbuildable (`cant_build`). Any other failure is raised.

    **The resolve happens outside any transaction**, because it can take most of a second and in
    Spawn may reach a provider — and a row lock held across a model call is a lock held for as
    long as a provider feels like. The session's `row_version` is read first and compared when
    the blueprint is written, so a session that moved while the resolver ran is refused rather
    than overwritten.
    """
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        if row.goal is None:
            raise ValueError(
                coded("MI0200", "this session has no confirmed goal to build from")
                + "\n  accept a goal first; a blueprint resolved from nothing is not a pipeline"
            )
        goal = Goal.model_validate(row.goal)
        mode = Mode(row.mode)
        version = row.row_version

    try:
        blueprint, calls = bp.resolve(goal, mode=mode, client=client)
    except UnroutableError as unroutable:
        # **A fact about the goal, so it goes in the conversation** (#115). Raised, it reached a
        # person as a toast and nowhere else, and a reload lost the reason entirely.
        _note(session_id, _unbuildable(unroutable), code="MI0207")
        return "cant_build"
    except Exception as failure:
        # **The resolver's own failure, whatever its type** (final review of 1b):
        # `NoCandidatesError` and the rule errors are `ValueError`s, and are not a refusal of
        # the request. `resolve` lands the session on `failed`, then raises it.
        log.exception("resolving the blueprint for %s failed", session_id)
        raise ResolverFailed(failure) from failure
    if calls and client is not None:
        authoring_ai.record_calls(
            calls, client=client, registry=blueprint.registry, session_id=session_id
        )

    contracts = registry.stack().registry
    with session_scope() as db:
        _swap(
            db,
            session_id,
            version,
            blueprint=blueprint.model_dump(mode="json"),
            registry_digest=blueprint.registry,
            cursor=0,
        )
        session_row = db.get(PipelineAuthoringSession, session_id)
        draft = db.get(PipelineDraft, session_row.draft_id)
        draft.goal = goal.model_dump(mode="json")
        if not DraftGraph.model_validate(draft.graph).nodes:
            # The measured profile rides on the graph, because `ir_of` builds its premises from
            # it — without it a tier-3 step re-materialises with nothing to have matched on.
            draft.graph = DraftGraph(profile=goal.profile).model_dump(mode="json")

        first = blueprint.after(None)
        if first is not None:
            _offer(db, session_id, blueprint, first, revision=draft.revision, registry=contracts)
        return "stored"


def settle_step(
    proposal_id: str,
    decision: ProposalState,
    *,
    expected_revision: int,
    by: str,
    chosen_option: str | None = None,
    client=None,
) -> StepOutcome:
    """Accept or reject one step, commit it, and offer the next — or say why not.

    **One transaction from the check to the next proposal.** The draft's graph, its provenance
    sidecar, its revision, the proposal's outcome, the session's cursor and the next proposal are
    written together or not at all; a draft revision that moved without the proposal recording
    it, or the reverse, is two accounts of one click.

    **The registry is compared before anything else.** If a layer moved since the blueprint was
    resolved, the proposal is marked `stale` and the blueprint is resolved again — `MI0206` — and
    nothing about the draft changes. An option chosen against a registry that no longer supplies
    it is not a choice anybody made.
    """
    contracts = registry.stack().registry
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        session_row = db.get(PipelineAuthoringSession, proposal.session_id)
        draft = db.get(PipelineDraft, session_row.draft_id)
        blueprint = bp.Blueprint.model_validate(session_row.blueprint)
        node = proposal.payload["node"]
        phase = Phase(session_row.phase)

        moved = (
            proposal.state == ProposalState.PENDING.value
            and bp.registry_digest([settings.registry_root]) != session_row.registry_digest
        )
        if moved:
            proposal.state = ProposalState.STALE.value
            proposal.settled_at = _now()
            # Plain values, not ORM attributes: everything below runs after this transaction has
            # closed, and reading a detached row's attribute there is a refresh with no session.
            session_id = session_row.id
            was = session_row.registry_digest
            goal = Goal.model_validate(session_row.goal)
            mode = Mode(session_row.mode)
            version = session_row.row_version
            revision = draft.revision
            accepted = {n.id for n in DraftGraph.model_validate(draft.graph).nodes}
        else:
            outcome = st.settle(
                current=ProposalState(proposal.state),
                proposal_revision=proposal.draft_revision,
                draft_revision=draft.revision,
                expected_revision=expected_revision,
                decision=decision,
            )
            if not outcome.applies:
                if outcome.state is not ProposalState(proposal.state):
                    proposal.state = outcome.state.value
                    proposal.settled_at = _now()
                return StepOutcome(outcome, draft.revision, None, phase)

            options: dict[str, str] = proposal.payload["options"]
            option = chosen_option or bp.KEEP
            session_mod.check(session_row.id, Command.SETTLE_STEP.value)
            if decision is ProposalState.ACCEPTED:
                if option not in options:
                    return StepOutcome(
                        st.Settlement(
                            ProposalState(proposal.state),
                            False,
                            coded("MI0205", "that option was never offered for this step")
                            + f"\n  offered: {', '.join(sorted(options))}",
                            False,
                        ),
                        draft.revision,
                        None,
                        phase,
                    )
                graph, provenance = bp.committed(
                    blueprint,
                    DraftGraph.model_validate(draft.graph),
                    DraftProvenance.model_validate(draft.provenance or {}),
                    node,
                    contract_id=options[option],
                    by=by,
                    registry=contracts,
                )
                draft.graph = graph.model_dump(mode="json")
                draft.provenance = provenance.model_dump(mode="json")
                draft.revision = draft.revision + 1
                draft.updated_at = _now()
                proposal.chosen_option = option

            proposal.state = outcome.state.value
            proposal.by = by
            proposal.settled_at = _now()
            db.flush()

            following = blueprint.after(node)
            _swap(db, session_row.id, session_row.row_version, cursor=session_row.cursor + 1)
            offered = (
                _offer(db, session_row.id, blueprint, following, revision=draft.revision,
                       registry=contracts)
                if following
                else None
            )
            settled_in, revision_now = session_row.id, draft.revision

    if not moved:
        # The next step was offered inside the transaction (`_offer`), so `offer` finds it.
        session_mod.perform_now(settled_in, Command.SETTLE_STEP.value)
        return StepOutcome(outcome, revision_now, offered, current_phase(settled_in))

    # The registry moved. Resolve again outside the transaction, for `start_building`'s reason.
    fresh, calls = bp.resolve(goal, mode=mode, client=client)
    if calls and client is not None:
        authoring_ai.record_calls(
            calls, client=client, registry=fresh.registry, session_id=session_id
        )
    with session_scope() as db:
        _swap(
            db,
            session_id,
            version,
            blueprint=fresh.model_dump(mode="json"),
            registry_digest=fresh.registry,
        )
        again = node if node in fresh.order else next(
            (step for step in fresh.order if step not in accepted), None
        )
        offered = (
            _offer(db, session_id, fresh, again, revision=revision, registry=contracts)
            if again
            else None
        )
    refusal = (
        coded("MI0206", "the registry changed after this step was proposed")
        + f"\n  it was resolved against {was}; it is {fresh.registry}"
        + "\n  nothing was applied — the blueprint was resolved again, and a fresh proposal waits"
    )
    return StepOutcome(
        st.Settlement(ProposalState.STALE, False, refusal, False), revision, offered, Phase.BUILDING
    )


def _unbuildable(unroutable: UnroutableError) -> str:
    """MI0207's line, naming what is missing when the resolver said — never its raw message,
    which spells an empty state set as Python's `[]`."""
    if unroutable.missing is None:
        return coded("MI0207", "the confirmed goal cannot be built from what it says you have")
    type_id, states = unroutable.missing
    spelled = f"{type_id}[{', '.join(sorted(states))}]" if states else type_id
    return coded(
        "MI0207",
        f"this goal needs {spelled}, and nothing can make it from what you have — "
        "start again and say that you have one",
    )


def _offer(db, session_id: str, blueprint, node_id: str, *, revision: int, registry) -> str:
    """Store one step proposal as `pending`, against the draft as it stands now."""
    proposal_id = _id()
    session_row = db.get(PipelineAuthoringSession, session_id)
    draft = db.get(PipelineDraft, session_row.draft_id)
    present = frozenset(node.id for node in DraftGraph.model_validate(draft.graph).nodes)
    db.add(
        PipelineAuthoringProposal(
            id=proposal_id,
            session_id=session_id,
            turn_id=None,
            kind=STEP,
            payload=bp.proposal(blueprint, node_id, registry=registry, present=present),
            state=ProposalState.PENDING.value,
            chosen_option=None,
            by=None,
            draft_revision=revision,
            created_at=_now(),
            settled_at=None,
        )
    )
    db.flush()
    return proposal_id


# ── the transport's verbs: starting, grounding a turn, goals, retrying ────────────────────


def _placement(row: PipelineAuthoringSession, draft: PipelineDraft | None, pending) -> dict:
    """Blueprint positions for the steps a person can see — accepted ones and the one on offer.

    **Only those.** The blueprint is the whole pipeline and it is private until revealed; handing
    the browser a coordinate for a step nobody has been shown yet would put the plan on the page
    as a set of empty slots. A step added by hand has no blueprint position and is simply absent
    here, for the canvas to place as it places any hand-drawn node.
    """
    placed = (row.blueprint or {}).get("placed") or {}
    visible = {n["id"] for n in (draft.graph or {}).get("nodes", [])} if draft else set()
    if pending is not None and pending.kind == STEP:
        visible.add(pending.payload.get("node"))
    return {node: {"x": at[0], "y": at[1]} for node, at in placed.items() if node in visible}


def record_edit(session_id: str, graph: DraftGraph, *, by: str) -> tuple[int, str | None]:
    """A direct edit to the session's draft, recorded in the transcript. Returns the new revision
    and the id of a re-offered proposal, if one was pending.

    **The receipt is composed here, from the difference, never sent by the browser.** A receipt is
    a fact the client already knew restated so the log stays complete — and a fact the server can
    derive is one a client cannot misstate. No model is called to narrate it.

    **An edit moves the revision**, because it changes the draft: a proposal offered against the
    old picture would otherwise apply to a pipeline that no longer looks that way. So a pending
    step proposal is marked stale and offered again at the new revision, in the same transaction —
    the session never ends up with nothing to answer because somebody moved a box.
    """
    from mendel_api.services import drafts

    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        draft = db.get(PipelineDraft, row.draft_id)
        before = DraftGraph.model_validate(draft.graph)
        prior = DraftProvenance.model_validate(draft.provenance or {})
        summary = describe_edit(before, graph)
        if summary is None:
            return draft.revision, None

        draft.graph = graph.model_dump(mode="json")
        draft.provenance = drafts._restamped(graph, before, prior).model_dump(mode="json")
        draft.revision = draft.revision + 1
        draft.updated_at = _now()

        seq = _next_seq(db, session_id)
        db.add(
            PipelineAuthoringTurn(
                session_id=session_id,
                seq=seq,
                role="assistant",
                state=TurnState.ANSWERED.value,
                blocks=[
                    {
                        "kind": "receipt",
                        "id": f"receipt-{seq}",
                        "summary": summary,
                        "revision": draft.revision,
                        "by": "person",
                    }
                ],
                text="",
                base_revision=draft.revision,
                at=_now(),
            )
        )

        pending = db.scalar(
            select(PipelineAuthoringProposal).where(
                PipelineAuthoringProposal.session_id == session_id,
                PipelineAuthoringProposal.state == ProposalState.PENDING.value,
            )
        )
        reoffered = None
        if pending is not None and pending.kind == STEP and row.blueprint:
            pending.state = ProposalState.STALE.value
            pending.settled_at = _now()
            db.flush()
            blueprint = bp.Blueprint.model_validate(row.blueprint)
            present = {n.id for n in graph.nodes}
            # The same step again — unless the person just put it there by hand, in which case the
            # next step the draft does not already hold. Never nothing: a session with no pending
            # proposal and steps left is a session nobody can move forward.
            node = pending.payload["node"]
            while node is not None and node in present:
                node = blueprint.after(node)
            if node is not None:
                reoffered = _offer(
                    db,
                    session_id,
                    blueprint,
                    node,
                    revision=draft.revision,
                    registry=registry.stack().registry,
                )
        return draft.revision, reoffered


def describe_edit(before: DraftGraph, after: DraftGraph) -> str | None:
    """One line saying what a direct edit did, or `None` when it did nothing.

    Named in the log's own vocabulary — step ids, upper-cased as the canvas draws them — and only
    what changed. A position move is not a change: `DraftGraph` has no coordinates.
    """
    was = {n.id: n for n in before.nodes}
    now = {n.id: n for n in after.nodes}
    parts: list[str] = []
    parts += [f"added {i.upper()}" for i in sorted(now.keys() - was.keys())]
    parts += [f"removed {i.upper()}" for i in sorted(was.keys() - now.keys())]
    for i in sorted(now.keys() & was.keys()):
        if now[i].contract_id != was[i].contract_id:
            parts.append(f"swapped {i.upper()} for {now[i].contract_id}")
        old = {p.name: p.value for p in was[i].params}
        for param in now[i].params:
            if old.get(param.name) != param.value:
                parts.append(f"set {i.upper()}.{param.name} to {param.value}")
        for name in sorted(old.keys() - {p.name for p in now[i].params}):
            parts.append(f"cleared {i.upper()}.{name}")
    edges = lambda g: {(e.from_node, e.from_port, e.to_node, e.to_port) for e in g.edges}  # noqa: E731
    if edges(before) != edges(after):
        parts.append("rewired the canvas")
    return ("you " + ", ".join(parts)) if parts else None


# ── Spawn: the same proposals, accepted by policy where that is safe ──────────────────────


SPAWN_STOP = frozenset({"MI0201", "MI0202", "MI0203", "MI0206"})
"""Refusals that end an automatic run with the proposal left for a person."""


class SpawnStop(NamedTuple):
    """Why an automatic run stopped, or `None` for a pipeline that completed."""

    node: str | None
    reason: str | None


def spawn_forward(session_id: str, *, limit: int = 200) -> SpawnStop:
    """Accept every step Spawn may accept, in order, until one needs a person or none is left.

    **The same `settle_step` Build uses, one proposal at a time** — an idempotent sequence rather
    than a second commit path, so a Spawn pipeline and a Build pipeline are made by the same code
    and every proposal stays in history, answered, with its author. §1.2's two policies over one
    engine is this function being a loop and nothing else.

    **What Spawn accepts:** a step the resolver settled at tiers 1 to 3, and a tier-4 step a model
    chose from its candidates (`source: model`). **Where it stops**, leaving the proposal pending
    for exactly the card Build would show: a tier-4 step the flag settled — no model, a refusal, or
    no candidate the model could take — an illegal graph after the step, and any refusal from the
    commit itself, including a registry that moved.

    The acceptance is recorded against the author the policy relied on — `resolver` or `model` —
    never against *spawn*: the policy decided nothing, it only declined to ask.
    """
    from mendel_api.services import validate as validation

    for _ in range(limit):
        with session_scope() as db:
            row = db.get(PipelineAuthoringSession, session_id)
            if row is None:
                raise KeyError(session_id)
            if Mode(row.mode) is not Mode.SPAWN or Phase(row.phase) is not Phase.BUILDING:
                return SpawnStop(None, None)
            pending = db.scalar(
                select(PipelineAuthoringProposal).where(
                    PipelineAuthoringProposal.session_id == session_id,
                    PipelineAuthoringProposal.state == ProposalState.PENDING.value,
                )
            )
            if pending is None or pending.kind != STEP:
                return SpawnStop(None, None)
            blueprint = bp.Blueprint.model_validate(row.blueprint)
            draft = db.get(PipelineDraft, row.draft_id)
            node = pending.payload["node"]
            step = blueprint.step(node)
            proposal_id = pending.id
            revision = draft.revision
            present = DraftGraph.model_validate(draft.graph)

        from comeni_core.plan.tiers import Tier, ValueSource

        if step.why.tier is Tier.AMBIGUOUS and step.why.source is not ValueSource.MODEL:
            return SpawnStop(node, "a choice no rule settled and no model made")

        after = present.model_copy(
            update={
                "nodes": [
                    *present.nodes,
                    {"id": node, "contract_id": step.module.contract_id, "params": []},
                ]
            }
        )
        if validation.of(DraftGraph.model_validate(after.model_dump())).illegal:
            return SpawnStop(node, "the pipeline would not be legal with this step")

        author = "model" if step.why.source is ValueSource.MODEL else "resolver"
        outcome = settle_step(
            proposal_id, ProposalState.ACCEPTED, expected_revision=revision, by=author
        )
        if outcome.settlement.refusal is not None:
            code = outcome.settlement.refusal.split(":", 1)[0]
            return SpawnStop(node, code if code in SPAWN_STOP else outcome.settlement.refusal)
        if outcome.next_proposal is None:
            return SpawnStop(None, None)
    return SpawnStop(None, "stopped after the step limit")


def mode_of(session_id: str) -> Mode:
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id)
        if row is None:
            raise KeyError(session_id)
        return Mode(row.mode)


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


class SampleAnswer(NamedTuple):
    """What one inspected sample settled, for the card."""

    phase: Phase
    recorded: list[str]
    """Subjects recorded from the sample, as measured."""
    kept: list[str]
    """Subjects the session already knew: what was said stands."""
    disagreed: list[str]
    """Of `kept`, those the sample measured differently. Shown, never written over."""


def _counts(evidence: dict) -> dict[str, int | float]:
    """Numbers only: a file name (`shorter_file`) never enters a fact (spec §9)."""
    return {
        k: v for k, v in evidence.items() if isinstance(v, int | float) and not isinstance(v, bool)
    }


def _sample_refusal(proposal) -> str | None:
    """Why this proposal cannot take a sample now, or `None` (MI0205, then MI0203)."""
    if proposal.kind != GAP or UPLOAD not in proposal.payload["options"]:
        return coded("MI0205", "that question does not take a sample")
    reading = _reading((proposal.payload or {}).get("block") or {}) or {}
    if reading.get("state") == "pending":
        return coded("MI0215", "a sample is already being read for this question")
    return st.settle(
        current=ProposalState(proposal.state),
        proposal_revision=proposal.draft_revision,
        draft_revision=proposal.draft_revision,
        expected_revision=proposal.draft_revision,
        decision=ProposalState.ACCEPTED,
    ).refusal


def check_sample_question(proposal_id: str) -> None:
    """Refuse a sample before it is inspected: a settled gap, or one that takes no sample, is
    told so without its bytes being read (issue 226). `answer_with_sample` asks again, under
    the row's lock, since a second tab may settle it in between."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        refusal = _sample_refusal(proposal)
    if refusal is not None:
        raise ValueError(refusal)


class _Found(NamedTuple):
    """One measurement a sample settled, from an inspector or from a model."""

    measurement: str
    value: object
    pieces: list[str] = []
    evidence: dict | None = None


def _record_found(
    db, proposal, row, *, type_id: str | None, states: list[str], found: list[_Found],
    source: FactSource, by: str, stack,
) -> tuple[list[str], list[str], list[str], bool]:
    """Record a sample's type and facts as `source`, the person's word standing; settle the
    proposal when its subject was recorded. Returns `(recorded, kept, disagreed, answered)`.

    **An open fact is not known**: *can't share* or *not sure* is nobody's value, and the
    person's own sample settling it is recorded in its place, never reported as disagreeing
    with a value nobody gave (review of #134).
    """
    session_id = proposal.session_id
    subject = proposal.payload["subject"]
    decided = {f.measurement for f in found if f.value is not None}
    facts = [
        f
        for f in row.facts or []
        if not (f.get("source") == FactSource.OPEN.value and f["subject"] in decided)
    ]
    known = {f["subject"]: f for f in facts}
    recorded, kept, disagreed = [], [], []
    if type_id:
        if type_id in known:
            kept.append(type_id)
        else:
            facts.append(
                Fact(kind=FactKind.INPUT, subject=type_id, states=sorted(states), source=source)
                .model_dump(mode="json")
            )
            recorded.append(type_id)
    for item in found:
        if item.value is None:
            continue
        try:
            stack.measurements.check(item.measurement, item.value)
        except (ValueError, KeyError):
            continue
        if item.measurement in known:
            kept.append(item.measurement)
            if known[item.measurement].get("value") != item.value:
                disagreed.append(item.measurement)
            continue
        facts.append(
            Fact(
                kind=FactKind.MEASUREMENT,
                subject=item.measurement,
                value=item.value,
                source=source,
                pieces=item.pieces,
                evidence=_counts(item.evidence or {}) or None,
            ).model_dump(mode="json")
        )
        recorded.append(item.measurement)
    answered = subject in recorded
    if answered:
        proposal.state = ProposalState.ACCEPTED.value
        proposal.by = by
        proposal.chosen_option = UPLOAD
        proposal.settled_at = _now()
    # A sample that changed nothing leaves the session's version alone, so a click the person
    # made meanwhile is not refused as stale (issue 226).
    if answered or facts != (row.facts or []):
        _swap(db, session_id, row.row_version, facts=facts)
    return recorded, kept, disagreed, answered


def _pin_proposals_session(proposal_id: str) -> None:
    """Pin the node of the session a sample answers before it records (`session.pin`)."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        session_id = proposal.session_id if proposal is not None else None
    if session_id is not None:
        session_mod.pin(session_id)


def _sample_moves(session_id: str, answered: bool) -> None:
    """A sample's way out of section ②a (14.7.8.1): on to the next question when it answered
    this one, or staying on it. **The session moved on meanwhile** (spec §8): what it measured
    stands, and nothing moves."""
    with contextlib.suppress(Refused):
        session_mod.perform_now(session_id, Command.UPLOAD_SAMPLE.value, answered=answered)


def answer_with_sample(proposal_id: str, inspection, *, by: str) -> SampleAnswer:
    """What one inspected sample settles, recorded the way a click records an answer.

    **The person's word stands.** A measurement the session already knows is not overwritten; a
    disagreement is reported back. **An undetermined fact is not recorded**, so if it was the gap
    being answered, the gap stays open with its reason on the card. The proposal is settled only
    when the inspection decided its subject (or, for an input gap, read the type). A gap already
    settled refuses the sample before anything is recorded (MI0203), as a duplicate click does.
    """
    stack = registry.stack()
    _pin_proposals_session(proposal_id)
    with session_scope() as db:
        # **Locked**: two tabs uploading at once take turns here, so the second reads the
        # proposal settled and is refused as a duplicate click (MI0203), not by the version
        # swap below (MI0201, issue 226).
        proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True)
        if proposal is None:
            raise KeyError(proposal_id)
        refusal = _sample_refusal(proposal)
        if refusal is not None:
            raise ValueError(refusal)

        row = db.get(PipelineAuthoringSession, proposal.session_id)
        measured = inspection.outcome == "measured"
        found = [
            _Found(f.measurement, f.value, f.pieces, f.evidence)
            for f in (inspection.facts if measured else [])
            if f.undetermined is None
        ]
        recorded, kept, disagreed, answered = _record_found(
            db, proposal, row,
            type_id=inspection.type_id if measured else None, states=[], found=found,
            source=FactSource.MEASURED, by=by, stack=stack,
        )
        session_id = proposal.session_id

    _sample_moves(session_id, answered)
    return SampleAnswer(
        phase=current_phase(session_id), recorded=recorded, kept=kept, disagreed=disagreed
    )


# ── the AI reading a sample (14.7.7) ─────────────────────────────────────────────────────────

STALE_AFTER = settings.ai_job_timeout_seconds + 60
"""A reading older than the job could run reads as `no_answer` (ruling 4 of 14.7.7.2's plan):
a worker killed mid-job never writes back, and the card must not wait forever."""


def _reading(block: dict) -> dict | None:
    """The block's reading as it should be read now: a pending one past `STALE_AFTER` is
    `no_answer`. Nothing is written."""
    reading = block.get("reading")
    if not reading or reading.get("state") != "pending" or not reading.get("started_at"):
        return reading
    started = datetime.fromisoformat(reading["started_at"])
    if (_now() - started).total_seconds() > STALE_AFTER:
        return {**reading, "state": "no_answer", "code": "MA0007"}
    return reading


def _aged(payload: dict) -> dict:
    """The payload with a reading the job never finished shown as `no_answer` (nothing written)."""
    block = payload.get("block") or {}
    if not block.get("reading"):
        return payload
    return {**payload, "block": {**block, "reading": _reading(block)}}


def _set_reading(db, proposal, reading: SampleReading | None) -> None:
    payload = dict(proposal.payload)
    block = dict(payload["block"])
    block["reading"] = None if reading is None else reading.model_dump(mode="json")
    payload["block"] = block
    proposal.payload = payload


def reading_of(proposal_id: str) -> SampleReading | None:
    """The question's reading as it should be read now, or `None`."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        found = _reading((proposal.payload or {}).get("block") or {}) if proposal else None
    return None if found is None else SampleReading.model_validate(found)


def start_reading(proposal_id: str) -> int:
    """Mark the question as being read by the AI; the attempt that keys the job."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True)
        if proposal is None:
            raise KeyError(proposal_id)
        # **Asked again under the lock** (issue 241): a click mid-inspection, or a second upload
        # at the same moment, is refused here rather than queueing a job for a settled question.
        refusal = _sample_refusal(proposal)
        if refusal is not None:
            raise ValueError(refusal)
        before = (proposal.payload.get("block") or {}).get("reading") or {}
        attempt = int(before.get("attempt", 0)) + 1
        _set_reading(
            db, proposal, SampleReading(state="pending", attempt=attempt, started_at=_now())
        )
    return attempt


def reading_failed(proposal_id: str, attempt: int, state: str, code: str | None) -> None:
    """End a reading without recording anything, if it is still this attempt's."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True)
        if proposal is None:
            return
        reading = (proposal.payload.get("block") or {}).get("reading") or {}
        if reading.get("attempt") != attempt or reading.get("state") != "pending":
            return
        _set_reading(
            db, proposal,
            SampleReading.model_validate({**reading, "state": state, "code": code}),
        )


def answer_with_reading(
    proposal_id: str, attempt: int, reply, *, by: str, handed_back: bool
) -> SampleAnswer | None:
    """What the AI read of a sample, recorded as *read by AI* (14.7.7), or handed back.

    `None` when the reading is no longer this attempt's or the question was settled meanwhile:
    a late answer records nothing. `handed_back`: the type is one the engine reads, so nothing
    is recorded and the browser sends the file again (spec §8).
    """
    stack = registry.stack()
    _pin_proposals_session(proposal_id)
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True)
        if proposal is None or proposal.state != ProposalState.PENDING.value:
            return None
        reading = (proposal.payload.get("block") or {}).get("reading") or {}
        if reading.get("attempt") != attempt or reading.get("state") != "pending":
            return None
        row = db.get(PipelineAuthoringSession, proposal.session_id)
        session_id = proposal.session_id
        if handed_back:
            _set_reading(db, proposal, SampleReading(
                state="hand_back", attempt=attempt, type_id=reply.type_id,
                states=[s.id for s in reply.states],
            ))
            recorded, kept, disagreed, answered = [], [], [], False
        else:
            found = [_Found(m.id, m.value) for m in reply.measurements]
            recorded, kept, disagreed, answered = _record_found(
                db, proposal, row, type_id=reply.type_id, states=[s.id for s in reply.states],
                found=found, source=FactSource.MODEL_READ, by=by, stack=stack,
            )
            # `read` whether or not it answered (issue 241): a settled question's reading is
            # in its history, and must not spin there.
            _set_reading(db, proposal, SampleReading(
                state="read", attempt=attempt, type_id=reply.type_id,
                states=[s.id for s in reply.states], recorded=recorded, kept=kept,
                disagreed=disagreed,
            ))
    _sample_moves(session_id, answered)
    return SampleAnswer(
        phase=current_phase(session_id), recorded=recorded, kept=kept, disagreed=disagreed
    )


def end_hand_back(proposal_id: str, *, confirmed: bool) -> None:
    """After the re-sent file was inspected (spec §8): `handed` when its format confirmed it,
    and the recorded type dropped when not, so nothing the AI said stays."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id, with_for_update=True)
        if proposal is None or proposal.state != ProposalState.PENDING.value:
            return
        reading = (proposal.payload.get("block") or {}).get("reading") or {}
        if reading.get("state") != "hand_back":
            return
        _set_reading(
            db,
            proposal,
            SampleReading.model_validate({**reading, "state": "handed"}) if confirmed else None,
        )


def reading_open(proposal_id: str, attempt: int) -> bool:
    """Whether this attempt's reading is still worth a model call: the question is pending and
    the reading is this attempt's, pending (issue 241)."""
    with session_scope() as db:
        proposal = db.get(PipelineAuthoringProposal, proposal_id)
        if proposal is None or proposal.state != ProposalState.PENDING.value:
            return False
        reading = _reading((proposal.payload or {}).get("block") or {}) or {}
    return reading.get("attempt") == attempt and reading.get("state") == "pending"
