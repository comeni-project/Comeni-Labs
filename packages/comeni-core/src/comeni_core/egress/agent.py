"""What the builder agent's tools return to its model (#463): one result per tool call.

A tool's name, whether it worked, a typed view of what it read or did, or the coded refusal the
engine gave. The views are declared here, beside the door, so the egress guards walk every shape
that reaches a model. At protection level 0 a view may carry a sample's name (the operator's
decision, 2026-11-14); stricter levels filter before a view is built.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from comeni_core.egress.base import EgressPayload
from comeni_core.spell.marks import (
    ContractId,
    Line,
    MeasurementId,
    NodeId,
    ParamValue,
    PortName,
    RoleName,
    SampleName,
    StateName,
    TypeId,
)


class ViewKind(StrEnum):
    """Which view a tool returned: the union's discriminator."""

    TEXT = "text"
    SAMPLES = "samples"
    GOAL = "goal"
    PIPELINE = "pipeline"
    STEP = "step"
    TOOLS = "tools"
    RULES = "rules"
    FACTS = "facts"
    NEEDS = "needs"


class TypeLine(EgressPayload):
    """A type by its id and its declared name."""

    type_id: TypeId
    name: Line
    states: list[StateName] = Field(default_factory=list)


class FactLine(EgressPayload):
    """A fact about the data: its id, its value, and where it came from."""

    measurement: MeasurementId
    value: ParamValue = None
    source: Line


class ChoiceLine(EgressPayload):
    """A tool chosen for a site, or a value set, and who made it."""

    subject: Line
    value: ParamValue = None
    by: Line
    because: Line = ""


class GoalView(EgressPayload):
    """What is wanted, what the person has, the facts, and the choices made."""

    kind: Literal[ViewKind.GOAL] = ViewKind.GOAL
    wants: list[TypeLine] = Field(default_factory=list)
    have: list[TypeLine] = Field(default_factory=list)
    facts: list[FactLine] = Field(default_factory=list)
    choices: list[ChoiceLine] = Field(default_factory=list)


class StepLine(EgressPayload):
    """One step of the pipeline as built."""

    node: NodeId
    contract: ContractId
    tool: Line
    reads: list[TypeId] = Field(default_factory=list)
    makes: list[TypeId] = Field(default_factory=list)
    chosen_by: Line
    open_values: list[PortName] = Field(default_factory=list)
    ai_unreviewed: bool = False


class PipelineView(EgressPayload):
    """The pipeline as the engine builds it from the decisions now."""

    kind: Literal[ViewKind.PIPELINE] = ViewKind.PIPELINE
    steps: list[StepLine] = Field(default_factory=list)
    inputs: list[TypeLine] = Field(default_factory=list)
    gives: list[TypeLine] = Field(default_factory=list)
    unbuilt: Line = ""
    """Why nothing could be built, when nothing could."""


class SettingLine(EgressPayload):
    """One setting of a step: its value, how sure, who decided, why, and the citation."""

    name: PortName
    value: ParamValue = None
    tier: int
    source: Line
    reason: Line
    cite: Line = ""


class StepView(EgressPayload):
    """One step in full."""

    kind: Literal[ViewKind.STEP] = ViewKind.STEP
    node: NodeId
    contract: ContractId
    tool: Line
    description: Line = ""
    does: Line = ""
    why_here: Line
    chosen: Line
    chosen_tier: int
    settings: list[SettingLine] = Field(default_factory=list)


class ToolRef(EgressPayload):
    """A tool that makes or reads a type."""

    contract: ContractId
    tool: Line
    roles: list[RoleName] = Field(default_factory=list)


class ToolsView(EgressPayload):
    """Who makes a type and who reads it."""

    kind: Literal[ViewKind.TOOLS] = ViewKind.TOOLS
    type_id: TypeId
    name: Line
    makes: list[ToolRef] = Field(default_factory=list)
    reads: list[ToolRef] = Field(default_factory=list)


class RuleLine(EgressPayload):
    """One rule: what it decides, its rows as sentences, why, and its citation."""

    decides: Line
    rows: list[Line] = Field(default_factory=list)
    because: Line = ""
    cite: Line = ""


class RulesView(EgressPayload):
    """The rules that decide for a role."""

    kind: Literal[ViewKind.RULES] = ViewKind.RULES
    role: RoleName
    rules: list[RuleLine] = Field(default_factory=list)


class FactsView(EgressPayload):
    """The facts about the person's data, and their samples by name at level 0."""

    kind: Literal[ViewKind.FACTS] = ViewKind.FACTS
    facts: list[FactLine] = Field(default_factory=list)
    samples: list[SampleName] = Field(default_factory=list)


class NeedLine(EgressPayload):
    """Something the pipeline needs that nothing settles yet."""

    kind: Line
    subject: Line
    name: Line
    why: Line
    optional: bool = False


class NeedsView(EgressPayload):
    """What the goal still needs from the person."""

    kind: Literal[ViewKind.NEEDS] = ViewKind.NEEDS
    needs: list[NeedLine] = Field(default_factory=list)


class TextView(EgressPayload):
    """A sentence from the engine about what a tool did."""

    kind: Literal[ViewKind.TEXT] = ViewKind.TEXT
    text: Line


class SamplesView(EgressPayload):
    """The samples of the person's last upload, by name."""

    kind: Literal[ViewKind.SAMPLES] = ViewKind.SAMPLES
    names: list[SampleName] = Field(default_factory=list)


AgentView = Annotated[
    TextView | SamplesView | GoalView | PipelineView | StepView | ToolsView | RulesView
    | FactsView | NeedsView,
    Field(discriminator="kind"),
]
"""Every view a tool may return. Each tool's own view joins this union."""


class AgentToolResult(EgressPayload):
    """One tool call's result, as its model reads it."""

    tool: Line
    ok: bool
    view: AgentView | None = None
    refusal: Line | None = None
