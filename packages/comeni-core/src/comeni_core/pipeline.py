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

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    source: EdgeRef | None = None
    """`<node>.<port>` when an upstream step produces it.

    Two fields rather than one string with two shapes. The spec drafted this as a single
    `from:` carrying either `trimgalore.reads` or `channel:annotation.gtf`, and that cannot be
    an `EdgeRef` — its validator requires two Groovy identifiers, which `channel:annotation.gtf`
    is not. Encoding a union in a string is also root G's problem: a field that reads two ways.
    """
    channel: TypeId | None = None
    """The entry channel this port reads, when nothing upstream produces it."""
    states: list[StateName] = Field(default_factory=list)

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "StepInput":
        if (self.source is None) == (self.channel is None):
            raise ValueError(
                f"MD0212: input {self.port} must name exactly one of `source` or `channel`"
            )
        return self
    """Sorted at materialisation. `IREdge.states` is a `frozenset`, and a set has no stable
    order — `digest_of` hashes the JSON, so this must not be one."""


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NodeId
    module: ModuleRef
    process: NfIdentifier
    include: NfPath
    why: Why
    ext_args: NfTemplate = ""
    """Flags the module always needs, from its contract — `--readFilesCommand zcat` because
    TrimGalore emits `.fq.gz` and STAR cannot read gzip.

    Not a `Setting`: nothing resolved it and there is no decision behind it, so giving it a
    `why` would invent provenance. Carried rather than looked up because emission must not
    need the registry, and composed *before* the resolved settings so a contract's baseline
    cannot be reordered by a value someone answered.
    """
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
    test_data: list[str] = Field(default_factory=list)
    """A small public example of this type, for the `test` profile. Pinned to a commit in the
    vocabulary, never a branch — a dataset that moves is one you cannot compare a result against
    next year. Always a list here even when the vocabulary declares one string, because a schema
    that is sometimes a string and sometimes a list reads two ways."""


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
                    ext_args=contract.ext_args,
                    inputs=_inputs(ir, node, contract),
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


def _inputs(ir, node, contract) -> list[StepInput]:
    """Every consumed port and where it comes from, keyed under the consumer.

    Entry ports are listed too. Without them a `Step` would not know which channel a port
    reads, and emission would have to ask the registry for `consumes[].type_id` — which is
    exactly the dependency materialisation removes.
    """
    fed = {
        edge.to_port: edge for edge in ir.edges if edge.to_node == node.id
    }
    inputs = []
    for port in contract.consumes:
        edge = fed.get(port.name)
        if edge is not None:
            inputs.append(
                StepInput(
                    port=port.name,
                    source=f"{edge.from_node}.{edge.from_port}",
                    states=sorted(edge.states),
                )
            )
        else:
            inputs.append(StepInput(port=port.name, channel=port.type_id))
    return inputs


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
        expression = vocab.entry_channels.get(type_id) or _default_entry(type_id)
        declared = vocab.test_data.get(type_id)
        channels.append(
            Channel(
                type_id=type_id,
                params=_param_refs(expression),
                expression=expression,
                meta=[MetaEntry(key=key, value=entries[key]) for key in sorted(entries)],
                test_data=[declared] if isinstance(declared, str) else list(declared or []),
            )
        )
    return channels


_IDENT_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "_"
)


def _param_refs(expression: str) -> list[str]:
    """Every `params.<name>` an entry-channel expression references, sorted and deduplicated.

    Scanned by hand rather than with `re`, which is not on `comeni-core`'s purity allowlist —
    `_is_identifier` refused to widen it for a character class and this is the same trade.
    `mendel_compiler.emit.entry_params` does the same job with a regex because that package
    already allows one; the two must agree, which is what `MD0211` checks.

    Plural because one expression may reference several: `fastq.reads` names `params.input`
    three times today, and the shipped registry being 1:1 is not a schema guarantee.
    """
    found: set[str] = set()
    marker = "params."
    start = expression.find(marker)
    while start != -1:
        cursor = start + len(marker)
        end = cursor
        while end < len(expression) and expression[end] in _IDENT_CHARS:
            end += 1
        if end > cursor:
            found.add(expression[cursor:end])
        start = expression.find(marker, end)
    return sorted(found)


def _default_entry(type_id: str) -> str:
    """How a type arrives when its vocabulary declares no `entry_channel`.

    Materialised here rather than left to the emitter, because emission must not need the
    vocabulary. Deleting this while narrowing `emit`'s signature emitted `ch_genome_index_star =`
    with nothing after it — valid-looking Groovy that dies at parse, caught by reading the
    golden diff rather than by regenerating it and moving on.
    """
    param = type_id.rsplit(".", 1)[-1]
    return f"Channel.fromPath(params.{param}, checkIfExists: true).map {{ f -> [ [:], f ] }}"
