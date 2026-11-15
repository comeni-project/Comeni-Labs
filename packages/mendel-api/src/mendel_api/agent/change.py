"""The builder agent's change tools (#463): each is one `DecisionChange`, the AI's, with its
reason, through the one writer every click uses (`services.changes.apply`). The engine checks it
as it checks a person's: an undeclared type, tool or setting is refused (`MI0204`), a value a
measurement refuses likewise (`MI0208`), and nothing is written."""

from typing import Literal

from comeni_core.egress.agent import TextView
from mendel_authoring.payloads import DecisionChange, source_subject
from pydantic import BaseModel, Field

from mendel_api.agent.tools import Tool, ToolContext, register
from mendel_api.services import changes

BECAUSE = Field()
"""Why, in a sentence, for the person to read: the prompt says so once, not every tool."""


class WantArgs(BaseModel):
    type_id: str = Field(description="Type id, e.g. counts.matrix")
    states: list[str] = Field(default_factory=list,
                              description="Required states")
    because: str = BECAUSE


class HaveArgs(BaseModel):
    type_id: str = Field(description="Type id")
    present: bool = Field(description="Whether they have it")
    because: str = BECAUSE


class FactArgs(BaseModel):
    subject: str = Field(description="A measurement id, e.g. read_length")
    value: bool | int | float | str | None = Field(description="Its value; null if unknown")
    because: str = BECAUSE


class ToolArgs(BaseModel):
    type_id: str = Field(description="Type id it makes")
    states: list[str] = Field(default_factory=list)
    contract: str = Field(description="Contract id, from find_tools")
    because: str = BECAUSE


class RoleArgs(BaseModel):
    role: str = Field(description="A role, e.g. trimming")
    on: bool = Field(description="False to leave every tool of this role out")
    because: str = BECAUSE


class InputArgs(BaseModel):
    contract: str
    port: str = Field(description="The tool's optional input")
    state: Literal["off", "optional", "required"]
    because: str = BECAUSE


class ValueArgs(BaseModel):
    name: str = Field(description="Setting name, from read_step")
    value: bool | int | float | str = Field(description="The value to set")
    because: str = BECAUSE


class WholeArgs(BaseModel):
    contract: str
    whole: bool = Field(description="True keeps it whole")
    because: str = BECAUSE


class UndoArgs(BaseModel):
    kind: Literal["want", "input", "measurement", "pin", "parameter", "role", "exclude",
                  "optional_input", "whole"]
    subject: str = Field(description="Its subject, as made")
    states: list[str] = Field(default_factory=list)


def _apply(ctx: ToolContext, change: DecisionChange) -> TextView:
    moved = changes.apply(ctx.draft_id, change, who=ctx.who)
    said = changes.describe(change)
    return TextView(text=said if moved else f"nothing changed: {said}")


def _change(kind: str, subject: str, *, because: str = "", **fields) -> DecisionChange:
    return DecisionChange(kind=kind, subject=subject, actor="model", because=because or None,
                          **fields)


def want(ctx: ToolContext, a: WantArgs) -> TextView:
    view = _apply(ctx, _change("want", a.type_id, because=a.because))
    if a.states:
        view = _apply(ctx, _change("require", a.type_id, states=a.states, because=a.because))
    return view


def have(ctx: ToolContext, a: HaveArgs) -> TextView:
    return _apply(ctx, _change("input", a.type_id, value=a.present, because=a.because))


def set_fact(ctx: ToolContext, a: FactArgs) -> TextView:
    return _apply(ctx, _change("measurement", a.subject, value=a.value, because=a.because))


def choose_tool(ctx: ToolContext, a: ToolArgs) -> TextView:
    return _apply(ctx, _change("pin", a.type_id, value=a.contract, states=a.states,
                               because=a.because))


def exclude_tool(ctx: ToolContext, a: ToolArgs) -> TextView:
    return _apply(ctx, _change("exclude", a.type_id, value=a.contract, states=a.states,
                               because=a.because))


def switch_role(ctx: ToolContext, a: RoleArgs) -> TextView:
    return _apply(ctx, _change("role", a.role, retract=a.on, because=a.because))


def switch_input(ctx: ToolContext, a: InputArgs) -> TextView:
    return _apply(ctx, _change("optional_input", source_subject(a.contract, a.port),
                               value=a.state, because=a.because))


def set_value(ctx: ToolContext, a: ValueArgs) -> TextView:
    return _apply(ctx, _change("parameter", a.name, value=a.value, because=a.because))


def keep_whole(ctx: ToolContext, a: WholeArgs) -> TextView:
    return _apply(ctx, _change("whole", a.contract, retract=not a.whole, because=a.because))


class NameArgs(BaseModel):
    name: str = Field(min_length=1, max_length=80,
                      description="e.g. Mouse liver RNA-seq counts")


def name_pipeline(ctx: ToolContext, a: NameArgs) -> TextView:
    """**A working name** (walk 2026-11-15): the analysis stayed "Untitled analysis". A name is
    not a decision: it moves no decision revision, and the person renames it as they like."""
    from mendel_api.services import draft_mutations

    name = " ".join(a.name.split())
    if not name:
        raise ValueError("MI0204: a name needs words")
    draft_mutations.save(ctx.draft_id, expected_revision=None, name=name)
    return TextView(text=f"named the pipeline {name}")


def undo(ctx: ToolContext, a: UndoArgs) -> TextView:
    return _apply(ctx, _change(a.kind, a.subject, states=a.states, retract=True))


for _tool in (
    Tool("want", "Ask for a result type, in the states it must be in.",
         WantArgs, want, writes=True),
    Tool("have", "Record whether the person has an input type.", HaveArgs,
         have, writes=True),
    Tool("set_fact", "Record a fact about the person's data.", FactArgs,
         set_fact, writes=True),
    Tool("choose_tool",
         "Choose the tool that makes a type, over a rule if needed. Recorded as yours for review.",
         
         ToolArgs, choose_tool, writes=True),
    Tool("exclude_tool", "Leave a tool out where it would make a type.", ToolArgs, exclude_tool,
         writes=True),
    Tool("switch_role", "Leave a role's tools out (on=false), or let them back in.",
         RoleArgs, switch_role, writes=True),
    Tool("switch_input", "Set a tool's optional input to off, optional or required.", InputArgs,
         switch_input, writes=True),
    Tool("set_value",
         "Set a step's setting, over a rule if needed. Recorded as yours for review.",
         ValueArgs,
         set_value, writes=True),
    Tool("keep_whole", "Keep a step whole, or let it run on parts of each sample.",
         WholeArgs, keep_whole, writes=True),
    Tool("undo", "Withdraw a change you or the person made.",
         UndoArgs, undo, writes=True),
    Tool("name_pipeline", "Give the analysis a short working name.", NameArgs, name_pipeline),
):
    register(_tool)
