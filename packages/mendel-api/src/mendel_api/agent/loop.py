"""The builder agent's loop (#463): one job per person's message.

Build the conversation, call the model with the tools, run each tool it calls, give it the
results, and repeat, until it replies without a tool, asks the person, or reaches a limit. Each
tool call is written to the turn before the next model call, so the page's poll shows the agent
working. Every model call is an `ai_invocation` row. A failure fails the turn with its code; a
turn never stays pending.
"""

import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

from comeni_ai.agent import AgentTransport
from comeni_ai.client import LiteLLMTransport
from sqlalchemy import func, select

from mendel_api.agent.tools import TOOLS, ToolContext, call, spec_of
from mendel_api.authoring.types import (
    AgentAsk,
    AgentMessage,
    Notice,
    NoticeKind,
    Phase,
    ToolLine,
    TurnRole,
    TurnState,
)
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation, PipelineAuthoringSession, PipelineAuthoringTurn
from mendel_api.services import decisions, protection
from mendel_api.settings import settings

PROMPT = Path(__file__).with_name("prompt.md")
PROMPT_ID = "builder.agent.v1"
WHO = "builder-agent"


def model_access():
    """The builder agent's model: the talking model (`("builder", "agent")`)."""
    from mendel_api.settings import model_access as access

    return access("builder", "agent")


def transport_for(access) -> AgentTransport:
    """The seam tests replace: the live transport reaches the provider through LiteLLM."""
    return LiteLLMTransport()


def _now() -> datetime:
    return datetime.now(UTC)


def start_session(draft_id: str, *, who: str) -> str:
    """A conversation about a draft: one session per draft."""
    with session_scope() as db:
        existing = db.scalar(select(PipelineAuthoringSession.id)
                             .where(PipelineAuthoringSession.draft_id == draft_id))
        if existing is not None:
            return existing
        session_id = token_hex(16)
        db.add(PipelineAuthoringSession(
            id=session_id, draft_id=draft_id, phase=Phase.COMPLETE.value, at="agent",
            failed_from=None, blueprint={}, registry_digest="", row_version=1,
            created_at=_now(), updated_at=_now(), who=who))
        return session_id


def add_person_turn(session_id: str, text: str) -> int:
    """The person's words, and the agent's turn waiting to answer them: its `seq`."""
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, session_id, with_for_update=True)
        if row is None:
            raise KeyError(session_id)
        last = db.scalar(select(func.max(PipelineAuthoringTurn.seq))
                         .where(PipelineAuthoringTurn.session_id == session_id))
        seq = -1 if last is None else last
        revision = decisions.revision(row.draft_id)
        db.add(PipelineAuthoringTurn(session_id=session_id, seq=seq + 1, role=TurnRole.PERSON,
                                     state=TurnState.ANSWERED, blocks=[], text=text,
                                     base_revision=revision, at=_now()))
        db.add(PipelineAuthoringTurn(session_id=session_id, seq=seq + 2,
                                     role=TurnRole.ASSISTANT, state=TurnState.PENDING,
                                     blocks=[], text="", base_revision=revision, at=_now()))
        row.row_version += 1
        return seq + 2


def _history(session_id: str, before: int) -> list[dict]:
    """Earlier turns as the conversation: the person's words and the agent's own messages."""
    with session_scope() as db:
        turns = db.scalars(select(PipelineAuthoringTurn)
                           .where(PipelineAuthoringTurn.session_id == session_id,
                                  PipelineAuthoringTurn.seq < before)
                           .order_by(PipelineAuthoringTurn.seq)).all()
        out = []
        for turn in turns:
            if turn.role == TurnRole.PERSON.value:
                out.append({"role": "user", "content": turn.text})
            else:
                said = [b.get("text", "") for b in turn.blocks if b.get("kind") == "message"]
                said += [f"(I asked: {b['question']})" for b in turn.blocks
                         if b.get("kind") == "ask"]
                if said:
                    out.append({"role": "assistant", "content": "\n\n".join(said)})
        return out


_LABELS = {
    "read_goal": "Read the goal", "read_pipeline": "Read the pipeline",
    "read_step": "Read the step {node}", "find_tools": "Looked for tools around {type_id}",
    "read_rules": "Read the rules for {role}", "read_facts": "Read the facts about your data",
    "what_is_needed": "Checked what is still needed", "want": "Asked for {type_id}",
    "have": "Noted {type_id}", "set_fact": "Noted {subject}",
    "choose_tool": "Chose {contract} for {type_id}", "exclude_tool": "Left {contract} out",
    "switch_role": "Switched {role}", "switch_input": "Switched {contract}'s {port} {state}",
    "set_value": "Set {name} to {value}", "keep_whole": "Kept {contract} whole",
    "undo": "Withdrew {kind} {subject}", "resolve": "Built the pipeline",
    "compile": "Compiled it to Nextflow", "ask": "Asked you",
}


def _label(name: str, arguments: dict) -> str:
    try:
        return _LABELS.get(name, name).format(**arguments)[:300]
    except (KeyError, IndexError, ValueError):
        return re.sub(r"\{[a-z_]+\}", "", _LABELS.get(name, name)).strip()[:300]


def _write(session_id: str, seq: int, blocks: list[dict], state: TurnState | None = None,
           invocation: str | None = None) -> None:
    with session_scope() as db:
        turn = db.scalar(select(PipelineAuthoringTurn).where(
            PipelineAuthoringTurn.session_id == session_id, PipelineAuthoringTurn.seq == seq))
        turn.blocks = list(blocks)
        if state is not None:
            turn.state = state.value
        if invocation is not None:
            turn.ai_invocation_id = invocation
        row = db.get(PipelineAuthoringSession, session_id)
        row.row_version += 1


def _record(session_id: str, access, sent: list[dict], reply, failure: str | None) -> str:
    """One `ai_invocation` row per model call, as every builder call has."""
    invocation = token_hex(16)
    text = json.dumps(sent, sort_keys=True, default=str)
    usage = getattr(reply, "usage", None)
    with session_scope() as db:
        db.add(AiInvocation(
            id=invocation, agent="builder", purpose="agent",
            model=getattr(access, "model", "") or "", prompt_id=PROMPT_ID, prompt_version="v1",
            prompt_digest=hashlib.sha256(text.encode()).hexdigest(), input_digests={},
            temperature=getattr(access, "temperature", None),
            state="failed" if failure else "succeeded",
            failure_code=(failure or "")[:16], started_at=_now(), finished_at=_now(),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            response=None if reply is None else json.dumps(
                {"text": reply.text, "calls": [c.model_dump() for c in reply.calls]}),
            session_id=session_id))
    return invocation


def _code(failure: Exception) -> str:
    found = re.match(r"(M[A-Z]\d{4})", str(failure))
    return found.group(1) if found else "MA0007"


def run_turn(session_id: str, seq: int, transport: AgentTransport | None = None) -> str:
    """Answer the pending turn `seq`. Returns the turn's final state."""
    with session_scope() as db:
        draft_id = db.get(PipelineAuthoringSession, session_id).draft_id
    blocks: list[dict] = []
    if not protection.allows(protection.Crossing.AGENT):
        blocks.append(Notice(id=f"refused-{seq}", notice=NoticeKind.REFUSAL,
                             text=protection.refuse(protection.Crossing.AGENT),
                             code="MI0213").model_dump(mode="json"))
        _write(session_id, seq, blocks, TurnState.FAILED)
        return TurnState.FAILED.value
    access = model_access()
    transport = transport or transport_for(access)
    ctx = ToolContext(draft_id=draft_id, session_id=session_id, who=WHO,
                      expected_revision=decisions.revision(draft_id))
    tools = [spec_of(t) for t in TOOLS.values()]
    messages = [{"role": "system", "content": PROMPT.read_text()}, *_history(session_id, seq)]
    spent = 0
    for step in range(settings.agent_max_steps):
        try:
            reply = transport.converse(access, messages, tools)
        except Exception as failure:  # noqa: BLE001 — every provider failure ends the turn coded
            invocation = _record(session_id, access, messages, None, _code(failure))
            blocks.append(Notice(id=f"failed-{seq}", notice=NoticeKind.REFUSAL,
                                 text="The AI did not answer. Try again.",
                                 code=_code(failure)).model_dump(mode="json"))
            _write(session_id, seq, blocks, TurnState.FAILED, invocation)
            return TurnState.FAILED.value
        invocation = _record(session_id, access, messages, reply, None)
        if reply.usage is not None:
            spent += (reply.usage.input_tokens or 0) + (reply.usage.output_tokens or 0)
        if reply.text:
            blocks.append(AgentMessage(id=f"say-{seq}-{step}", text=reply.text[:16000])
                          .model_dump(mode="json"))
        if not reply.calls:
            _write(session_id, seq, blocks, TurnState.ANSWERED, invocation)
            return TurnState.ANSWERED.value
        messages.append({"role": "assistant", "content": reply.text or None, "tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
            for c in reply.calls]})
        for made in reply.calls:
            result = call(ctx, made.name, made.arguments)
            blocks.append(ToolLine(id=f"tool-{seq}-{len(blocks)}", name=made.name[:64],
                                   label=_label(made.name, made.arguments), ok=result.ok,
                                   summary=(result.refusal or "")[:2000])
                          .model_dump(mode="json"))
            messages.append({"role": "tool", "tool_call_id": made.id,
                             "content": result.model_dump_json(exclude_none=True)})
            if made.name == "ask" and result.ok:
                asked = result.view
                blocks.append(AgentAsk(id=f"ask-{seq}", question_id=asked.id,
                                       question=asked.question, shape=asked.shape,
                                       options=asked.options, unit=asked.unit,
                                       type_id=asked.type_id).model_dump(mode="json"))
                _write(session_id, seq, blocks, TurnState.ANSWERED, invocation)
                return TurnState.ANSWERED.value
        _write(session_id, seq, blocks, invocation=invocation)
        if spent > settings.agent_max_tokens:
            break
    blocks.append(Notice(id=f"limit-{seq}", notice=NoticeKind.LIMIT,
                         text="I stopped here: this took more steps than one turn allows. "
                              "Tell me to go on, or ask me something.").model_dump(mode="json"))
    _write(session_id, seq, blocks, TurnState.ANSWERED)
    return TurnState.ANSWERED.value


async def run_builder_turn(ctx: dict, session_id: str, seq: int) -> str:
    """The arq job: the turn runs off the event loop, its tools touching the database."""
    state = await asyncio.to_thread(run_turn, session_id, seq)
    return f"{session_id}:{seq}:{state}"
