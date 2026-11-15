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

BECAUSE = Field(description="Why, in a sentence: recorded with the choice for the person to read")


class WantArgs(BaseModel):
    type_id: str = Field(description="The type of result wanted, e.g. counts.matrix")
    states: list[str] = Field(default_factory=list,
                              description="States the result must be in, e.g. gene_level")
    because: str = BECAUSE


class HaveArgs(BaseModel):
    type_id: str = Field(description="A type the person has, or does not have")
    present: bool = Field(description="Whether they have it")
    because: str = BECAUSE


class FactArgs(BaseModel):
    subject: str = Field(description="A measurement id, e.g. read_length")
    value: bool | int | float | str | None = Field(description="Its value; null if unknown")
    because: str = BECAUSE


class ToolArgs(BaseModel):
    type_id: str = Field(description="The type the tool makes, e.g. alignment.bam")
    states: list[str] = Field(default_factory=list)
    contract: str = Field(description="The tool's contract id, as find_tools gives it")
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
    name: str = Field(description="A setting's name, as read_step lists it")
    value: bool | int | float | str = Field(description="The value to set")
    because: str = BECAUSE


class WholeArgs(BaseModel):
    contract: str
    whole: bool = Field(description="True keeps the step whole; false lets it run on parts")
    because: str = BECAUSE


class UndoArgs(BaseModel):
    kind: Literal["want", "input", "measurement", "pin", "parameter", "role", "exclude",
                  "optional_input", "whole"]
    subject: str = Field(description="What the change was about, as it was made")
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
                      description="A short working name, e.g. Mouse liver RNA-seq counts")


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
    Tool("want", "Say what result the pipeline should make, and the states it must be in.",
         WantArgs, want, writes=True),
    Tool("have", "Record that the person has, or does not have, an input of a type.", HaveArgs,
         have, writes=True),
    Tool("set_fact", "Record a fact about the person's data, e.g. their read length.", FactArgs,
         set_fact, writes=True),
    Tool("choose_tool", "Choose the tool that makes a type, over the registry's rule if it "
         "chose another. Recorded as the AI's, with your reason, for the person to review.",
         ToolArgs, choose_tool, writes=True),
    Tool("exclude_tool", "Leave a tool out where it would make a type.", ToolArgs, exclude_tool,
         writes=True),
    Tool("switch_role", "Leave every tool of a role out (on=false), or let it back in.",
         RoleArgs, switch_role, writes=True),
    Tool("switch_input", "Switch a tool's optional input off, optional or required.", InputArgs,
         switch_input, writes=True),
    Tool("set_value", "Set a step's setting, over the registry's rule if it decided another. "
         "Recorded as the AI's, with your reason, for the person to review.", ValueArgs,
         set_value, writes=True),
    Tool("keep_whole", "Keep a step whole rather than running it on parts of each sample.",
         WholeArgs, keep_whole, writes=True),
    Tool("undo", "Withdraw a change: a want, an input, a fact, a tool choice, a setting.",
         UndoArgs, undo, writes=True),
    Tool("name_pipeline", "Give the analysis a short working name once you know what it is; "
         "the person can rename it.", NameArgs, name_pipeline),
):
    register(_tool)
