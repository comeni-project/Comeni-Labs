"""Build the saved Pipeline model from a resolved plan and registry declarations.

Called through Pipeline.of(). Copies the details needed for Nextflow emission
into the artifact: module references, settings, wiring, input channels, and
provenance. The returned model can be emitted without reading the registry.

Complexity: lookup and assembly work is expected O(n) in the combined input
and output size, including expanded ports, settings, metadata, and expressions.
Edges, channel assignments, and profile measurements are indexed once;
measurement declarations are scanned once for all requested input types.
Deterministic sorting adds up to O(n log n). Dependency fingerprinting also
sorts registry file names and reads the relevant file and contract bytes.
Pydantic model validation has additional costs; this is not an O(n) guarantee
for the complete call. The indexes require O(n) additional memory.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

from comeni_core.artifact.lockfile import Locator, Lockfile
from comeni_core.artifact.param_refs import extract_param_refs
from comeni_core.artifact.pipeline import (
    AiPoint,
    AiProvenance,
    CallArg,
    Channel,
    ExtArgs,
    MetaEntry,
    ModuleRef,
    Pipeline,
    RegistryProvenance,
    RunRule,
    Setting,
    Step,
    StepInput,
    Why,
    _no_flags_why,
)
from comeni_core.declared.constraints import Setup, evaluate, rows_of, sentence
from comeni_core.declared.contract import Cardinality, ModuleContract
from comeni_core.declared.measurement import Measurement, MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.diagnostics import coded
from comeni_core.goal.asked import Goal, InputState
from comeni_core.goal.profile import DataProfile, Measured
from comeni_core.plan.ir import IREdge, IRNode, PipelineIR, ResolvedValue
from comeni_core.plan.tiers import InputForm, Scope, Tier, ValueSource
from comeni_core.spell.marks import LayerName, ParamValue

# ---------------- PIPELINE CONSTRUCTION ----------------


def of(
    ir: PipelineIR,
    registry: Registry,
    vocab: Vocabulary,
    measurements: MeasurementRegistry | None = None,
    layers: Sequence[Path] = (),
    *,
    goal: Goal,
    ai: AiProvenance | None = None,
    locators: Mapping[LayerName, Locator] | None = None,
) -> Pipeline:
    """Build a Pipeline from resolved nodes, edges, decisions, and declarations.

    Requires the original goal and records its resolved profile. Fingerprints
    contracts and layers, builds input channels and steps, and records registry
    and AI provenance. Model construction validates the resulting artifact.
    """

    lock = Lockfile.of(ir, registry, layers, locators)
    pinned = {entry.id: entry for entry in lock.contracts}

    incoming_edges = {(edge.to_node, edge.to_port): edge for edge in ir.edges}
    assigned_channels = _named(ir)

    # Build channels before wiring step inputs to their names.
    channels = _channels(ir, registry, vocab, measurements, incoming_edges, assigned_channels)
    default_channels_by_type = {channel.type_id: channel.name for channel in channels}

    steps = []
    params_of = {channel.name: channel.param for channel in channels}
    for node in ir.nodes:
        contract = registry.get(node.contract_id)
        entry = pinned[node.contract_id]
        wiring = _inputs(
            node, contract, incoming_edges, assigned_channels, default_channels_by_type
        )
        fed = {w.port: params_of[w.channel] for w in wiring if w.channel is not None}
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
                inputs=wiring,
                call=_call(contract, _off(node)),
                settings=_settings(node, contract),
                input_states=list(node.inputs),
                run_rules=_run_rules(contract, node, fed),
            )
        )
    channels = _optional_channels(channels, steps, registry)

    return Pipeline(
        # Save the resolved profile with the original intent and inputs.
        intent=goal.intent,
        facts=goal.model_copy(update={"profile": ir.profile}).facts,
        registry=RegistryProvenance(
            layers=list(lock.layers),
            displaced=list(ir.displaced),
            unverified=list(ir.unverified),
        ),
        # Availability comes from the caller; decisions alone cannot establish it.
        ai=_read_upstream(ai or AiProvenance(available=[], used=[]), ir.profile),
        steps=steps,
        channels=channels,
        input_form=_form(channels),
        decisions=list(ir.decisions),
    )



# ---------------- STEP DETAILS AND METADATA ----------------


def _ext_args(contract: ModuleContract) -> ExtArgs:
    """Normalize a contract's baseline flags and their stated reason into ExtArgs.

    Accepts either a bare string or a declaration with a template and reason.
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


def _meta_entry(
    key: str, measurement: Measurement, value: ParamValue | list[ParamValue], entry: Measured | None
) -> MetaEntry:
    """Build channel metadata with the measurement value and its provenance.

    Records whether the value was measured, read by AI, or asserted in the goal,
    including available measurement counts, citations, and descriptions.
    """
    source = entry.source if entry is not None else ValueSource.SAID
    by = entry.by if entry is not None else None

    if source is ValueSource.MEASURED:
        measurer = " + ".join(entry.pieces) if entry is not None and entry.pieces else by
        reason = f"measured by {measurer}" if measurer else "measured"
        evidence = entry.evidence if entry is not None else None
        if evidence is not None and evidence.records is not None:
            reason = f"{reason}, on {evidence.records:,} reads"
        elif evidence is not None and evidence.rows is not None:
            reason = f"{reason}, on {evidence.rows:,} rows of reads"
    elif source is ValueSource.MODEL:
        reason = "read by AI from the start of a sample; check it"
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


def _why(value: ResolvedValue) -> Why:
    """Copy a resolved value's provenance, including the value it explains."""
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


def _settings(node: IRNode, contract: ModuleContract) -> list[Setting]:
    """Pair resolved parameter values with their contract-defined output routes.

    Sorts settings by name and rejects parameters not declared by the contract.
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


def _off(node: IRNode) -> frozenset[str]:
    """The optional inputs this step leaves out (#460)."""
    return frozenset(r.port for r in node.inputs if r.state is InputState.OFF)


def _call(contract: ModuleContract, off: frozenset[str] = frozenset()) -> list[CallArg]:
    """Copy the contract's ordered process input signature into call arguments.

    Records ports, literals, empty inputs, setting references, joins, and reasons. An entry
    whose inputs are all left out passes its declared empty tuple (`absent`, #460).
    """
    return [
        CallArg(
            ports=list(spec.ports),
            literal=spec.literal,
            empty_width=(spec.absent if spec.ports and set(spec.ports) <= off
                         else spec.empty) or None,
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


# ---------------- INPUT CONNECTIONS AND CHANNELS ----------------


def _inputs(
    node: IRNode,
    contract: ModuleContract,
    incoming_edges: dict[tuple[str, str], IREdge],
    assigned_channels: dict[str, str],
    default_channels_by_type: dict[str, str],
) -> list[StepInput]:
    """Connect each consumed port to an upstream output or an external channel.

    Uses explicit channel assignments where present, otherwise the type's default
    channel. Marks multi-item ports for gathering on either input route.
    """
    inputs = []
    off = _off(node)
    for port in contract.consumes:
        if port.name in off:
            continue
        edge = incoming_edges.get((node.id, port.name))
        # Multi-item ports gather both upstream outputs and external inputs.
        gather = port.cardinality is Cardinality.MANY
        if edge is not None:
            inputs.append(
                StepInput(
                    port=port.name,
                    source=f"{edge.from_node}.{edge.from_port}",
                    states=sorted(edge.states),
                    gather=gather,
                )
            )
        else:
            assigned = (
                assigned_channels.get(f"{node.id}.{port.name}")
                or default_channels_by_type[node.entry_type(port.name, port.type_id)]
            )
            inputs.append(StepInput(port=port.name, channel=assigned, gather=gather))
    return inputs


def _optional_channels(
    channels: list[Channel], steps: list[Step], registry: Registry
) -> list[Channel]:
    """Mark a channel optional when every step it feeds has it as an optional input (#460).

    One required consumer makes it required: a run cannot leave a file empty that another
    step needs. An optional channel carries the empty tuple its consumers take instead; the
    constraints a run must settle are on those steps (`Step.run_rules`)."""
    consumers: dict[str, list[tuple[Step, str]]] = {}
    for step in steps:
        for wiring in step.inputs:
            if wiring.channel is not None:
                consumers.setdefault(wiring.channel, []).append((step, wiring.port))
    marked = []
    for channel in channels:
        fed = consumers.get(channel.name, [])
        widths = []
        for step, port in fed:
            states = {r.port: r.state for r in step.input_states}
            if states.get(port) is not InputState.OPTIONAL:
                break
            contract = registry.get(step.module.contract_id)
            widths += [e.absent for e in contract.input_signature() if port in e.ports]
        else:
            if fed and len(set(widths)) > 1:
                # One empty tuple feeds every consumer, and Nextflow matches its arity.
                raise ValueError(
                    f"optional input {channel.name} feeds steps whose empty placeholders "
                    f"differ in width ({', '.join(str(w) for w in sorted(set(widths)))}), "
                    "so one run cannot leave it empty for all of them; make it required "
                    "for one of them")
            if fed:
                channel = channel.model_copy(update={"optional": True,
                                                     "absent_width": widths[0]})
        marked.append(channel)
    return marked


def _run_rules(contract: ModuleContract, node: IRNode, fed: dict[str, str]) -> list[RunRule]:
    """The step's constraints only a run can settle, as the pipeline params they concern, so the
    pipeline and the run sheet can check them (#460). A row about an input fed by another step
    or about a param was settled at build time, and is not here."""
    said = set(_run_sentences(contract, node))
    rules = []
    for row in rows_of(contract):
        says = sentence(row)
        if says not in said:
            continue
        given = [fed[k.partition(".")[2]] for k in row.when
                 if k.startswith("given.") and k.partition(".")[2] in fed]
        rule = RunRule(given=sorted(given),
                       requires=sorted(fed[n] for n in row.requires if n in fed),
                       forbids=sorted(fed[n] for n in row.forbids if n in fed), says=says)
        # A row with no condition left to test still binds the run when it forbids something:
        # `forbids: [gff]` becomes `if (params.gff) error` (second review I3). One that only
        # requires, with nothing given, would already be a build-time refusal.
        keeps = rule.forbids or (rule.given and rule.requires)
        if keeps and rule not in rules:
            rules.append(rule)
    return rules


def _run_sentences(contract: ModuleContract, node: IRNode) -> list[str]:
    states = {r.port: r.state for r in node.inputs}
    given = {p.name for p in contract.consumes if p.required}
    given |= {p for p, s in states.items() if s is InputState.REQUIRED}
    unknown = frozenset(p for p, s in states.items() if s is InputState.OPTIONAL)
    params = {p.name: (node.param(p.name).value if node.param(p.name) else None)
              for p in contract.params}
    verdict = evaluate(contract, Setup(given=frozenset(given), params=params, unknown=unknown))
    return verdict.holds_at_run_time


def _form(channels: Sequence[Channel]) -> InputForm:
    """Use a samplesheet for multiple sample-scoped channels, otherwise direct input."""
    return (
        InputForm.SAMPLESHEET
        if sum(1 for c in channels if c.scope is Scope.SAMPLE) > 1
        else InputForm.DIRECT
    )


def _wanted(
    ir: PipelineIR,
    registry: Registry,
    incoming_edges: dict[tuple[str, str], IREdge],
    assigned_channels: dict[str, str],
) -> list[tuple[str, str]]:
    """List explicit channels, then default channels needed by unconnected ports.

    An empty name requests a derived name. Explicit assignments cover their ports;
    remaining ports get one default channel per type, sorted by type ID.
    """
    defaulted: set[str] = set()
    for node in ir.nodes:
        off = _off(node)
        for port in registry.get(node.contract_id).consumes:
            if (node.id, port.name) in incoming_edges or port.name in off:
                continue
            if f"{node.id}.{port.name}" not in assigned_channels:
                defaulted.add(node.entry_type(port.name, port.type_id))
    return [(c.name, c.type_id) for c in ir.channels] + [
        ("", type_id) for type_id in sorted(defaulted)
    ]


def _named(ir: PipelineIR) -> dict[str, str]:
    """Map each explicitly assigned node.port to its channel name."""
    return {port: channel.name for channel in ir.channels for port in channel.ports}


def _channels(
    ir: PipelineIR,
    registry: Registry,
    vocab: Vocabulary,
    measurements: MeasurementRegistry | None,
    incoming_edges: dict[tuple[str, str], IREdge],
    assigned_channels: dict[str, str],
) -> list[Channel]:
    """Build external input channels from the IR, vocabulary, and measurements.

    Keeps explicit names and scope choices, supplies defaults for other channels,
    and records expressions, parameter references, columns, metadata, and test data.
    Channel names and parameter names use separate collision tracking.
    """
    names: dict[str, None] = {}
    params: dict[str, None] = {}
    name_suffixes: dict[str, int] = {}
    param_suffixes: dict[str, int] = {}
    declared_channels = {channel.name: channel for channel in reversed(ir.channels)}
    profile_entries = {entry.measurement: entry for entry in reversed(ir.profile.measurements)}
    wanted = _wanted(ir, registry, incoming_edges, assigned_channels)
    sources_by_type = (
        measurements.meta_sources_by_type({type_id for _, type_id in wanted}, ir.profile)
        if measurements and wanted else {}
    )
    channels = []
    for given, type_id in wanted:
        sourced = sources_by_type.get(type_id, {})
        template = vocab.entry_channels.get(type_id) or _default_entry()
        # Preserve explicit names; derive names only for default channels.
        name = given or _unique(_stem(type_id), names, name_suffixes)
        if given:
            names[given] = None
        param = _unique(vocab.params.get(type_id) or _stem(type_id), params, param_suffixes)
        expression = _substitute(template, param)
        declared = vocab.test_data.get(type_id)
        declared_channel = declared_channels.get(name)
        chosen = declared_channel.scope if declared_channel is not None else None
        wide = vocab.columns.get(type_id, 1)
        channels.append(
            Channel(
                columns=[name] if wide == 1 else [f"{name}_{n}" for n in range(1, wide + 1)],
                scope=Scope(chosen.value) if chosen else Scope(
                    vocab.scopes.get(type_id, Scope.SAMPLE)
                ),
                why=_why(chosen) if chosen else None,
                name=name,
                param=param,
                type_id=type_id,
                params=extract_param_refs(expression),
                expression=expression,
                meta=[
                    _meta_entry(key, *sourced[key], profile_entries.get(sourced[key][0].id))
                    for key in sorted(sourced)
                ],
                test_data=[declared] if isinstance(declared, str) else list(declared or []),
            )
        )
    return channels


# ---------------- CHANNEL NAMES AND EXPRESSIONS ----------------


def _stem(type_id: str) -> str:
    """Derive a name from the type ID's last segment, replacing hyphens with underscores."""
    return type_id.rsplit(".", 1)[-1].replace("-", "_")


def _unique(
    stem: str, taken: dict[str, None], next_suffix: dict[str, int] | None = None
) -> str:
    """Reserve a free name: stem, stem_2, stem_3, and so on.

    A shared suffix index avoids retrying occupied suffixes on repeated calls.
    """
    if stem not in taken:
        taken[stem] = None
        return stem
    n = next_suffix.get(stem, 2) if next_suffix is not None else 2
    while True:
        candidate = f"{stem}_{n}"
        if candidate not in taken:
            taken[candidate] = None
            if next_suffix is not None:
                next_suffix[stem] = n + 1
            return candidate
        n += 1


PLACEHOLDER = "{param}"
"""Literal parameter-name placeholder in vocabulary entry-channel expressions."""


def _substitute(expression: str, param: str) -> str:
    """Replace each literal {param} placeholder with the channel's parameter name."""
    return expression.replace(PLACEHOLDER, param)


def _default_entry() -> str:
    """Supply a file input expression when the vocabulary defines none.

    Each matched path becomes a tuple containing empty metadata and the file.
    """
    return (
        "Channel.fromPath(params.{param}, checkIfExists: true).map { f -> [ [:], f ] }"
    )


# ---------------- AI PROVENANCE ----------------


def _read_upstream(ai: AiProvenance, profile: DataProfile | None) -> AiProvenance:
    """Record characterisation as available and used for AI-sourced measurements.

    Preserves the caller's other AI provenance and avoids duplicate entries.
    """
    if profile is None or not any(m.source is ValueSource.MODEL for m in profile.measurements):
        return ai
    point = AiPoint.CHARACTERISE

    def with_point(points: list[AiPoint] | None) -> list[AiPoint]:
        return [*(points or []), *([] if point in (points or []) else [point])]

    return ai.model_copy(
        update={"available": with_point(ai.available), "used": with_point(ai.used)}
    )
