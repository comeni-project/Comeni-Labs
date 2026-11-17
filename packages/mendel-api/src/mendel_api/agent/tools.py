"""The engine's operations as tools, defined once (#463).

The builder agent calls them in-process; the MCP server serves the same definitions. A tool
takes a typed input and returns a typed view. `call` turns a refused argument, or a coded
refusal from the engine, into a result the model reads, never an exception that ends its turn.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from comeni_ai.agent import ToolSpec
from comeni_core.egress.agent import AgentToolResult
from pydantic import BaseModel, ValidationError


@dataclass
class ToolContext:
    """Which draft a tool works on, who is acting, and the decisions' revision last read."""

    draft_id: str
    session_id: str | None
    who: str
    expected_revision: int


# Here, not in `read`, so every tool module can take it without importing `read` while `read` is
# still loading `tools`. Its docstring is sent to the model with every tool that takes it.
class Nothing(BaseModel):
    """No arguments."""


@dataclass(frozen=True)
class Tool:
    """One engine operation: its name, what it is for, its input, and what runs it."""

    name: str
    description: str
    input: type[BaseModel]
    run: Callable[[ToolContext, BaseModel], BaseModel]
    writes: bool = False


TOOLS: dict[str, Tool] = {}
"""Every tool, by name. The read, change and build modules register theirs on import."""


def register(tool: Tool) -> Tool:
    if tool.name in TOOLS:
        raise ValueError(f"two tools are called {tool.name}")
    TOOLS[tool.name] = tool
    return tool


_DROPPED = {"title", "maxLength", "minLength", "maxItems", "minItems", "default"}
"""Schema keys the model need not read: pydantic's titles repeat each property's name, and the
limits and defaults are checked and applied here when the call arrives, whatever the model sent."""


def _untitled(node):
    """The schema as the model reads it, small (walk 2026-11-15: the definitions are sent on every
    round of every turn): without `_DROPPED`, and a union of plain types as one type list."""
    if isinstance(node, dict):
        out = {k: _untitled(v) for k, v in node.items() if k not in _DROPPED}
        plain = out.get("anyOf")
        if isinstance(plain, list) and all(set(o) == {"type"} for o in plain):
            out.pop("anyOf")
            out["type"] = [o["type"] for o in plain]
        return out
    if isinstance(node, list):
        return [_untitled(v) for v in node]
    return node


def spec_of(tool: Tool) -> ToolSpec:
    """The tool as a model sees it: name, description, and its input's JSON schema."""
    return ToolSpec(name=tool.name, description=tool.description,
                    parameters=_untitled(tool.input.model_json_schema()))


def _said(failure: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}"
                     for e in failure.errors()[:3])


def printable(name: str) -> str:
    """A tool name the model sent, safe to write back: letters, digits, `_`, `.` and `-` only.
    A model can send anything, and a name that is not a tool is still said back to it."""
    return re.sub(r"[^\w.-]", "?", name)[:64] or "?"


def call(ctx: ToolContext, name: str, arguments: dict) -> AgentToolResult:
    """Run one tool. A tool that does not exist, arguments that do not fit, or a refusal the
    engine gives (a coded `ValueError` or `KeyError`) come back as `ok=False` with the reason."""
    tool = TOOLS.get(name)
    if tool is None:
        return AgentToolResult(tool=printable(name), ok=False,
                               refusal=f"there is no tool called {printable(name)}")
    try:
        given = tool.input.model_validate(arguments)
    except ValidationError as failure:
        return AgentToolResult(tool=name, ok=False, refusal=f"MI0204: {_said(failure)}")
    from mendel_api.services import decisions

    # **A write against a revision that moved is refused** (Review Focus 2): somebody — the
    # person on the canvas, another agent — changed the decisions since this agent last read
    # them. It reads again and decides again; their change stands.
    if tool.writes and decisions.revision(ctx.draft_id) != ctx.expected_revision:
        return AgentToolResult(tool=name, ok=False, refusal=(
            "MI0201: the pipeline changed since you last read it; read it again before "
            "changing it"))
    try:
        # The check above is a fast refusal; the one that holds is each write's own, under the
        # draft's lock (`decisions.expecting`).
        with decisions.expecting(ctx.expected_revision if tool.writes else None):
            view = tool.run(ctx, given)
    except (ValueError, KeyError, LookupError) as refused:
        said = refused.args[0] if refused.args else type(refused).__name__
        text = " ".join(str(said).split())[:500]
        # **A tool refused after writing part of its change** has moved the revision itself:
        # the agent's next write is not stale for it. A stale refusal is not refreshed: the
        # agent reads again.
        if not text.startswith("MI0201"):
            ctx.expected_revision = decisions.revision(ctx.draft_id)
        return AgentToolResult(tool=name, ok=False, refusal=text)
    ctx.expected_revision = decisions.revision(ctx.draft_id)
    return AgentToolResult(tool=name, ok=True, view=view)


def _load() -> None:
    from mendel_api.agent import ask, build, change, console, data, read, reply  # noqa: F401  (register their tools)


_load()
