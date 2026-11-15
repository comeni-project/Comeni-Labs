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
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

from comeni_ai.agent import AgentTransport
from comeni_ai.client import LiteLLMTransport
from comeni_core.egress.agent import AgentRequest, AgentTurn, Speaker
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from mendel_api.agent.tools import TOOLS, ToolContext, call, printable, spec_of
from mendel_api.authoring.types import (
    AgentAsk,
    AgentMessage,
    Notice,
    NoticeKind,
    ToolLine,
    TurnRole,
    TurnState,
)
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation, PipelineAuthoringSession, PipelineAuthoringTurn
from mendel_api.services import decisions, protection
from mendel_api.settings import settings

log = logging.getLogger(__name__)

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


def _existing(db, draft_id: str) -> str | None:
    return db.scalar(select(PipelineAuthoringSession.id)
                     .where(PipelineAuthoringSession.draft_id == draft_id))


def start_session(draft_id: str, *, who: str) -> str:
    """A conversation about a draft: one session per draft. Two opens at once make one: the
    unique index refuses the second insert, and it is answered with the winner's."""
    with session_scope() as db:
        existing = _existing(db, draft_id)
        if existing is not None:
            return existing
    session_id = token_hex(16)
    try:
        with session_scope() as db:
            db.add(PipelineAuthoringSession(
                id=session_id, draft_id=draft_id, blueprint={}, registry_digest="",
                row_version=1, created_at=_now(), updated_at=_now(), who=who))
    except IntegrityError:
        with session_scope() as db:
            winner = _existing(db, draft_id)
        if winner is None:
            raise
        return winner
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


def conversation(session_id: str, before: int) -> AgentRequest:
    """Earlier turns as the declared payload (door `builder_agent`): the person's words and the
    agent's own messages, and what it asked."""
    with session_scope() as db:
        turns = db.scalars(select(PipelineAuthoringTurn)
                           .where(PipelineAuthoringTurn.session_id == session_id,
                                  PipelineAuthoringTurn.seq < before)
                           .order_by(PipelineAuthoringTurn.seq)).all()
        out = []
        for turn in turns:
            if turn.role == TurnRole.PERSON.value:
                out.append(AgentTurn(speaker=Speaker.PERSON, content=turn.text))
            else:
                said = [b.get("text", "") for b in turn.blocks if b.get("kind") == "message"]
                said += [f"(I asked: {b['question']})" for b in turn.blocks
                         if b.get("kind") == "ask"]
                if said:
                    out.append(AgentTurn(speaker=Speaker.AGENT, content="\n\n".join(said)))
        return AgentRequest(turns=out)


def _history(session_id: str, before: int) -> list[dict]:
    """The conversation in the provider's message shape."""
    role = {Speaker.PERSON: "user", Speaker.AGENT: "assistant"}
    return [{"role": role[t.speaker], "content": t.content}
            for t in conversation(session_id, before).turns]


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


_DOING = {
    "read_goal": "Reading the goal", "read_pipeline": "Reading the pipeline",
    "read_step": "Reading the step {node}", "find_tools": "Looking for tools around {type_id}",
    "read_rules": "Reading the rules for {role}", "read_facts": "Reading the facts about your data",
    "what_is_needed": "Checking what is still needed", "want": "Asking for {type_id}",
    "have": "Noting {type_id}", "set_fact": "Noting {subject}",
    "choose_tool": "Choosing {contract} for {type_id}", "exclude_tool": "Leaving {contract} out",
    "switch_role": "Switching {role}", "switch_input": "Switching {contract}'s {port} {state}",
    "set_value": "Setting {name} to {value}", "keep_whole": "Keeping {contract} whole",
    "undo": "Withdrawing {kind} {subject}", "resolve": "Building the pipeline",
    "compile": "Compiling it to Nextflow", "ask": "Asking you",
}
"""What each tool is doing while it runs (#504), beside what it did (`_LABELS`)."""


def _node_of(session_id: str, arguments: dict) -> str | None:
    """The step a tool call touched (#499): named by its `node`, or found by the tool's contract
    or the setting's name — **and only a step the pipeline last built has** (plan 2 review), so
    the link an answer carries is the engine's, never an id the model made up."""
    with session_scope() as db:
        stored = db.get(PipelineAuthoringSession, session_id).blueprint
    pipeline = (stored or {}).get("pipeline") or {}
    steps = [s for s in pipeline.get("steps") or [] if isinstance(s, dict)]
    ids = {s.get("id") for s in steps}
    named = arguments.get("node")
    if isinstance(named, str):
        return named if named in ids else None
    contract, setting = arguments.get("contract"), arguments.get("name")
    if contract:
        return next((s["id"] for s in steps
                     if (s.get("module") or {}).get("contract_id") == contract), None)
    if setting:
        # A setting's name alone may be any step's: linked only when exactly one step has it.
        having = [s["id"] for s in steps
                  if any(x.get("name") == setting for x in s.get("settings") or [])]
        return having[0] if len(having) == 1 else None
    return None


def _label(name: str, arguments: dict, labels: dict[str, str] = _LABELS) -> str:
    try:
        return labels.get(name, name).format(**arguments)[:300]
    except (KeyError, IndexError, ValueError):
        return re.sub(r"\{[a-z_]+\}", "", labels.get(name, name)).strip()[:300]


def fail(session_id: str, seq: int, text: str) -> None:
    """End the turn `seq` as failed, coded `MI0220`, keeping what it already wrote: the page
    stops saying it is working and offers Retry."""
    with session_scope() as db:
        turn = db.scalar(select(PipelineAuthoringTurn).where(
            PipelineAuthoringTurn.session_id == session_id, PipelineAuthoringTurn.seq == seq))
        kept = [b for b in (turn.blocks or []) if not b.get("running")]
    _write(session_id, seq, [*kept, Notice(id=f"failed-{seq}", notice=NoticeKind.REFUSAL,
                                           text=text, code="MI0220").model_dump(mode="json")],
           TurnState.FAILED)


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
    if access is None:
        blocks.append(Notice(id=f"refused-{seq}", notice=NoticeKind.REFUSAL,
                             text="No model is configured, so the builder cannot answer. Choose "
                                  "one in Settings → Models.", code="MI0106")
                      .model_dump(mode="json"))
        _write(session_id, seq, blocks, TurnState.FAILED)
        return TurnState.FAILED.value
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
            blocks.append(AgentMessage(id=f"say-{seq}-{step}", text=reply.text[:16000],
                                       narration=bool(reply.calls)).model_dump(mode="json"))
        if not reply.calls:
            _write(session_id, seq, blocks, TurnState.ANSWERED, invocation)
            return TurnState.ANSWERED.value
        messages.append({"role": "assistant", "content": reply.text or None, "tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
            for c in reply.calls]})
        for made in reply.calls:
            # **Said before it runs** (#504): the page shows what is happening, not "working".
            line, name = f"tool-{seq}-{len(blocks)}", printable(made.name)
            blocks.append(ToolLine(id=line, name=name, ok=True, running=True,
                                   label=_label(name, made.arguments, _DOING))
                          .model_dump(mode="json"))
            _write(session_id, seq, blocks)
            try:
                result = call(ctx, made.name, made.arguments)
                node = _node_of(session_id, made.arguments) if result.ok else None
            except Exception:  # noqa: BLE001 — a turn never stays pending on an engine error
                # **Failed, not left waiting** (#463 review): an error the engine does not refuse
                # with a code (a lost connection, a bug) ends the turn so the page offers Retry.
                # The error goes to the log, not to the chat or the model.
                log.exception("builder turn %s:%s stopped in tool %s", session_id, seq, name)
                blocks[-1] = ToolLine(id=line, name=name, ok=False,
                                      label=_label(name, made.arguments)).model_dump(mode="json")
                blocks.append(Notice(id=f"failed-{seq}", notice=NoticeKind.REFUSAL,
                                     text="Something went wrong inside the builder while it "
                                          "worked. Try again.", code="MI0220")
                              .model_dump(mode="json"))
                _write(session_id, seq, blocks, TurnState.FAILED, invocation)
                return TurnState.FAILED.value
            blocks[-1] = ToolLine(id=line, name=name,
                                  label=_label(name, made.arguments), ok=result.ok,
                                  summary=(result.refusal or "")[:2000], node=node)\
                .model_dump(mode="json", exclude_none=True)
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
