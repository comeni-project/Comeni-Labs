"""`pipeline.yml` — one artifact, every setting, every provenance.

Replaces `pipeline.ir.json`, `mendel.lock.yml` and `PublishBundle`'s on-disk form. A researcher
asking "what settings does this pipeline use, and why" read four files and had to know which of
four mechanisms carried each value; one of those mechanisms carried nothing at all.

Everything the emitter reads is **materialised** here, so `emit(pipeline)` takes one argument
and needs no registry. That is what lets a laboratory archive a validated pipeline and
regenerate its Nextflow years later without the registry it was built against — the part that
resolves differently as it changes.

Two rules govern what is in here, and they are converse:

- **Totality.** Every field of every type this replaces has a home, checked mechanically by
  `tests/test_pipeline_totality.py`. Three drafts of this schema dropped five fields between
  them, including the one the `sealed` profile depends on.
- **Productivity.** A field is embedded only if `emit` reads it, or it is provenance no later
  registry lookup recovers. Self-containment widens the publication door, and that widening was
  accepted on condition that nothing rides along.
"""

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.contract import ModuleContract
from comeni_core.decision import DecisionRecord
from comeni_core.egress import Emitted
from comeni_core.gates import Gate
from comeni_core.goal import Goal
from comeni_core.layered import Displacement
from comeni_core.lockfile import LockedLayer
from comeni_core.marks import (
    ContainerRef,
    ContractId,
    Digest,
    EdgeRef,
    Line,
    NfIdentifier,
    NfPath,
    NfTemplate,
    NodeId,
    ParamValue,
    PortName,
    StateName,
    TypeId,
)
from comeni_core.routes import ExtKey, Via
from comeni_core.tiers import Tier, ValueSource

__all__ = [
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


class Why(BaseModel):
    """Tier, who settled it, which layer, and the citation — in one place.

    This is the legibility the four-file split could not provide: a reader asking why a value
    is what it is gets the answer beside the value rather than by joining a decision record to
    a node by hand.
    """

    model_config = ConfigDict(extra="forbid")

    tier: Tier
    source: ValueSource
    reason: Line
    from_layer: str | None = None
    displaced_layer: str | None = None
    """Set when a lower layer offered something this one beat. A5, A15 — dropped by two drafts
    of this schema, which is why the totality test exists."""


class ModuleRef(BaseModel):
    """Which module, pinned. Replaces `LockedContract`, per step rather than in a side file."""

    model_config = ConfigDict(extra="forbid")

    contract_id: ContractId
    digest: Digest
    container: ContainerRef | None = None
    """The container as the contract declared it, tag and all.

    Carried rather than looked up: resolving a tag to an immutable digest needs a registry
    client and therefore the network, which `comeni-core` may not have — and the `sealed`
    profile's digests-required rule depends on this being recorded.
    """


class Setting(BaseModel):
    """One resolved value, and the route that carries it to the tool."""

    model_config = ConfigDict(extra="forbid")

    name: PortName
    value: ParamValue
    via: Via
    key: ExtKey | None = None
    template: NfTemplate | None = None
    why: Why


class MetaEntry(BaseModel):
    """One key in a channel's `meta` map. A record rather than a mapping, because a typed key
    does not prove a *declared* key."""

    model_config = ConfigDict(extra="forbid")

    key: NfIdentifier
    value: ParamValue


class CallArg(BaseModel):
    """One positional input of the process.

    Mirrors `NfInput`'s three shapes written out, with **no positional shorthand**: root G's
    rule is that a file reads one way, and `call:` is where a second reading produces a
    silently miswired pipeline rather than a parse error.
    """

    model_config = ConfigDict(extra="forbid")

    ports: list[PortName] = Field(default_factory=list)
    literal: ParamValue = None
    empty_width: int | None = None
    why: Why | None = None
    """A positional literal is as much a decision as a flag is. `NfInput.empty` already
    requires a `because`; this carries the whole provenance instead, because "every choice
    carries its provenance" cannot have an exception for the one route that had no artifact."""


class StepInput(BaseModel):
    """Where one consumed port comes from. An `IREdge`, keyed under its consumer.

    Lossless, since an edge has exactly one consuming port — and it makes "where does this
    step's GTF come from" answerable without scanning a separate list, which is what root D
    found `diff_ir` was not even comparing.
    """

    model_config = ConfigDict(extra="forbid")

    port: PortName
    source: EdgeRef
    """`<node>.<port>`, or `channel:<type_id>` for something entering the pipeline."""
    states: list[StateName] = Field(default_factory=list)
    """Sorted at materialisation. `IREdge.states` is a `frozenset`, and a set has no stable
    order — `digest_of` hashes the JSON, so this must not be one."""


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    module: ModuleRef
    process: NfIdentifier
    include: NfPath
    why: Why
    inputs: list[StepInput] = Field(default_factory=list)
    call: list[CallArg] = Field(default_factory=list)
    settings: list[Setting] = Field(default_factory=list)


class Channel(BaseModel):
    """What the laboratory supplies, and the measured facts that ride with it."""

    model_config = ConfigDict(extra="forbid")

    type_id: TypeId
    params: list[PortName] = Field(default_factory=list)
    """Which `params.<name>` the expression references. Plural: one expression may reference
    several, and the shipped registry being 1:1 today is not a schema guarantee.

    Stored *and* derivable, deliberately. Taking a regex over arbitrary Groovy out of the
    emitter is much of what materialisation buys, so the duplication is accepted and then
    checked — `MD0211` refuses a hand-edited file where the two have diverged.
    """
    expression: str
    """The one unbounded-Groovy field in the file, by design. A type declares how it arrives;
    the compiler has no built-in idea what a FASTQ is."""
    meta: list[MetaEntry] = Field(default_factory=list)


class RegistryProvenance(BaseModel):
    """Which registry built this. **Provenance, not a dependency of `emit`.**"""

    model_config = ConfigDict(extra="forbid")

    layers: list[LockedLayer] = Field(default_factory=list)
    displaced: list[Displacement] = Field(default_factory=list)
    """What an overlay replaced, across every kind of declared data. Wider than the
    `shadowed` it replaced, which covered contracts alone."""
    unverified: list[ContractId] = Field(default_factory=list)


class Pipeline(BaseModel):
    """The pipeline. Read this; edit this; `mendel emit` rebuilds the Nextflow from it."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    goal: Goal = Field(default_factory=Goal)
    """What was asked for. **Inert to `emit`** — it is input to *resolution*, and the facts
    emission needs are already materialised into `channels[].meta`. Editing it takes effect on
    `mendel upgrade`, and the emitted file says so in a comment."""
    registry: RegistryProvenance = Field(default_factory=RegistryProvenance)
    steps: list[Step] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    emitted: Emitted | None = None
    """Digests of what was written. `None` means no evidence, exactly as `gate: None` does."""
    gate: Gate | None = None
    """The strongest gate this pipeline actually passed. The verdict comes from the artifact."""

    @classmethod
    def of(cls, ir, registry, vocab, measurements=None, layers=()) -> "Pipeline":
        """The **only** validating constructor.

        Enforced by `tests/test_construction.py`, the way `MeasurementRegistry.profile()`
        already is — that guard exists because deleting one call let `profile: {sample_name:
        ...}` build cleanly. Same reasoning: materialisation must not be bypassable by a caller
        assembling a `Pipeline` by hand with the contract-derived fields left empty.

        Takes a registry as an *argument* and keeps none of it. `registry.py` carries a mapping
        and says it is legal because `Registry` is not payload-reachable; holding one here would
        silently end that.
        """
        from comeni_core.lockfile import Lockfile

        lock = Lockfile.of(ir, registry, layers)
        pinned = {entry.id: entry for entry in lock.contracts}

        steps = []
        for node in ir.nodes:
            contract = registry.get(node.contract_id)
            entry = pinned[node.contract_id]
            steps.append(
                Step(
                    id=node.id,
                    module=ModuleRef(
                        contract_id=node.contract_id,
                        digest=entry.digest,
                        container=entry.container,
                    ),
                    process=contract.nf_process,
                    include=contract.nf_include,
                    why=_why(node.selection),
                    inputs=_inputs(ir, node),
                    call=_call(contract),
                    settings=_settings(node, contract),
                )
            )

        return cls(
            goal=Goal(profile=ir.profile),
            registry=RegistryProvenance(
                layers=list(lock.layers),
                displaced=list(ir.displaced),
                unverified=list(ir.unverified),
            ),
            steps=steps,
            channels=_channels(ir, registry, vocab, measurements),
            decisions=list(ir.decisions),
        )


def _why(value) -> Why:
    """A `ResolvedValue` seen as provenance. Field for field, no interpretation."""
    return Why(
        tier=value.tier,
        source=value.source,
        reason=value.reason,
        from_layer=value.from_layer,
        displaced_layer=value.displaced_layer,
    )


def _settings(node, contract: ModuleContract) -> list[Setting]:
    """Resolved values, each carrying the route its contract declared for it.

    Sorted by name. With one setting the order is unobservable, which is exactly why a test
    with one setting cannot see a sort bug — and `ext.args` composition depends on this being
    deterministic for byte-identical emission.
    """
    routes = {param.name: param for param in contract.params}
    return [
        Setting(
            name=binding.name,
            value=binding.value.value,
            via=routes[binding.name].via,
            key=routes[binding.name].key,
            template=routes[binding.name].template,
            why=_why(binding.value),
        )
        for binding in sorted(node.params, key=lambda b: b.name)
        if binding.name in routes
    ]


def _call(contract: ModuleContract) -> list[CallArg]:
    """The process's positional inputs, materialised from `nf_inputs`.

    A positional literal is a tier-1 decision that appeared in no artifact at all before this —
    `STAR_ALIGN(reads, index, gtf, false)` and nothing recorded that `false` or why.
    """
    return [
        CallArg(
            ports=list(spec.ports),
            literal=spec.literal,
            empty_width=spec.empty or None,
            why=(
                Why(
                    tier=Tier.STRUCTURAL,
                    source=ValueSource.RESOLVER,
                    reason=spec.because,
                )
                if spec.because
                else None
            ),
        )
        for spec in contract.input_signature()
    ]


def _inputs(ir, node) -> list[StepInput]:
    """Every consumed port and where it comes from, keyed under the consumer."""
    return [
        StepInput(
            port=edge.to_port,
            source=f"{edge.from_node}.{edge.from_port}",
            states=sorted(edge.states),
        )
        for edge in ir.edges
        if edge.to_node == node.id
    ]


def _channels(ir, registry, vocab, measurements) -> list[Channel]:
    """Every type consumed but not produced inside the pipeline, and how it arrives.

    The `meta` entries are the measured facts a module reads — `single_end`, `strandedness` —
    materialised here so emission needs no measurement registry. Sorted, because a set or a
    dict order reaching a digest is how a lockfile becomes spuriously dirty.
    """
    fed = {(edge.to_node, edge.to_port) for edge in ir.edges}
    needed: dict[str, None] = {}
    for node in ir.nodes:
        for port in registry.get(node.contract_id).consumes:
            if (node.id, port.name) not in fed:
                needed[port.type_id] = None

    channels = []
    for type_id in sorted(needed):
        entries = measurements.meta_for(type_id, ir.profile) if measurements else {}
        channels.append(
            Channel(
                type_id=type_id,
                params=[],
                expression=vocab.entry_channels.get(type_id, ""),
                meta=[MetaEntry(key=key, value=entries[key]) for key in sorted(entries)],
            )
        )
    return channels
