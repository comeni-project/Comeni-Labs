"""The forge's model calls: drafting a piece, and answering the chat (forge MVP 3, spec §3).

**This is what crosses the `forge_drafting` door.** Each call builds a `ForgeRequest` — the
module's public files, the registry's ids, this adaptation's items — renders its prompt from it,
and validates the reply twice before anything is stored: as the declared reply model, and item
by item against the registry and the module (`mendel_forge.forging.validate`). An invalid reply
goes back to the model once with its problems; a second one is shown to the person as an engine
message. Nothing invalid becomes a proposal.
"""

import asyncio
import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from comeni_ai import Client
from comeni_ai.prompts import PromptTemplate
from comeni_core.egress.authoring import AuthoringRole
from comeni_core.egress.forge import (
    ForgeItemText,
    ForgePiece,
    ForgeRequest,
    ForgeTurn,
    KnownIds,
    ModuleFacts,
)
from comeni_flow.interpret import Refused
from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging import rules
from mendel_forge.forging.model import Actor, Adaptation, Command, Move, Piece, Status
from mendel_forge.forging.protocol import Phase
from mendel_forge.forging.validate import Known, check_items, known
from mendel_forge.forging.values import validate_value
from pydantic import BaseModel, JsonValue, ValidationError

from mendel_api import db
from mendel_api.invocations import Agent, InvocationPurpose, InvocationState
from mendel_api.models import AiInvocation, ForgeAdaptation
from mendel_api.services import forging, registry
from mendel_api.settings import model_access

PROMPTS = Path(__file__).parent.parent / "forge" / "prompts"
CHAT_TAIL = 12
"""How many messages the chat sends back: enough to follow the thread, bounded like the
builder's."""

_PURPOSE = {"forge.questions.v1": InvocationPurpose.ANALYSIS,
            "forge.draft.v1": InvocationPurpose.IMPLEMENTATION,
            "forge.chat.v1": InvocationPurpose.CHAT}


def _client(purpose: InvocationPurpose) -> Client | None:
    """The model for this purpose (Settings → Models → *forge*), or `None`. The seam tests
    replace with a fake."""
    access = model_access(Agent.FORGE.value, purpose.value)
    return Client(access) if access is not None else None


# ── the door payload ──────────────────────────────────────────────────────────────────────────


def _known(adaptation: ForgeAdaptation) -> Known:
    return known(registry.stack(), pending=forging.pending_ids(adaptation.id))


def compose(adaptation: ForgeAdaptation, state: Adaptation, piece: Piece, prompt: str,
            turns: list[tuple[str, str]] = ()) -> ForgeRequest:
    folder = forging.module_folder(adaptation.source, adaptation.path)
    seen = _known(adaptation)
    return ForgeRequest(
        prompt=prompt,
        piece=ForgePiece(piece.value),
        module=ModuleFacts(module=f"{adaptation.source}/{adaptation.path}",
                           main_nf=(folder / "main.nf").read_text(),
                           meta_yml=(folder / "meta.yml").read_text()),
        known=KnownIds(types=sorted(seen.types), roles=sorted(seen.roles),
                       measurements=sorted(seen.measurements), contracts=sorted(seen.contracts),
                       pending=sorted(seen.pending)),
        items=[ForgeItemText(key=key, value=json.dumps(item.value, sort_keys=True))
               for key, item in sorted(state.items.items()) if item.status is not Status.REMOVED],
        turns=[ForgeTurn(role=AuthoringRole(role), content=content)
               for role, content in list(turns)[-CHAT_TAIL:]],
    )


def _values(request: ForgeRequest, problems: list[str]) -> dict[str, str]:
    known_text = "\n".join([
        f"types: {', '.join(request.known.types)}",
        f"roles: {', '.join(request.known.roles)}",
        f"measurements: {', '.join(request.known.measurements)}",
        f"tools: {', '.join(request.known.contracts)}",
        f"pending (from approved drafts, not in the registry yet): "
        f"{', '.join(request.known.pending) or '(none)'}",
    ])
    items_text = "\n".join(f"{i.key} = {i.value}" for i in request.items) or "(nothing yet)"
    turns_text = "\n".join(f"{t.role.value}: {t.content}" for t in request.turns) or "(none)"
    return {
        "module": request.module.module, "main_nf": request.module.main_nf,
        "meta_yml": request.module.meta_yml, "known": known_text, "items": items_text,
        "piece": request.piece.value, "turns": turns_text,
        "problems": ("\nYour previous reply was refused:\n- " + "\n- ".join(problems)
                     if problems else ""),
    }


# ── one call, checked and recorded ───────────────────────────────────────────────────────────


def _call(prompt_id: str, request: ForgeRequest, shape: type[BaseModel], client: Client,
          adaptation_id: str, problems: list[str] = ()) -> tuple[BaseModel | None, str]:
    template = PromptTemplate.load(PROMPTS, prompt_id)
    wanted = template.placeholders()
    rendered = template.render({k: v for k, v in _values(request, list(problems)).items()
                                if k in wanted})
    started = datetime.now(UTC)
    reply = client.respond(rendered.text, shape)
    invocation = _record(prompt_id, rendered.digest, client, adaptation_id, started,
                         ok=reply is not None)
    return reply, invocation


def _record(prompt_id: str, digest: str, client: Client, adaptation_id: str,
            started: datetime, *, ok: bool) -> str:
    invocation_id = secrets.token_hex(16)
    finished = datetime.now(UTC)
    usage = getattr(client, "last_usage", None)
    with db.session_scope() as session:
        session.add(AiInvocation(
            id=invocation_id, agent=Agent.FORGE.value, purpose=_PURPOSE[prompt_id].value,
            model=usage.model if usage else client.access.model,
            provider="local" if client.access.base_url else "",
            prompt_id=prompt_id, prompt_version=prompt_id.rsplit(".", 1)[-1],
            prompt_digest=hashlib.sha256((client.last_prompt or "").encode()).hexdigest()
            if getattr(client, "last_prompt", None) else digest,
            input_digests={"registry": registry.registry_label(), "adaptation": adaptation_id},
            temperature=client.access.temperature,
            state=(InvocationState.SUCCEEDED if ok else InvocationState.REFUSED).value,
            failure_code="" if ok else "MA0004",
            started_at=started, finished_at=finished,
            duration_ms=int((finished - started).total_seconds() * 1000),
            response=getattr(client, "last_response", None),
        ))
    return invocation_id


def _item_problems(items: dict[str, JsonValue], state: Adaptation, adaptation: ForgeAdaptation,
                   moves: dict[str, Move]) -> list[str]:
    """Each value as the registry's model, then the whole against the registry and module."""
    problems: list[str] = []
    for key, value in items.items():
        if moves.get(key) is Move.PROPOSE_REMOVAL:
            continue
        try:
            validate_value(key, value)
        except (ValidationError, KeyError) as error:
            problems.append(f"{key}: {error}".splitlines()[0])
    if problems:
        return problems
    merged = {k: i.value for k, i in state.items.items() if i.status is not Status.REMOVED}
    merged.update({k: v for k, v in items.items() if moves.get(k) is not Move.PROPOSE_REMOVAL})
    folder = forging.module_folder(adaptation.source, adaptation.path)
    spec = ModuleSpec.parse(folder / "main.nf")
    return [f"{p.code}: {p.says}" for p in check_items(merged, _known(adaptation), spec)]


def _engine_says(adaptation_id: str, content: str) -> None:
    forging.post_message(adaptation_id, role="engine", content=content)


# ── drafting a piece ─────────────────────────────────────────────────────────────────────────


def draft_piece(adaptation_id: str, piece: Piece, client: Client | None = None) -> None:
    """Draft the next piece: one call, retried once with its problems, then proposals."""
    adaptation = forging.row(adaptation_id)
    prompt_id = "forge.questions.v1" if piece is Piece.QUESTIONS else "forge.draft.v1"
    client = client or _client(_PURPOSE[prompt_id])
    if client is None:
        _engine_says(adaptation_id, "MI0106: no model is configured for the forge (Settings → "
                     "Models → Adapting tools). Write the piece yourself, or set a model.")
        forging.set_phase(adaptation_id, Phase.REVIEWING)
        return
    problems: list[str] = []
    for _ in range(2):
        state = forging.load(adaptation_id)
        request = compose(adaptation, state, piece, prompt=prompt_id)
        shape = _questions_shape() if piece is Piece.QUESTIONS else _draft_shape()
        reply, invocation = _call(prompt_id, request, shape, client, adaptation_id, problems)
        if reply is None:
            problems = [getattr(client, "last_refusal", None) or "the reply did not fit its shape"]
            continue
        items, because = _proposed(piece, reply)
        moves = {k: Move.REVISE if k in state.items else Move.DRAFT for k in items}
        wrong_piece = [k for k in items if not k.startswith(f"{piece.value}:")]
        problems = [f"{k}: not part of {piece.value}" for k in wrong_piece] or \
            _item_problems(items, state, adaptation, moves)
        if problems:
            continue
        commands = [Command(move=moves[k], actor=Actor.AI, item=k, value=v,
                            because=because.get(k), invocation=invocation)
                    for k, v in sorted(items.items())]
        try:
            forging.act_all(adaptation_id, commands)
        except Refused as refused:
            problems = [str(refused)]
            continue
        forging.set_phase(adaptation_id, Phase.REVIEWING)
        return
    _engine_says(adaptation_id, "The AI's draft of " + piece.value + " was refused twice, so "
                 "nothing was stored:\n- " + "\n- ".join(problems))
    forging.set_phase(adaptation_id, Phase.REVIEWING)


def _questions_shape():
    from mendel_api.forge.replies import QuestionsReply
    return QuestionsReply


def _draft_shape():
    from mendel_api.forge.replies import DraftReply
    return DraftReply


def _proposed(piece: Piece, reply) -> tuple[dict[str, JsonValue], dict[str, str]]:
    if piece is Piece.QUESTIONS:
        return ({q.key: q.model_dump(exclude={"key"}) for q in reply.questions}, {})
    return dict(reply.items), dict(reply.because)


# ── answering the chat ───────────────────────────────────────────────────────────────────────


def answer_message(adaptation_id: str, seq: int, client: Client | None = None) -> None:
    """Reply to the person's message `seq`; its commands are proposals, checked first."""
    from mendel_api.forge.replies import ChatReply

    adaptation = forging.row(adaptation_id)
    client = client or _client(InvocationPurpose.CHAT)
    if client is None:
        forging.answer_message(adaptation_id, seq, "MI0106: no model is configured for the "
                               "forge (Settings → Models → Adapting tools).", [])
        return
    turns = forging.turns(adaptation_id, upto=seq)
    problems: list[str] = []
    for _ in range(2):
        state = forging.load(adaptation_id)
        piece = rules.next_piece(state) or Piece.RULES
        request = compose(adaptation, state, piece, prompt="forge.chat.v1", turns=turns)
        reply, invocation = _call("forge.chat.v1", request, ChatReply, client, adaptation_id,
                                  problems)
        if reply is None:
            problems = [getattr(client, "last_refusal", None) or "the reply did not fit its shape"]
            continue
        items = {c.item: c.value for c in reply.commands}
        moves = {c.item: Move(c.move) for c in reply.commands}
        problems = _item_problems(items, state, adaptation, moves)
        if problems:
            continue
        commands = [Command(move=Move(c.move), actor=Actor.AI, item=c.item,
                            value=None if c.move == "propose_removal" else c.value,
                            because=c.because, invocation=invocation)
                    for c in reply.commands]
        try:
            reached = forging.act_all(adaptation_id, commands)
        except Refused as refused:
            problems = [str(refused)]
            continue
        forging.answer_message(adaptation_id, seq, reply.text,
                               [{**c.model_dump(), "n": reached[c.item]} for c in reply.commands],
                               invocation)
        return
    forging.answer_message(adaptation_id, seq, "The AI's reply was refused twice, so nothing "
                           "changed:\n- " + "\n- ".join(problems), [])


# ── the jobs (AI worker) ─────────────────────────────────────────────────────────────────────


async def draft_forge_piece(ctx: dict, adaptation_id: str, piece: str) -> str:
    await asyncio.to_thread(draft_piece, adaptation_id, Piece(piece))
    return f"{adaptation_id}:{piece}"


async def answer_forge_message(ctx: dict, adaptation_id: str, seq: int) -> str:
    await asyncio.to_thread(answer_message, adaptation_id, seq)
    return f"{adaptation_id}:{seq}"
