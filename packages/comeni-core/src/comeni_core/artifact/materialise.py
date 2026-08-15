"""Building a `Pipeline` from a resolved IR. The one direction that reads the registry.

Split out of `pipeline.py` because that file was doing three jobs — what the artifact *is*, how
it is built, and what a file must satisfy to be read back — and only this one needs a registry,
a vocabulary and a measurement set. A reader asking "where does `ext_args` get its premise" was
reading 1,116 lines to find out.

**Materialisation is why `emit` takes one argument.** Everything the emitter would otherwise
look up — process names, include paths, entry-channel expressions, the measured facts that ride
in `meta` — is copied onto the `Pipeline` here. That is what lets a laboratory archive a
validated pipeline and rebuild its Nextflow years later with no registry and no network.

`Pipeline.of` stays on `Pipeline` and delegates here: `tests/test_construction.py` asserts it is
the only validating constructor, and that guard is about the entry point rather than the code
behind it.
"""

from comeni_core.artifact.load import _param_refs
from comeni_core.artifact.lockfile import Lockfile
from comeni_core.artifact.pipeline import (
    AiProvenance,
    CallArg,
    Channel,
    ExtArgs,
    MetaEntry,
    ModuleRef,
    Pipeline,
    RegistryProvenance,
    Setting,
    Step,
    StepInput,
    Why,
    _no_flags_why,
)
from comeni_core.declared.contract import ModuleContract
from comeni_core.diagnostics import coded
from comeni_core.plan.tiers import Tier, ValueSource


def of(ir, registry, vocab, measurements=None, layers=(), *, goal) -> Pipeline:
    """The **only** validating constructor.

    `goal` is **keyword-only and required**, with no default. The first version defaulted
    it to `Goal(profile=ir.profile)`, which type-checked, round-tripped, passed the
    totality test — that test asks whether a field has a *home*, and it did — and wrote
    `have: []`, `want: []` into every pipeline file. A default is how a field comes to be
    present and empty, and this file's whole claim is that it records what was asked for.

    Enforced by `tests/test_construction.py`, the way `MeasurementRegistry.profile()`
    already is — that guard exists because deleting one call let `profile: {sample_name:
    ...}` build cleanly. Same reasoning: materialisation must not be bypassable by a caller
    assembling a `Pipeline` by hand with the contract-derived fields left empty.

    Takes a registry as an *argument* and keeps none of it. `registry.py` carries a mapping
    and says it is legal because `Registry` is not payload-reachable; holding one here would
    silently end that.
    """

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
                presence=_why(node.presence),
                ext_args=_ext_args(contract),
                inputs=_inputs(ir, node, contract),
                call=_call(contract),
                settings=_settings(node, contract),
            )
        )

    return Pipeline(
        # The *resolved* profile, not the one the goal file declared: `resolve()` routes
        # every profile through `MeasurementRegistry.profile()`, the one validating
        # constructor, and what survived that is what the pipeline was built against.
        goal=goal.model_copy(update={"profile": ir.profile}),
        registry=RegistryProvenance(
            layers=list(lock.layers),
            displaced=list(ir.displaced),
            unverified=list(ir.unverified),
        ),
        # **Empty lists are a measurement, not a placeholder.** Through Plan 1 there is no
        # AI path at all — `mendel-ai` does not exist and nothing implements the resolver
        # ports — so no declared AI point had an adapter and none answered. Writing `[]`
        # rather than leaving the field defaulted is the difference between the artifact
        # *stating* that no model was consulted and merely not mentioning it, which is A130.
        # Plan 2 fills these from what was actually configured. Do not "fix" them to a
        # default: `None` means a file written before the question existed.
        ai=AiProvenance(available=[], used=[]),
        steps=steps,
        channels=_channels(ir, registry, vocab, measurements),
        decisions=list(ir.decisions),
    )



def _ext_args(contract: ModuleContract) -> ExtArgs:
    """A contract's baseline flags, with the reason it declared for them.

    `ModuleContract.ext_args` accepts a bare string as well as a record, so this is where the
    two forms become one shape. A contract that states only the flags gets a reason saying so
    rather than an invented one — the gap stays visible and greppable. A82.
    """
    declared = contract.ext_args
    if isinstance(declared, str):
        return ExtArgs.model_validate(declared) if declared else ExtArgs(why=_no_flags_why())
    return ExtArgs(
        template=declared.template,
        why=Why(
            tier=Tier.STRUCTURAL,
            source=ValueSource.RESOLVER,
            reason=declared.because or "declared by the contract with no stated reason",
            for_value=declared.template,
        ),
    )


def _meta_entry(key: str, measurement, value, profile) -> MetaEntry:
    """One `meta` key, with where its value came from. A80.

    The provenance is the profile's, not this function's invention: `Measured.source` already
    separates a profiling run that named itself from a number somebody typed into a goal file,
    and `Measured.by` already names the contract that produced it. Both stopped at the goal.

    Tier 1 throughout, and that is not a cop-out. A measurement is not a *decision* — nothing
    chose it, the data either says this or it does not — so "no choice exists" is the honest
    tier. What varies is `source`, and that is the field a reader and `sealed` both need.
    """
    entry = next(
        (m for m in profile.measurements if m.measurement == measurement.id), None
    )
    source = entry.source if entry is not None else ValueSource.GOAL
    by = entry.by if entry is not None else None

    if source is ValueSource.MEASURED:
        reason = f"measured by {by}" if by else "measured"
    else:
        reason = "asserted in the goal; no profiling run established it"
    if measurement.cite:
        reason = f"{reason}; {measurement.cite}"
    if measurement.description:
        reason = f"{reason} — {measurement.description}"

    return MetaEntry(
        key=key,
        value=value,
        why=Why(
            tier=Tier.STRUCTURAL,
            source=source,
            reason=reason,
            for_value=value,
        ),
    )


def _why(value) -> Why:
    """A `ResolvedValue` seen as provenance. Field for field, no interpretation.

    `for_value` is the one field that is not simply copied, and it needs no interpretation
    either: the reason was written about the value it arrived with, so recording that value
    beside it is a statement of fact at the moment it is true. Everything after this point can
    only make it false, which is exactly what `MD0223` is for. A104.
    """
    return Why(
        tier=value.tier,
        source=value.source,
        reason=value.reason,
        premise=list(value.premise),
        axis_reason=value.axis_reason,
        for_value=value.value,
        from_layer=value.from_layer,
        displaced_layer=value.displaced_layer,
    )


def _settings(node, contract: ModuleContract) -> list[Setting]:
    """Resolved values, each carrying the route its contract declared for it.

    Sorted by name. With one setting the order is unobservable, which is exactly why a test
    with one setting cannot see a sort bug — and `ext.args` composition depends on this being
    deterministic for byte-identical emission.

    **A binding whose contract declares no such param refuses**, and used to be dropped in
    silence — the orphan case one level below `MD0203`, and found by a guard that passed for
    the wrong reason: an A27 test smuggled prose through a `samtools/sort` binding, and that
    contract declares `params: []`, so nothing was being tested.

    Resolution cannot produce one, since it sets parameters *from* `contract.params`. So this
    takes a deserialised or hand-built IR — and there, refusing is right: a value with no
    route is a value the emitted Nextflow will not contain, described in a file whose whole
    claim is that it records every value.
    """
    routes = {param.name: param for param in contract.params}
    orphaned = sorted({b.name for b in node.params} - set(routes))
    if orphaned:
        raise ValueError(
            coded("MD0216", f"{node.id} carries resolved value(s) for {', '.join(orphaned)}, which "
            f"{contract.id} does not declare as a parameter, so nothing would carry them to "
            f"the tool. `mendel explain MD0216`.")
        )
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
            from_setting=spec.param or None,
            join=spec.join,
            why=(
                Why(
                    tier=Tier.STRUCTURAL,
                    source=ValueSource.RESOLVER,
                    reason=spec.because,
                    for_value=spec.literal,
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
        sourced = measurements.meta_sources_for(type_id, ir.profile) if measurements else {}
        expression = vocab.entry_channels.get(type_id) or _default_entry(type_id)
        declared = vocab.test_data.get(type_id)
        channels.append(
            Channel(
                type_id=type_id,
                params=_param_refs(expression),
                expression=expression,
                meta=[
                    _meta_entry(key, *sourced[key], ir.profile) for key in sorted(sourced)
                ],
                test_data=[declared] if isinstance(declared, str) else list(declared or []),
            )
        )
    return channels


def _default_entry(type_id: str) -> str:
    """How a type arrives when its vocabulary declares no `entry_channel`.

    Materialised here rather than left to the emitter, because emission must not need the
    vocabulary. Deleting this while narrowing `emit`'s signature emitted `ch_genome_index_star =`
    with nothing after it — valid-looking Groovy that dies at parse, caught by reading the
    golden diff rather than by regenerating it and moving on.
    """
    param = type_id.rsplit(".", 1)[-1]
    return f"Channel.fromPath(params.{param}, checkIfExists: true).map {{ f -> [ [:], f ] }}"
