"""Building a `Pipeline` from a resolved IR. The one direction that reads the registry.

Split out of `pipeline.py` because that file was doing three jobs — what the artifact *is*, how
it is built, and what a file must satisfy to be read back — and only this one needs a registry,
a vocabulary and a measurement set. A reader asking "where does `ext_args` get its premise" was
reading 1,116 lines to find out.

**Materialisation is why `emit` takes one argument.** Everything the emitter would otherwise
look up — process names, include paths, entry-channel expressions, the measured facts that ride
in `meta` — is copied onto the `Pipeline` here. That is what lets a laboratory archive a
validated pipeline and rebuild its Nextflow years later with no registry and no network.

`Pipeline.of` stays on `Pipeline` and delegates here: `tests/guards/test_construction.py` asserts it
is the only validating constructor, and that guard is about the entry point rather than the code
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
from comeni_core.declared.contract import Cardinality, ModuleContract
from comeni_core.diagnostics import coded
from comeni_core.plan.tiers import InputForm, Scope, Tier, ValueSource


def of(ir, registry, vocab, measurements=None, layers=(), *, goal) -> Pipeline:
    """The **only** validating constructor.

    `goal` is **keyword-only and required**, with no default. The first version defaulted
    it to `Goal(profile=ir.profile)`, which type-checked, round-tripped, passed the
    totality test — that test asks whether a field has a *home*, and it did — and wrote
    `have: []`, `want: []` into every pipeline file. A default is how a field comes to be
    present and empty, and this file's whole claim is that it records what was asked for.

    Enforced by `tests/guards/test_construction.py`, the way `MeasurementRegistry.profile()`
    already is — that guard exists because deleting one call let `profile: {sample_name:
    ...}` build cleanly. Same reasoning: materialisation must not be bypassable by a caller
    assembling a `Pipeline` by hand with the contract-derived fields left empty.

    Takes a registry as an *argument* and keeps none of it. `registry.py` carries a mapping
    and says it is legal because `Registry` is not payload-reachable; holding one here would
    silently end that.
    """

    lock = Lockfile.of(ir, registry, layers)
    pinned = {entry.id: entry for entry in lock.contracts}

    # **Channels first, because a port now names one.** `StepInput.channel` was a `TypeId`, so
    # a port could say where it read from without anything having decided what the channels
    # were; it is a `ChannelName` now, and a name that no channel declares is `MD0227`.
    channels = _channels(ir, registry, vocab, measurements)
    named = {channel.type_id: channel.name for channel in channels}

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
                inputs=_inputs(ir, node, contract, named),
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
        channels=channels,
        # **Derived, never authored.** One sample-scoped channel is a glob; two or more is a
        # table, because *reads with their respective annotations* cannot be two globs.
        # `MD0229` refuses a file where the two disagree, which is what keeps `params.input`'s
        # two meanings from both being claimed at once.
        input_form=_form(channels),
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


def _inputs(ir, node, contract, named: dict[str, str]) -> list[StepInput]:
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
        # **On both branches.** MULTIQC's `reports` port is *wired* — it consumes what FASTQC
        # produced — so setting this only where a port reads an entry channel would have left
        # the case the field exists for untouched.
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
            # **The channel's NAME, not its type**, and since phase 3 the drawing may have
            # said which of two same-type channels this port reads. `named` is the
            # one-per-type fallback, used only where the drawing said nothing.
            assigned = _named(ir).get(f"{node.id}.{port.name}") or named[port.type_id]
            inputs.append(StepInput(port=port.name, channel=assigned, gather=gather))
    return inputs


def _form(channels) -> InputForm:
    """One sample-scoped channel is a glob; two or more is a table.

    **Derived, never authored**, because *reads with their respective annotations* cannot be two
    globs — two independent `fromFilePairs` zip by position and nothing ties a sample's reads to
    its own annotation. `MD0229` refuses a file where this and the channels disagree.
    """
    return (
        InputForm.SAMPLESHEET
        if sum(1 for c in channels if c.scope is Scope.SAMPLE) > 1
        else InputForm.DIRECT
    )


def _override_for(ir, name: str):
    """The IR channel of this name, if the drawing declared one. `None` for a derived channel."""
    return next((c for c in getattr(ir, "channels", []) if c.name == name), None)


def _wanted(ir, registry) -> list[tuple[str, str]]:
    """`(name, type_id)` per channel, in order — an empty name meaning *derive it*.

    ═══ THE DRAWING'S ASSIGNMENT IS AN OVERRIDE, NOT A REPLACEMENT ═══════════════════════════

    `ir.channel_of` maps `<node>.<port>` → channel name and is filled by
    `mendel_resolver.materialise.channels_of` from the drawing's `DraftChannel` list. It covers
    only the ports whose type declares an `entry_channel`, because those are the ones a person
    can split — so a port reading a type with no declared channel (`alignment.bam` on a graph
    with no sorter) is **not in the map and still needs one**, from `_default_entry`.

    Treating the map as a replacement rather than an override is exactly the bug this docstring
    exists to stop: `_inputs` raised `KeyError: 'alignment.bam'` on the first drawing that split
    a channel, because the map had three types and the graph consumed four.

    **Names are not re-derived where the map has one.** Two derivations of one fact is the
    defect this whole plan started from, so materialisation reads the resolver's answer rather
    than computing its own and hoping they agree.

    ═══ THE FALLBACK ORDER IS SHAPE, NOT IDENTITY ════════════════════════════════════════════

    Sorting by type id is keyed on nothing a person clicked: with one channel per type the order
    is a pure function of the SET of types consumed, so two identical drawings sort identically
    however they were built. Spec §11.2's `(depth, contract, port)` key is what `channels_of`
    applies on the other route, where a type has stopped being a unique key.
    """
    fed = {(edge.to_node, edge.to_port) for edge in ir.edges}
    named = _named(ir)
    defaulted: dict[str, None] = {}
    for node in ir.nodes:
        for port in registry.get(node.contract_id).consumes:
            if (node.id, port.name) in fed:
                continue
            if f"{node.id}.{port.name}" not in named:
                defaulted[port.type_id] = None
    return [(c.name, c.type_id) for c in ir.channels] + [
        ("", type_id) for type_id in sorted(defaulted)
    ]


def _named(ir) -> dict[str, str]:
    """`<node>.<port>` → channel name, from the IR's channel records.

    Built at the point of use rather than stored: a mapping on a payload is what
    `tests/guards/test_egress.py` refuses, and it refuses it because a mapping's keys are
    unvalidated by construction. Inside a function the keys came from `SocketKey` fields that were.
    """
    return {port: channel.name for channel in ir.channels for port in channel.ports}


def _channels(ir, registry, vocab, measurements) -> list[Channel]:
    """Every channel the pipeline reads from outside, and how each arrives.

    The `meta` entries are the measured facts a module reads — `single_end`, `strandedness` —
    materialised here so emission needs no measurement registry. Sorted, because a set or a
    dict order reaching a digest is how a lockfile becomes spuriously dirty.

    **Two counters, not one.** They were one, and it produced `ch_star` reading `params.star_2`:
    the name took `star` and the param — the same word, for the same channel — found it taken
    and suffixed itself. A name and a param are different namespaces (a Groovy variable against
    a `params.*` key), and only a *cross-channel* collision is a collision. Caught by reading the
    golden diff rather than regenerating it.
    """
    names: dict[str, None] = {}
    params: dict[str, None] = {}
    channels = []
    for given, type_id in _wanted(ir, registry):
        sourced = measurements.meta_sources_for(type_id, ir.profile) if measurements else {}
        template = vocab.entry_channels.get(type_id) or _default_entry()
        # A name the resolver assigned is taken as given and only recorded as used; an empty one
        # is derived here, which is the one-channel-per-type route.
        name = given or _unique(_stem(type_id), names)
        if given:
            names[given] = None
        param = _unique(vocab.params.get(type_id) or _param_of(template, type_id), params)
        expression = _substitute(template, param)
        declared = vocab.test_data.get(type_id)
        # **The type's default unless the drawing overrode it**, and an override is a decision.
        # Per-sample annotations over a shared one is a different analysis, not a different
        # spelling, so it exits at tier 4 and carries the person's own reason (invariant 6).
        # Taking the default records nothing: a `Why` for a choice nobody made would owe
        # `mendel explain` an answer to a question that was never open, and `upgrade` would
        # replay it forever.
        drawn = _override_for(ir, name)
        chosen = drawn.scope if drawn is not None else None
        wide = vocab.columns.get(type_id, 1)
        channels.append(
            Channel(
                columns=[name] if wide == 1 else [f"{name}_{n}" for n in range(1, wide + 1)],
                scope=Scope(chosen.value) if chosen else Scope(
                    vocab.scopes.get(type_id, Scope.SAMPLE)
                ),
                # **Read from the resolver's answer, not rebuilt.** It stamped the tier when it
                # read the drawing; deriving a second `Why` here would be two answers to *at
                # which tier was this settled*, which is A130's shape — and `_why` is the same
                # function every settled param goes through.
                why=_why(chosen) if chosen else None,
                name=name,
                param=param,
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


def _stem(type_id: str) -> str:
    """`annotation.gtf` -> `gtf`. The type id's last segment, and nothing else.

    **Not injective, and the suffix is what fixes it rather than a longer name.** `qc.report`
    and `multiqc.report` both end in `report` — a collision `_channel_name`'s docstring already
    recorded costing two ports the same channel silently. `_unique` assigns the second one
    `report_2`, in an order that is a function of the graph's shape, and `MD0226` refuses the
    pipeline if two ever come out equal anyway.
    """
    return type_id.rsplit(".", 1)[-1].replace("-", "_")


def _param_of(template: str, type_id: str) -> str:
    """Which param a channel of this type reads, when the type does not declare one.

    The type id's last segment: `annotation.gtf` → `gtf`, `genome.fasta` → `fasta`. Every
    shipped type but `fastq.reads` gets its param this way, and that one declares `param: input`
    rather than being renamed to `params.reads` by a derivation.

    **It used to ask a literal expression what it read**, for the one commit between the engine
    learning `{param}` and the registry writing it. `MD0228` refuses a literal now, so there is
    no expression left to ask.
    """
    return _stem(type_id)


def _unique(stem: str, taken: dict[str, None]) -> str:
    """`stem`, or `stem_2`, `stem_3` … — whichever is free, recorded as taken.

    Called with a **separate** set for names and for params — see `_channels` for why sharing
    one produced `ch_star = … params.star_2`.
    """
    #
    # **A `while` rather than `itertools.count`**, and the guard is why: `itertools` is not on
    # `comeni-core`'s purity allowlist, and that allowlist is worth more than the import. The
    # same trade `_joined_identifier` records for `re` — *widening the allowlist for a two-line
    # loop is a worse trade than the loop* — reached the same way, by the scan refusing it.
    if stem not in taken:
        taken[stem] = None
        return stem
    n = 2
    while True:
        candidate = f"{stem}_{n}"
        if candidate not in taken:
            taken[candidate] = None
            return candidate
        n += 1


PLACEHOLDER = "{param}"
"""The one substitution an `entry_channel` may carry. **Seven literal characters.**

Not a template language — the same argument as Plan 1.15's `transform`: no parser, no
precedence, no second name. `{` is legal Groovy and appears throughout these expressions
(`.map { gtf -> … }`), so this is matched literally and everything else is left alone.
"""


def _substitute(expression: str, param: str) -> str:
    """Put this channel's param into the type's template.

    **One `str.replace` is the whole implementation, and that is the design.** `MD0228` has
    already refused a template with no placeholder by the time anything reaches here, and
    `PLACEHOLDER` is seven literal characters — so there is no parser, no precedence and no
    second name a type could reference. Plan 1.15's `transform` made the same trade for the
    same reason.
    """
    return expression.replace(PLACEHOLDER, param)


def _default_entry() -> str:
    """How a type arrives when its vocabulary declares no `entry_channel`.

    Materialised here rather than left to the emitter, because emission must not need the
    vocabulary. Deleting this while narrowing `emit`'s signature emitted `ch_genome_index_star =`
    with nothing after it — valid-looking Groovy that dies at parse, caught by reading the
    golden diff rather than by regenerating it and moving on.
    """
    return (
        "Channel.fromPath(params.{param}, checkIfExists: true).map { f -> [ [:], f ] }"
    )
