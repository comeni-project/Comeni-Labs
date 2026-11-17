"""What reaches the builder agent's model (#463): the conversation, and one result per tool call.

The conversation is the person's own words and the agent's own replies, as typed. A tool result
is its name, whether it worked, a typed view of what it read or did, or the coded refusal the
engine gave. The views are declared here, beside the door, so the egress guards walk every shape
that reaches a model. A view may carry a sample's name (the operator's decision, 2026-11-14), never
a path or a file's contents.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from comeni_core.egress.base import EgressPayload
from comeni_core.spell.marks import (
    ContractId,
    Digest,
    Line,
    MeasurementId,
    NodeId,
    ParamValue,
    PortName,
    RoleName,
    SampleName,
    StateName,
    Text,
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
    RESOLVED = "resolved"
    COMPILED = "compiled"
    ASKED = "asked"
    REPLIED = "replied"
    VOCABULARY = "vocabulary"
    DATA = "data"
    COMMAND = "command"


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
    name: Line = ""
    """The analysis's name, so the agent can tell it is still untitled (walk 2026-11-15)."""
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


class InputLine(EgressPayload):
    """One input a step's tool declares (walk 2026-11-15): its name, its type, and whether the
    tool can run without it — what `switch_input` names."""

    name: PortName
    type_id: TypeId
    optional: bool = False


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
    inputs: list[InputLine] = Field(default_factory=list)
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
    """The facts about the person's data, and their samples by name."""

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


class CheckKind(StrEnum):
    MISSING_MATE = "missing_mate"
    ODD_FACT = "odd_fact"


class RuleBy(StrEnum):
    RULE = "rule"
    YOU = "you"
    AI = "ai"


class DataCheckLine(EgressPayload):
    """Something *Check these* found (#511): a sample missing its mate, with the file that looks
    like it, or a sample whose measured value differs from the one most share."""

    sample: SampleName
    kind: CheckKind
    file: SampleName | None = None
    measurement: MeasurementId | None = None


class ReferenceCandidate(EgressPayload):
    """A file already in the analysis, addressed without exposing its filesystem path."""

    id: Digest
    name: SampleName
    collection: SampleName
    types: list[TypeId] = Field(default_factory=list)
    selected: bool = False


class DataView(EgressPayload):
    """The analysis's data by name and fact (#511): its samples, the kinds of data, how the files
    were read into samples and what needs checking. **Never a path or a file's contents.**"""

    kind: Literal[ViewKind.DATA] = ViewKind.DATA
    samples: list[SampleName] = Field(default_factory=list)
    left_out: list[SampleName] = Field(default_factory=list)
    kinds: list[TypeId] = Field(default_factory=list)
    unfit: int = 0
    rule: Line | None = None
    """The reading rule's pattern, `None` for pairing by name."""
    rule_by: RuleBy = RuleBy.RULE
    rule_confirmed: bool = False
    checks: list[DataCheckLine] = Field(default_factory=list)
    references: list[TypeId] = Field(default_factory=list)
    """The references set on Data → References, by kind (#531)."""
    reference_files: list[ReferenceCandidate] = Field(default_factory=list)
    """Available reference files and their possible kinds; selected ones are marked."""


class FiredLine(EgressPayload):
    """A rule that decided something in this pipeline: what, the value, why, and the citation."""

    decides: Line
    value: ParamValue = None
    reason: Line
    cite: Line = ""


class ResolvedView(EgressPayload):
    """The pipeline the decisions resolve to now, what changed, what is open, what rules did."""

    kind: Literal[ViewKind.RESOLVED] = ViewKind.RESOLVED
    steps: list[StepLine] = Field(default_factory=list)
    open_values: list[Line] = Field(default_factory=list)
    rules: list[FiredLine] = Field(default_factory=list)
    needs: list[NeedLine] = Field(default_factory=list)
    """What is still needed (walk 2026-11-15), so a build is one round, not two."""
    changed: Line = ""
    unbuilt: Line = ""


class CompiledView(EgressPayload):
    """That the pipeline compiled: its processes and the files' sizes. **Not the code**
    (walk 2026-11-15): the agent needs neither file, and every later round would send them again;
    the person reads them in the pipeline file."""

    kind: Literal[ViewKind.COMPILED] = ViewKind.COMPILED
    processes: list[Line] = Field(default_factory=list)
    main_nf_lines: int = 0
    config_lines: int = 0


class RepliedView(EgressPayload):
    """The agent's validated message to the person, ending its turn."""

    kind: Literal[ViewKind.REPLIED] = ViewKind.REPLIED
    message: Text


class AskedView(EgressPayload):
    """A question put to the person, and the shape of answer it takes."""

    kind: Literal[ViewKind.ASKED] = ViewKind.ASKED
    id: Line
    question: Line
    shape: Line
    options: list[Line] = Field(default_factory=list)
    unit: Line = ""
    type_id: TypeId | None = None


class MeasureLine(EgressPayload):
    """A fact the registry can measure or take from the person, by its exact id."""

    measurement: MeasurementId
    name: Line
    kind: Line
    values: list[Line] = Field(default_factory=list)
    unit: Line = ""
    describes: TypeId | None = None


class VocabularyView(EgressPayload):
    """Every type and measurement the registry declares (walk 2026-11-15): registry data, so the
    agent names them exactly rather than guessing."""

    kind: Literal[ViewKind.VOCABULARY] = ViewKind.VOCABULARY
    types: list[TypeLine] = Field(default_factory=list)
    measurements: list[MeasureLine] = Field(default_factory=list)


class CommandView(EgressPayload):
    """A command the agent suggests for the run's shell (#511): run by the person, or, when it only
    reads, by the page on the agent's behalf, its output coming back as the next turn."""

    kind: Literal[ViewKind.COMMAND] = ViewKind.COMMAND
    command: Line
    read_only: bool
    because: Line


class ConsoleView(EgressPayload):
    """What the person saw on Run → Console when they wrote (#511): the last lines Nextflow
    printed and the shell's, carried by the page. Paths are shortened to their last parts before
    they are stored."""

    run: Line
    console: Text
    shell: Text = ""


AgentView = Annotated[
    TextView | SamplesView | GoalView | PipelineView | StepView | ToolsView | RulesView
    | FactsView | NeedsView | ResolvedView | CompiledView | AskedView | VocabularyView | DataView
    | CommandView | RepliedView,
    Field(discriminator="kind"),
]
"""Every view a tool may return. Each tool's own view joins this union."""


class AgentToolResult(EgressPayload):
    """One tool call's result, as its model reads it."""

    tool: Line
    ok: bool
    view: AgentView | None = None
    refusal: Line | None = None


class Speaker(StrEnum):
    """Who said a turn of the conversation: the person, or the agent."""

    PERSON = "person"
    AGENT = "agent"


class AgentTurn(EgressPayload):
    """One earlier turn, as the model is shown it: the person's words or the agent's own."""

    speaker: Speaker
    content: Text
    console: ConsoleView | None = None
    """The Console's output beside the person's words, when they wrote from Run → Console."""


class AgentRequest(EgressPayload):
    """Everything one model call of an agent turn carries, besides the fixed system prompt and
    the tool declarations: the conversation so far, and the results of the tools it called."""

    turns: list[AgentTurn] = Field(default_factory=list)
    results: list[AgentToolResult] = Field(default_factory=list)
