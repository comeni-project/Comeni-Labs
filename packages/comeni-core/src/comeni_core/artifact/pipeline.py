"""Models and validation for the saved pipeline.yml artifact.

Pipeline combines steps, external input channels, the goal, and provenance.
Each step records its module, settings, call arguments, and input connections.
These records give the compiler the details needed to emit Nextflow without
reading the registry. Pipeline.of() delegates construction to materialise.py.

Validators check local values and consistency across the artifact. Loading
reads the current schema version only (no upgraders before v0.1.0). Replay helpers carry edited
parameter answers into upgrades; content_digest() links the artifact to its
recorded generated files.

Complexity: this module uses expected O(n) record scans and indexed lookups,
where n includes steps, settings, channels, connections, and decisions.
Sorting groups and diagnostics adds up to O(n log n). Decision replay indexes settings
and goal pins once. Digesting is linear in the serialized content size.
Indexes require O(n) extra memory. Nested model validation and text processing
have additional costs, so these bounds are not a guarantee for the complete
construction or loading call.
"""

from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from comeni_core.artifact.digest import digest_of
from comeni_core.artifact.emitted import Emitted
from comeni_core.artifact.gates import Gate
from comeni_core.artifact.lockfile import LockedLayer
from comeni_core.artifact.param_refs import extract_param_refs
from comeni_core.declared.layered import Displacement
from comeni_core.declared.measurement import MeasurementKind, MetaValue
from comeni_core.diagnostics import coded
from comeni_core.egress.base import EgressPayload
from comeni_core.goal.asked import Facts, Goal, Intent
from comeni_core.goal.premise import PremiseRecord
from comeni_core.plan.at_run import (
    AtRun,
    AtRunCondition,
    Confirm,
    Guard,
    MetaAtRun,
    SampleRule,
)
from comeni_core.plan.decision import DecisionKind, DecisionRecord
from comeni_core.plan.ir import InputRecord, Parts
from comeni_core.plan.tiers import (
    Grain,
    InputForm,
    PremiseOrigin,
    ReviewLevel,
    Tier,
    ValueSource,
    review_level_for,
)
from comeni_core.spell.marks import (
    ChannelName,
    ContainerRef,
    ContractId,
    Digest,
    EdgeRef,
    GroovyExpression,
    LayerName,
    Line,
    MeasurementId,
    NfIdentifier,
    NfPath,
    NfTemplate,
    NodeId,
    OptionId,
    ParamValue,
    PortName,
    StateName,
    TestDataRef,
    TypeId,
    substitutable,
)
from comeni_core.spell.routes import TEMPLATED, ExtKey, Join, Via

# ---------------- CONSTANTS ----------------

SCHEMA_VERSION = 9
"""The schema version written and the only one read.

Bump when the serialized shape changes; content digests depend on that shape.
"""

__all__ = [
    "SCHEMA_VERSION",
    "CallArg",
    "Channel",
    "MetaEntry",
    "ModuleRef",
    "Pipeline",
    "RegistryProvenance",
    "RunRule",
    "Setting",
    "Step",
    "StepInput",
    "Why",
]


# ---------------- VALIDATION HELPERS ----------------


def _duplicates(values: Iterable[str]) -> list[str]:
    """Find repeated values in one pass, then sort the distinct duplicates."""
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        else:
            seen.add(value)
    return sorted(repeated)


# ---------------- MODELS: PROVENANCE AND STEP DETAILS ----------------


class Why(BaseModel):
    """Provenance for a value or choice: its tier, source, reason, and supporting facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_computed(cls, data: object) -> object:
        """Discard serialized review_level so it is recomputed from tier on loading."""
        if isinstance(data, dict) and "review_level" in data:
            data = {k: v for k, v in data.items() if k != "review_level"}
        return data

    tier: Tier
    source: ValueSource

    @computed_field
    @property
    def review_level(self) -> ReviewLevel:
        """Derive the required review level from the decision tier."""
        return review_level_for(self.tier)

    reason: Line

    premise: list[PremiseRecord] = Field(default_factory=list)
    """Facts used to make the decision, including their origins."""

    for_value: ParamValue = None
    """Value this reason explains. None leaves the value unspecified; it may also be unresolved."""

    axis_reason: Line = ""
    """Methodology behind the decision, separate from the reason for the selected answer."""

    from_layer: LayerName | None = None
    displaced_layer: LayerName | None = None
    """Lower-priority layer whose declaration was superseded, if any."""


def _no_flags_why() -> Why:
    """Explain that the contract declares no baseline flags."""
    return Why(
        tier=Tier.STRUCTURAL,
        source=ValueSource.RESOLVER,
        reason="this contract declares no flags its module always needs",
        for_value="",
    )


class ModuleRef(BaseModel):
    """Contract identity, content fingerprint, and declared container for one step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: ContractId
    digest: Digest
    container: ContainerRef | None = None
    """Container reference as declared; this model does not resolve tags to immutable digests."""


class Setting(BaseModel):
    """Resolved parameter value, its route to the tool, and its provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: PortName
    value: ParamValue
    via: Via
    key: ExtKey | None = None
    template: NfTemplate | None = None
    why: Why
    at_run: AtRun | None = Field(default=None, exclude_if=lambda at_run: at_run is None)
    """Decided at run time (#217): the lookup the pipeline runs over a measured fact. `value`
    is then the fallback, used when the fact is undetermined or no row matches."""

    @model_validator(mode="after")
    def _a_raw_ext_value_cannot_be_groovy(self) -> "Setting":
        """Reject unsafe raw values on the untemplated ext route (MD0221).

        Unresolved values contribute no fragment and are allowed. Other raw values
        must satisfy the restricted substitution syntax before config generation.
        """
        if (
            self.via is Via.EXT
            and self.template is None
            and self.value is not None
            and not substitutable(self.value)
        ):
            raise ValueError(
                coded("MD0221", f"{self.name} routes {self.value!r} to `ext.{self.key}` with no "
                "template, so it is written into Nextflow config verbatim. Use letters, "
                "digits and _ . : + - only, or a number, or true/false — "
                "`mendel explain MD0221`.")
            )
        return self


class MetaEntry(BaseModel):
    """One channel metadata key and value, with provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: NfIdentifier
    value: ParamValue
    why: Why
    """Required provenance identifying the source of the metadata value."""


class ExtArgs(BaseModel):
    """Baseline argument template declared by a module, with its reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template: NfTemplate = ""
    why: Why

    @classmethod
    def none(cls) -> "ExtArgs":
        """Return empty baseline arguments with an explicit reason."""
        return cls(why=_no_flags_why())

    @model_validator(mode="before")
    @classmethod
    def _accept_a_bare_template(cls, data: object) -> object:
        """Normalize a string template, recording that the contract supplies no reason."""
        if isinstance(data, str):
            return {
                "template": data,
                "why": {
                    "tier": Tier.STRUCTURAL,
                    "source": ValueSource.RESOLVER,
                    "reason": "declared by the contract with no stated reason",
                    "for_value": data,
                },
            }
        return data


class PortJoin(BaseModel):
    """How one port after the first of a shared slot meets the ones before it (#464)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    port: PortName
    join: Join


class CallArg(BaseModel):
    """One positional process argument.

    Records input ports, a literal, an empty input width, or a setting reference,
    plus any join rule and provenance needed for emission.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    ports: list[PortName] = Field(default_factory=list)
    literal: ParamValue = None
    empty_width: int | None = None
    from_setting: PortName | None = None
    """Setting whose value supplies this positional argument."""
    join: Join | None = None
    """How multiple input ports are combined for this argument."""
    key: MeasurementId | None = Field(default=None, exclude_if=lambda key: key is None)
    """For a `by_key` or `by_ref` join, the fact the ports meet on (#466)."""
    joins: list["PortJoin"] = Field(default_factory=list, exclude_if=lambda joins: not joins)
    """Each later port's own join, when the contract gives one per port (#464); then `join`
    is unset."""
    why: Why | None = None
    """Provenance for the argument, when supplied."""

    def join_for(self, port: str) -> Join:
        """How `port`, a port after the first, meets the ones before it."""
        if port not in self.ports[1:]:
            raise ValueError(f"{port!r} is not a port after the first of {self.ports}")
        found = next((j.join for j in self.joins if j.port == port), self.join)
        if found is None:
            raise ValueError(f"call argument {self.ports} declares no join for {port!r}")
        return found


class PartsWiring(StrEnum):
    """How an input meets parts of a sample (#466, stage 6)."""

    SPREAD = "spread"
    """Reads a splitter's output: each sample's parts become items of their own, carrying
    `meta.part` and `meta.comeni_parts`."""

    GATHER = "gather"
    """A merger reading one sample's parts: gathered per sample, sized by `meta.comeni_parts`."""


class StepInput(BaseModel):
    """Connection from one consumed port to an upstream output or external channel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    port: PortName
    source: EdgeRef | None = None
    """Upstream output reference in node.port form; mutually exclusive with channel."""
    channel: ChannelName | None = None
    """External input channel name; mutually exclusive with source."""
    gather: bool = False
    """Collect the whole channel for one invocation, rather than process individual items."""
    by: MeasurementId | None = Field(default=None, exclude_if=lambda by: by is None)
    """With `gather`, gather per value of this key rather than over the study (#466)."""
    select: list[AtRunCondition] = Field(default_factory=list, exclude_if=lambda s: not s)
    """Only the samples meeting every condition, as the contract's port selects them (#466)."""
    mixed: list[EdgeRef] = Field(default_factory=list, exclude_if=lambda m: not m)
    """Further upstream outputs feeding this input, sorted: branches of a tool chosen per
    sample rejoining here, each sample arriving from its own (#466)."""
    parts: PartsWiring | None = Field(default=None, exclude_if=lambda parts: parts is None)
    """Where this input spreads a sample into parts or gathers them back (#466)."""

    states: list[StateName] = Field(default_factory=list)
    """States carried by the upstream connection, sorted during materialisation."""

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "StepInput":
        """Require exactly one upstream source or external channel (MD0215)."""
        if (self.source is None) == (self.channel is None):
            raise ValueError(
                coded("MD0215", f"input {self.port} must name exactly one of `source` or `channel`")
            )
        if self.parts is not None and self.source is None:
            raise ValueError(f"input {self.port} {self.parts.value}s parts, which only a step "
                             "makes")
        if self.parts is PartsWiring.GATHER and not self.gather:
            raise ValueError(f"input {self.port} gathers parts and does not gather")
        return self


# ---------------- MODELS: STEPS AND CHANNELS ----------------


class RunRule(BaseModel):
    """One constraint only a run can settle (#460), in the pipeline's own params: when every
    param in `given` is supplied, those in `requires` must be and those in `forbids` must not."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    given: list[NfIdentifier]
    requires: list[NfIdentifier] = Field(default_factory=list)
    forbids: list[NfIdentifier] = Field(default_factory=list)
    says: Line


class Step(BaseModel):
    """One pipeline process, including its module, arguments, inputs, and provenance."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NodeId
    module: ModuleRef
    process: NfIdentifier
    include: NfPath
    why: Why
    """Reason this contract was selected for the step."""

    presence: Why | None = None
    """Reason the step is needed, separate from the selected contract; optional when unrecorded."""
    ext_args: ExtArgs = Field(default_factory=lambda: ExtArgs(why=_no_flags_why()))
    """Baseline module flags, composed before the resolved setting fragments."""
    inputs: list[StepInput] = Field(default_factory=list)
    call: list[CallArg] = Field(default_factory=list)
    settings: list[Setting] = Field(default_factory=list)
    input_states: list[InputRecord] = Field(
        default_factory=list, exclude_if=lambda states: not states)
    """Each optional input's state, who set it and why, sorted by port (#460); omitted when the
    step's tool has none."""
    sample_rules: list[SampleRule] = Field(default_factory=list, exclude_if=lambda r: not r)
    """This step's rules each sample's facts settle (#466): a sample breaking one stops the run
    before the step runs, naming the sample and the rule."""
    guard: Guard | None = Field(default=None, exclude_if=lambda guard: guard is None)
    parts: Parts | None = Field(default=None, exclude_if=lambda parts: parts is None)
    """Whether this step runs on parts of a sample, with which tools and why (#466)."""
    """The samples this step takes, when each sample's tool is chosen per sample and only some
    lead here (#466): the rule, written as a lookup, and the tools whose samples it takes."""
    run_rules: list[RunRule] = Field(default_factory=list, exclude_if=lambda rules: not rules)
    """This step's constraints only a run can settle, because they involve an input each run
    may leave empty. The pipeline checks them at its start and the run sheet before sending.
    On the step, not the channel: a channel carries no free text (test_scope_override)."""

    @model_validator(mode="after")
    def _no_duplicate_setting(self) -> "Step":
        """Reject repeated setting names within this step (MD0212)."""
        repeated = _duplicates(setting.name for setting in self.settings)
        if repeated:
            raise ValueError(
                coded("MD0212", f"step {self.id} declares {', '.join(repeated)} more than once")
            )
        return self

    @model_validator(mode="after")
    def _no_two_writers_for_one_destination(self) -> "Step":
        """Reject settings sharing an ext destination that accepts only one value (MD0208).

        Argument keys in TEMPLATED intentionally compose multiple fragments and
        are excluded from this collision check.
        """
        writers: dict[ExtKey, list[str]] = {}
        for setting in self.settings:
            if setting.via is Via.EXT and setting.key not in TEMPLATED:
                writers.setdefault(setting.key, []).append(setting.name)
        collided = sorted(
            (key, sorted(who)) for key, who in writers.items() if len(who) > 1
        )
        if collided:
            key, who = collided[0]
            raise ValueError(
                coded(
                    "MD0208",
                    f"step {self.id} routes {' and '.join(who)} to ext.{key.value}, which "
                    f"takes one value — a second writer silently wins. `mendel explain MD0208`.")
            )
        return self


class MetaKeyOf(BaseModel):
    """One key a samplesheet fact becomes on the sample's `meta`, and how its value is spelled
    there: the fact's own id, read by run-time lookups, and a module's key (`single_end`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: NfIdentifier
    translate: list[MetaValue] = Field(default_factory=list, exclude_if=lambda t: not t)


class SheetFact(BaseModel):
    """A fact each sample's samplesheet row states (#466), checked when the run starts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: MeasurementId
    column: NfIdentifier
    kind: MeasurementKind
    values: list[OptionId] = Field(default_factory=list, exclude_if=lambda v: not v)
    """The allowed values, for an enum: identifiers, as a measurement declares them."""
    minimum: float | None = Field(default=None, exclude_if=lambda m: m is None)
    maximum: float | None = Field(default=None, exclude_if=lambda m: m is None)
    required: bool
    """A blank cell stops the run; otherwise a blank is measured (`auto`)."""
    from_row: "RowFact | None" = Field(
        default=None, exclude_if=lambda r: r is None)
    """Read off the row rather than stated in a column of its own (#466): true where the row
    gives `column`, its input's second file."""
    auto: bool = Field(default=False, exclude_if=lambda auto: not auto)
    """A step the build added measures the fact where the cell is blank or says `auto`."""
    describes: TypeId
    """The input whose row carries it: its channel's `meta` gets the value."""
    meta: list[MetaKeyOf]
    why: Why


class Channel(BaseModel):
    """External pipeline input, including its expression, grain, metadata, and test data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: ChannelName
    """Unique channel identity used by step inputs and generated workflow variables."""
    param: NfIdentifier
    """Input parameter name used as params.<param>; independent of the channel name."""
    why: "Why | None" = None
    """Reason for an explicit grain override; None when the type's grain is used."""

    grain: Grain = Grain.SAMPLE
    """Whether the input is one item for the study or one per sample."""

    columns: list[PortName] = Field(default_factory=list)
    """Column names used when this channel is supplied through a samplesheet."""

    type_id: TypeId
    params: list[PortName] = Field(default_factory=list)
    """Parameter names referenced by expression; validated against its text."""
    expression: GroovyExpression
    """Groovy expression that constructs the input channel."""
    meta: list[MetaEntry] = Field(default_factory=list)
    test_data: list[TestDataRef] = Field(default_factory=list)
    """Public example inputs used by the test profile, represented as a list."""

    units: bool = Field(default=False, exclude_if=lambda units: not units)
    """A sample may span several rows of this input, such as its lanes (#466): the samplesheet
    takes a `unit` column, and each sample's rows are merged before anything reads them."""

    optional: bool = Field(default=False, exclude_if=lambda optional: not optional)
    """Each run may supply this input or leave it empty (#460). True only when every step it
    feeds has it as an optional input."""
    absent_width: int = Field(default=0, exclude_if=lambda width: not width)
    meta_at_run: list[MetaAtRun] = Field(default_factory=list, exclude_if=lambda m: not m)
    """Facts the run measures on this input and joins into its `meta` (#217): the step that
    measures each, and the key a run-time setting reads."""
    """The empty tuple's width passed when a run leaves this input empty."""

    @model_validator(mode="after")
    def _optional_says_its_placeholder(self) -> "Channel":
        if self.optional and self.absent_width < 1:
            raise ValueError(f"optional channel {self.name} has no absent_width")
        return self

    @model_validator(mode="after")
    def _params_match_the_expression(self) -> "Channel":
        """Require params to match the parameter references extracted from expression (MD0211)."""
        referenced = extract_param_refs(self.expression)
        if sorted(self.params) != referenced:
            raise ValueError(
                coded("MD0211", f"channel {self.type_id} declares params {sorted(self.params)} but "
                f"its expression references {referenced}. `params:` names what `expression:` "
                f"reads; edit whichever of the two is wrong.")
            )
        return self


# ---------------- MODELS: BUILD PROVENANCE ----------------


class RegistryProvenance(BaseModel):
    """Registry layer fingerprints, displaced declarations, and unverified contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layers: list[LockedLayer] = Field(default_factory=list)
    displaced: list[Displacement] = Field(default_factory=list)
    """Declarations superseded by higher-priority registry layers."""
    unverified: list[ContractId] = Field(default_factory=list)



class RowFact(StrEnum):
    """A fact read off a samplesheet row rather than stated in a column (#466)."""

    SECOND_FILE_PRESENT = "second_file_present"
    """True where the row gives its input's second file: paired-end reads."""


class AiPoint(StrEnum):
    """Named AI integration points recorded in pipeline provenance."""

    PROMPT = "prompt"
    """Interpret the authoring conversation to produce a goal."""
    TIER_4 = "tier-4"
    """Help resolve an ambiguity requiring review."""
    REPAIR = "repair"
    """Help repair a pipeline after compilation or gate failure."""
    CHARACTERISE = "characterise"
    """Read sample excerpts to identify declared types, states, and measurements."""


class AiProvenance(BaseModel):
    """Record which AI integration points were available and which were used.

    None means the information was not recorded. An empty list explicitly
    records that no points were available or used. These are caller-supplied
    records; the model does not independently observe model calls.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    available: list[AiPoint] | None = None
    """AI points configured for this build; None if unrecorded, [] if none."""
    used: list[AiPoint] | None = None
    """AI points reported as consulted; None if unrecorded, [] if none."""


# ---------------- PIPELINE ----------------


class Pipeline(EgressPayload):
    """Saved pipeline model used for emission, upgrades, and publication.

    Contains the materialised workflow details alongside the goal, decisions,
    and provenance. Inherits rejection of unknown fields and field reassignment
    from EgressPayload. Nested collections are not deeply immutable.
    """

    # ---------------- SCHEMA VERSION ----------------

    @model_validator(mode="before")
    @classmethod
    def _this_version_only(cls, data: object) -> object:
        """Refuse a file written under another schema before its fields are read.

        Until v0.1.0 no older version is carried (no upgraders): an older file is rebuilt from
        its intent and facts. Checked first, so the reader gets this sentence rather than a
        complaint about a field the older shape had (MD0207).
        """
        if isinstance(data, dict) and data.get("version", SCHEMA_VERSION) != SCHEMA_VERSION:
            version = data.get("version")
            raise ValueError(coded(
                "MD0207",
                f"this pipeline.yml declares version {version}, and this Mendel reads version "
                f"{SCHEMA_VERSION} only. "
                + ("Upgrade Mendel; do not edit the version down."
                   if isinstance(version, int) and version > SCHEMA_VERSION
                   else "Rebuild it: copy its intent and facts into a starter and run "
                        "`mendel build <starter>`.")))
        return data

    # ---------------- FIELDS ----------------

    version: int = SCHEMA_VERSION
    """Artifact schema version, defaulting to SCHEMA_VERSION."""

    intent: Intent
    """What is wanted. With `facts`, the input `upgrade` re-resolves; emission reads the steps."""
    facts: Facts
    """What is known about the data, each measurement with its source; no person's words."""
    registry: RegistryProvenance = Field(default_factory=RegistryProvenance)
    ai: AiProvenance = Field(default_factory=AiProvenance)
    """Recorded AI availability and usage for this build."""
    steps: list[Step] = Field(default_factory=list)
    confirms: list[Confirm] = Field(default_factory=list, exclude_if=lambda c: not c)
    """Estimates the build rested on, measured again over all the data in the run, each with
    the decisions that used it: what the run's reading of the facts is compared against."""
    sheet_facts: list[SheetFact] = Field(default_factory=list, exclude_if=lambda f: not f)
    """Facts each sample's samplesheet row states (#466), sorted by column."""
    channels: list[Channel] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    emitted: Emitted | None = None
    """Generated-file digests and their source artifact digest; None when unrecorded."""
    gate: Gate | None = None
    """Strongest validation gate recorded as passed; None when unrecorded."""

    input_form: InputForm = InputForm.DIRECT
    """Direct parameter inputs or a samplesheet.

    Materialisation selects a samplesheet for multiple sample-scoped channels.
    Validation requires a samplesheet to have at least two such channels and
    rejects channels sharing an input parameter.
    """

    @property
    def goal(self) -> Goal:
        """Project the stored intent and facts back into the resolver's input."""
        return Goal.of(self.intent, self.facts)

    # ---------------- VALIDATION ----------------

    def _validate_channels(self) -> None:
        """Reject ambiguous channel identities, references, and input forms."""
        names = [channel.name for channel in self.channels]
        repeated = _duplicates(names)
        if repeated:
            raise ValueError(
                coded(
                    "MD0226",
                    f"two channels share the name {', '.join(repeated)}. A channel name is what "
                    f"`inputs[].channel` points at and what becomes `ch_{repeated[0]}` in the "
                    f"workflow, so a duplicate feeds two ports from one channel and drops the "
                    f"other. `mendel explain MD0226`.",
                )
            )
        declared = set(names)
        dangling = sorted(
            {
                f"{step.id}.{item.port} -> {item.channel}"
                for step in self.steps
                for item in step.inputs
                if item.channel is not None and item.channel not in declared
            }
        )
        if dangling:
            raise ValueError(
                coded(
                    "MD0227",
                    f"{dangling[0]} names a channel this pipeline does not declare. "
                    f"{len(dangling)} port(s) in total. A port reads a channel by NAME since "
                    f"schema 6 — by type before it — so a file hand-edited from an older one "
                    f"names `annotation.gtf` where it now means `gtf`. `mendel explain MD0227`.",
                )
            )
        per_sample = [c.name for c in self.channels if c.grain is Grain.SAMPLE]
        wants_table = self.input_form is InputForm.SAMPLESHEET
        # Every fact said to vary, and every key a step groups by, has its column (#466).
        varies = set(self.intent.constraints.varies) | {
            i.by for s in self.steps for i in s.inputs if i.by is not None} | {
            c.fact for s in self.steps for i in s.inputs for c in i.select} | {
            a.key for s in self.steps for a in s.call if a.key is not None}
        if varies != {f.measurement for f in self.sheet_facts}:
            raise ValueError(coded(
                "MD0335", f"the facts said to differ between samples "
                f"({', '.join(sorted(varies)) or 'none'}) are not this pipeline's samplesheet "
                f"columns ({', '.join(sorted(f.column for f in self.sheet_facts)) or 'none'}); "
                "rebuild it from its goal — `mendel explain MD0335`."))
        if self.sheet_facts and not wants_table:
            raise ValueError(coded(
                "MD0335", "this pipeline has samplesheet facts and takes no samplesheet; a "
                "fact that differs between samples needs a row to carry it."))
        lanes = any(c.units for c in self.channels)
        if lanes and not wants_table:
            raise ValueError(coded(
                "MD0340", "an input whose rows may repeat a sample needs a samplesheet: only a "
                "row says which lane it is — `mendel explain MD0340`."))
        if wants_table and len(per_sample) < 2 and not self.sheet_facts and not lanes:
            raise ValueError(
                coded(
                    "MD0229",
                    f"this pipeline says its input is a samplesheet and has "
                    f"{len(per_sample)} sample-scoped channel(s): "
                    f"{', '.join(per_sample) or '(none)'}.\n"
                    f"  A samplesheet's columns are its sample-scoped channels, so one of them "
                    f"is a table with one column — which is a glob written the long way.",
                )
            )
        taken = {"sample", "id", *(c for ch in self.channels for c in ch.columns)}
        clash = sorted(f.column for f in self.sheet_facts
                       if f.column in taken and f.from_row is None)
        if clash:
            raise ValueError(coded(
                "MD0335", f"samplesheet column {clash[0]} is both a fact and a file or the "
                "sample's id; rename the channel."))
        claimed: dict[str, list[str]] = {}
        for channel in self.channels:
            claimed.setdefault(channel.param, []).append(channel.name)
        twice = sorted((param, names) for param, names in claimed.items() if len(names) > 1)
        if twice:
            param, names = twice[0]
            raise ValueError(
                coded(
                    "MD0229",
                    f"channels {', '.join(sorted(names))} all read `params.{param}`.\n"
                    f"  A laboratory supplies one path and every one of them reads it, which "
                    f"is the silent merge this schema exists to make impossible.",
                )
            )

    @model_validator(mode="after")
    def _readable_and_unambiguous(self) -> "Pipeline":
        """Check artifact consistency after nested models have validated.

        Rejects unsupported versions, duplicate identities, dangling external channel
        references, contradictory AI claims, invalid samplesheet use, metadata
        collisions, and inconsistent parameter overrides or human-source claims.
        """
        repeated = _duplicates(step.id for step in self.steps)
        if repeated:
            raise ValueError(
                coded("MD0212", f"two steps share the id {', '.join(repeated)}. A step id is what "
                f"`inputs[].source` points at, so a duplicate makes the wiring ambiguous.")
            )
        # Unrecorded availability (None) makes no claim; [] explicitly rules out AI use.
        if self.ai.available == []:
            claimed = sorted(
                {
                    f"{step.id}.{setting.name}"
                    for step in self.steps
                    for setting in step.settings
                    if setting.why.source is ValueSource.MODEL
                }
                | {
                    f"{step.id}.premise.{premise.id}"
                    for step in self.steps
                    for premise in step.why.premise
                    if premise.origin is PremiseOrigin.MODEL_READ
                }
                | {
                    f"{channel.name}.meta.{entry.key}"
                    for channel in self.channels
                    for entry in channel.meta
                    if entry.why.source is ValueSource.MODEL
                }
            )
            if claimed:
                raise ValueError(
                    coded(
                        "MD0225",
                        f"{', '.join(claimed)} record that a model settled them, and this "
                        "build records that no AI point was available. One of the two is false. "
                    "`ai.available: []` means nothing was wired to a model, so nothing could "
                    "have been consulted.")
                )
        self._validate_channels()

        measured = {entry.key for channel in self.channels for entry in channel.meta}
        for step in self.steps:
            shadow = sorted(
                s.name
                for s in step.settings
                if s.via is Via.META and s.name in measured
            )
            if shadow:
                raise ValueError(
                    coded("MD0208", f"step {step.id} routes {', '.join(shadow)} to meta, but a "
                    f"measurement already writes {shadow[0]} into the meta map — the setting "
                    f"would silently overwrite a measured fact. `mendel explain MD0208`.")
                )
        repeated = _duplicates(record.key for record in self.decisions)
        if repeated:
            raise ValueError(
                coded(
                    "MD0219",
                    f"two decision records share the key {repeated[0]}. A key names one "
                    f"decision; a duplicate is a corrupt file, and `ReplayResolver` would keep one "
                f"and drop the other's answer in silence. `mendel explain MD0219`.")
            )
        values = self._param_setting_values()
        for record in self.decisions:
            if getattr(record, "kind", None) is not DecisionKind.PARAM:
                continue
            override = record.human_override
            value = values.get(record.key)
            if override is not None and value is not None and override != value:
                raise ValueError(
                    coded(
                        "MD0218",
                        f"{record.key} is answered {value!r} in settings and {override!r} "
                        f"in its decision's human_override — one file, two answers, and emit and "
                    f"upgrade would read different ones. settings[].value is the writable one; "
                    f"remove the human_override or set it equal. `mendel explain MD0218`.")
                )

        # A human-source setting must have a recorded parameter override.
        overrides = {
            record.key: record.human_override
            for record in self.decisions
            if getattr(record, "kind", None) is DecisionKind.PARAM
        }
        for step in self.steps:
            for setting in step.settings:
                if setting.why.source is not ValueSource.HUMAN:
                    continue
                key = f"{step.id}.{setting.name}"
                if overrides.get(key) is None:
                    raise ValueError(
                        coded(
                            "MD0220",
                            f"{key} says source: human, but no decision records a person "
                            f"answering it — its human_override is null or absent. `source: human` "
                        f"clears the review, so it must be backed by the answer it claims.\n"
                        f"  Edit `settings[].value` and leave `source` alone: `upgrade` "
                        f"promotes the answer and sets `source: human` itself. Or restore the "
                        f"source that resolution gave it. `mendel explain MD0220`.")
                    )
        return self

    # ---------------- DECISION REPLAY ----------------

    def _param_setting_values(self) -> dict[str, ParamValue]:
        """Index saved parameter values by step_id.setting_name."""
        return {
            f"{step.id}.{setting.name}": setting.value
            for step in self.steps
            for setting in step.settings
        }

    def _param_setting_reasons(self) -> dict[str, str]:
        """Index saved parameter reasons by step_id.setting_name."""
        return {
            f"{step.id}.{setting.name}": setting.why.reason
            for step in self.steps
            for setting in step.settings
        }

    def replayable_decisions(self) -> list[DecisionRecord]:
        """Prepare decision records for re-resolution during upgrade.

        Promotes parameter values edited away from the chosen value into human
        overrides and carries edited reasons. Producer records already answered by
        goal pins are omitted. Returns copies for changed records.
        """
        values = self._param_setting_values()
        reasons = self._param_setting_reasons()
        goal_pins = {
            (f"producer:{pin.site.type_id}", pin.contract)
            for pin in self.goal.constraints.producers
        }
        replayable = []
        for record in self.decisions:
            value = values.get(record.key)
            if (
                getattr(record, "kind", None) is DecisionKind.PARAM
                and record.human_override is not None
                and reasons.get(record.key, "") not in ("", record.reason)
            ):
                replayable.append(
                    record.model_copy(
                        update={"override_reason": reasons[record.key]}
                    )
                )
            elif (
                getattr(record, "kind", None) is DecisionKind.PARAM
                and record.human_override is None
                and value is not None
                and value != record.chosen
            ):
                written = reasons.get(record.key, "")
                replayable.append(
                    record.model_copy(
                        update={
                            "human_override": value,
                            "override_reason": (
                                written if written != record.reason else ""
                            ),
                        }
                    )
                )
            elif (
                getattr(record, "kind", None) is DecisionKind.PRODUCER
                and (record.subject, record.human_override) in goal_pins
            ):
                continue
            else:
                replayable.append(record)
        return replayable

    # ---------------- DIGEST AND CONSTRUCTION ----------------

    def content_digest(self) -> str:
        """Hash the pipeline with emitted set to None, avoiding a self-referential digest."""
        return digest_of(self.model_copy(update={"emitted": None}))

    @classmethod
    def of(
        cls, ir, registry, vocab, measurements=None, layers=(), *, goal, ai=None, locators=None
    ) -> "Pipeline":
        """Build a fully materialised Pipeline by delegating to materialise.of()."""
        # Import locally because materialise imports these models.
        from comeni_core.artifact import materialise

        return materialise.of(
            ir, registry, vocab, measurements=measurements, layers=layers, goal=goal, ai=ai,
            locators=locators,
        )
