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
from comeni_core.diagnostics import coded
from comeni_core.egress.base import EgressPayload
from comeni_core.goal.asked import Facts, Goal, Intent
from comeni_core.goal.premise import PremiseRecord
from comeni_core.plan.decision import DecisionKind, DecisionRecord
from comeni_core.plan.tiers import (
    InputForm,
    PremiseOrigin,
    ReviewLevel,
    Scope,
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
    NfIdentifier,
    NfPath,
    NfTemplate,
    NodeId,
    ParamValue,
    PortName,
    StateName,
    TestDataRef,
    TypeId,
    substitutable,
)
from comeni_core.spell.routes import TEMPLATED, ExtKey, Join, Via

# ---------------- CONSTANTS ----------------

SCHEMA_VERSION = 8
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
    why: Why | None = None
    """Provenance for the argument, when supplied."""


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

    states: list[StateName] = Field(default_factory=list)
    """States carried by the upstream connection, sorted during materialisation."""

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "StepInput":
        """Require exactly one upstream source or external channel (MD0215)."""
        if (self.source is None) == (self.channel is None):
            raise ValueError(
                coded("MD0215", f"input {self.port} must name exactly one of `source` or `channel`")
            )
        return self


# ---------------- MODELS: STEPS AND CHANNELS ----------------


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


class Channel(BaseModel):
    """External pipeline input, including its expression, scope, metadata, and test data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: ChannelName
    """Unique channel identity used by step inputs and generated workflow variables."""
    param: NfIdentifier
    """Input parameter name used as params.<param>; independent of the channel name."""
    why: "Why | None" = None
    """Reason for an explicit scope override; None when the default scope is used."""

    scope: Scope = Scope.SAMPLE
    """Whether the input is shared across the run or supplied per sample."""

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
        """The resolver's input, projected from `intent` and `facts` (spec §8.1)."""
        return Goal.of(self.intent, self.facts)

    # ---------------- VALIDATION ----------------

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
        per_sample = [c.name for c in self.channels if c.scope is Scope.SAMPLE]
        wants_table = self.input_form is InputForm.SAMPLESHEET
        if wants_table and len(per_sample) < 2:
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
        # Each external channel must have its own input parameter.
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
