"""Compare declared module contracts with facts parsed from their Nextflow source.

Checks cover processes, inputs, outputs, containers, metadata, and routed settings. Each
diagnostic identifies the declaration, contradictory source fact, and a concrete correction.
"""

from collections.abc import Mapping
from pathlib import Path

from comeni_core import diagnostics
from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.module import ENTRY, Module, key_of
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.diagnostics import explain  # re-exported: `mendel explain` calls it here
from comeni_core.spell.routes import ExtKey, Via
from pydantic import BaseModel, ConfigDict, field_validator

from mendel_compiler.modulespec import ModuleSpec, _format


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    where: str
    summary: str
    detail: str
    """What the module says, and what the contract says instead."""
    fix: str
    """What to write. A diagnostic without this is half a diagnostic."""

    @field_validator("code")
    @classmethod
    def _declared(cls, code: str) -> str:
        """A code must exist in `comeni_core/diagnostics.yml`.

        The alternative was a test asserting every emittable code has an explanation, and a
        test can only find codes on paths it executes. This makes an undeclared code
        unrepresentable — invariant 7's shape, a closed vocabulary, applied to diagnostics.

        Re-raised as `ValueError`: Pydantic converts only `ValueError` and `AssertionError`
        into a `ValidationError`, and `UnknownDiagnosticError` is a `KeyError` because a direct
        `spec_for` call is a failed lookup. Left alone it escapes this validator raw, so a
        caller writing `except ValidationError` around a model construction would miss it.
        """
        try:
            diagnostics.spec_for(code)
        except diagnostics.UnknownDiagnosticError as error:
            raise ValueError(str(error)) from None
        return code

    def render(self) -> str:
        return (
            f"{self.code}  {self.where}\n"
            f"  {self.summary}\n"
            f"{self.detail}\n"
            f"  → {self.fix}"
        )


__all__ = ["Diagnostic", "against", "check", "explain", "module_path"]


def module_path(contract: ModuleContract, modules: Mapping[str, Module]) -> Path | None:
    """The `main.nf` this contract is a binding for, or `None` if the stack carries no such
    module.

    **This took a `module_root: Path` until Plan 5A, and the change is the whole point of that
    plan.** Module source lived in `vendor/` in the *engine's* repository while the contracts
    describing it lived in `registry/` — two repositories on two release cadences — so this
    computed `module_root / f"{nf_include}.nf"` and a contract could drift from its module with
    nothing keeping the two in step. `MD0104` exists to catch that drift and was comparing two
    things nobody synchronised.

    The source is now *in the layer*, so a location is no longer derivable from a root: the
    module is looked up **by key**, which `comeni_core.declared.module.key_of` derives from the
    contract's own `nf_include`. `nf_include` still means what it always meant — where a module
    lands in the *generated* pipeline — and is still deliberately not where the source lives.

    `None` rather than a non-existent path, because the two callers want different things from
    the absence: `check` reports `MD0100`, and the forge skips.
    """
    found = modules.get(key_of(contract.nf_include))
    if found is None or found.source is None:
        return None
    return found.source / f"{ENTRY}.nf"


def blocking(found: list[Diagnostic]) -> list[Diagnostic]:
    """The diagnostics that stop a build: those `diagnostics.yml` declares as refusing.
    `MD0100` (no source to check) and `MD0611` (an optional emit said always) are reported."""
    return [d for d in found if diagnostics.spec_for(d.code).refuses]


def type_formats(registry: Registry, vocabulary: Vocabulary | None = None) -> dict[str, set[str]]:
    """The file formats each type is known to come in (#414): what the contracts making it
    write, and the format of its declared `test_data`. Types declare no format of their own, so
    a type nothing makes and with no test data has none, and a slot it fills is not checked."""
    found: dict[str, set[str]] = {}
    for contract in registry.all():
        for port in contract.produces:
            found.setdefault(port.type_id, set()).update(f for f in port.format if f != "folder")
    for type_id, data in ((vocabulary.test_data if vocabulary else {}) or {}).items():
        urls = data if isinstance(data, list) else [data]
        for url in urls:
            name = url.rsplit("/", 1)[-1]
            if (format_ := _format(name)) and format_ != "folder" and "." in name:
                found.setdefault(type_id, set()).add(format_)
    return found


def specs_of(registry: Registry, modules: Mapping[str, Module]) -> dict[str, ModuleSpec]:
    """Each contract's module source, parsed once, by contract id; a contract whose source
    cannot be read has none. What `check`, `_meta_keys` and `facts_read` all read: parsing it
    for each of them was 3 parses of every module per build (#546). A value the caller holds
    for one build, not a cache."""
    parsed: dict[Path, ModuleSpec] = {}
    found: dict[str, ModuleSpec] = {}
    for contract in registry.all():
        path = module_path(contract, modules)
        if path is None or not path.exists():
            continue
        if path not in parsed:
            parsed[path] = ModuleSpec.parse(path)
        found[contract.id] = parsed[path]
    return found


def check(
    registry: Registry,
    modules: Mapping[str, Module],
    measurements: MeasurementRegistry | None = None,
    vocabulary: Vocabulary | None = None,
    specs: Mapping[str, ModuleSpec] | None = None,
) -> list[Diagnostic]:
    """Every way a contract disagrees with the module it claims to describe.

    Sorted, because these are printed and byte-identical output is a hard requirement.

    `measurements` is optional because `check` is called from places that have none, and
    MD0106 cannot be evaluated without one. Silence beats a wrong answer.
    """
    found: list[Diagnostic] = []
    formats = type_formats(registry, vocabulary)
    specs = specs_of(registry, modules) if specs is None else specs
    for contract in registry.all():
        path = module_path(contract, modules)
        if path is None or not path.exists():
            found.append(
                Diagnostic(
                    code="MD0100",
                    where=contract.id,
                    summary="unverified: no module source to check this contract against",
                    detail=(
                        "    no layer in this stack declares module "
                        f"{key_of(contract.nf_include)}"
                    ),
                    fix="vendor it with `comeni-vendor add`, or accept that this contract "
                    "cannot be curated",
                )
            )
            continue
        found += against(contract, specs[contract.id], path, formats=formats)
    if measurements is not None:
        found += _meta_keys(registry, modules, measurements, specs)
    return sorted(found, key=lambda d: (d.where, d.code, d.detail))


def against(contract: ModuleContract, spec: ModuleSpec, path: Path,
            formats: Mapping[str, set[str]] | None = None) -> list[Diagnostic]:
    """Every way *one* contract disagrees with *one* module.

    Public because the forge checks a single draft where `check` checks a whole registry,
    and `Registry` has no constructor that takes one in-memory contract — it loads from
    disk or wraps a `Stacked`. Reaching into another package's underscore to get at this
    would be worse than naming it, so it is named.
    """
    found: list[Diagnostic] = []

    if contract.nf_process != spec.process:
        found.append(
            Diagnostic(
                code="MD0101",
                where=contract.id,
                summary=f"process {contract.nf_process!r} is not what this module declares",
                detail=f"    {path}   process {spec.process} {{",
                fix=f"nf_process: {spec.process}",
            )
        )

    signature = contract.input_signature()
    if len(signature) != len(spec.inputs):
        found.append(
            Diagnostic(
                code="MD0102",
                where=contract.id,
                summary=(
                    f"the contract declares {len(signature)} channels; "
                    f"the module takes {len(spec.inputs)}"
                ),
                detail="\n".join(
                    f"    slot {slot.position}: {' '.join(slot.kinds)}  ({', '.join(slot.names)})"
                    for slot in spec.inputs
                ),
                fix=f"nf_inputs needs exactly {len(spec.inputs)} entries, in the module's order",
            )
        )
        return found  # positional checks below are meaningless once the count is wrong

    for entry, slot in zip(signature, spec.inputs, strict=True):
        if entry.empty and entry.empty != slot.width:
            found.append(
                Diagnostic(
                    code="MD0103",
                    where=contract.id,
                    summary=(
                        f"slot {slot.position} placeholder is width {entry.empty}, "
                        f"the module declares {slot.width}"
                    ),
                    # The width is in the detail as well as the summary because the
                    # detail is what a reader compares against the module by eye.
                    detail=f"    {path}   tuple of {slot.width}: {' '.join(slot.kinds)}",
                    fix=f"{{empty: {slot.width}, because: ...}}",
                )
            )

        if entry.ports:
            # `val(meta)` heads the tuple when its ports' channel carries one; then one element
            # per port, then the padding (#507).
            heads = 1 if slot.kinds[0] == "val" and slot.width > 1 else 0
            filled = heads + len(entry.ports) + entry.pad
            unfilled = slot.width - heads - len(entry.ports)
            if filled != slot.width:
                found.append(
                    Diagnostic(
                        code="MD0111",
                        where=contract.id,
                        summary=(
                            f"slot {slot.position} is a tuple of {slot.width}; the contract "
                            f"fills {filled}"
                        ),
                        detail=f"    {path}   tuple of {slot.width}: {' '.join(slot.kinds)}"
                               f"  ({', '.join(n for n in slot.names if n)})",
                        fix=(f"{{ports: {entry.ports}, pad: {unfilled}}}" if unfilled > 0
                             else "one port per element of the module's tuple"),
                    )
                )

        if entry.ports and formats:
            found += _misplaced(contract, entry, slot, spec, path, formats)

        if entry.empty and slot.needs_a_file and not entry.because:
            # The *file* element, never the `val(meta)` beside it. meta.yml documents both
            # and documents `meta` first, so a plain "name in slot.names" lookup reports
            # "path(meta)" with a Groovy-map description — sending the reader to look for a
            # sample map where a genome is missing.
            file_names = [
                name
                for kind, name in zip(slot.kinds, slot.names, strict=True)
                if kind == "path" and name
            ]
            documented = next((d for d in spec.documented if d.name in file_names), None)
            wanted = documented.name if documented else (file_names[-1] if file_names else "?")
            described = (
                f'\n    meta.yml   {documented.name}: "{documented.description}"'
                if documented
                else ""
            )
            found.append(
                Diagnostic(
                    code="MD0104",
                    where=contract.id,
                    summary=(
                        f"slot {slot.position} declares path({wanted}) "
                        f"and the contract supplies a placeholder"
                    ),
                    detail=(
                        f"    {path}   {' '.join(slot.kinds)}"
                        f"  ({', '.join(n for n in slot.names if n)}){described}"
                    ),
                    fix=(
                        "declare a port with a type_id for it, or say why the type system "
                        "does not model it with `because`"
                    ),
                )
            )

    emitted = set(spec.emits)
    for port in contract.produces:
        if port.name in spec.optional_emits and port.produced_when is None:
            found.append(
                Diagnostic(
                    code="MD0611",
                    where=contract.id,
                    summary=f"output {port.name!r} is optional in the module and always "
                            "written in the contract",
                    detail=f"    {path}   emit: {port.name} … optional: true",
                    fix="give it `produced_when`, the condition under which the module "
                        "writes it, e.g. {given.<input>: present}",
                )
            )
        if port.name not in emitted:
            found.append(
                Diagnostic(
                    code="MD0105",
                    where=contract.id,
                    summary=f"the module emits no channel named {port.name!r}",
                    detail=f"    {path}   emit: {', '.join(sorted(emitted)) or '(none)'}",
                    fix=f"rename the port to one of: {', '.join(sorted(emitted)) or '(none)'}",
                )
            )
        elif port.format and not port.format <= set(spec.emit_formats.get(port.name, [])):
            written = ", ".join(spec.emit_formats.get(port.name, [])) or "(unknown)"
            found.append(
                Diagnostic(
                    code="MD0109",
                    where=contract.id,
                    summary=f"output {port.name!r} declares a format the module does not write",
                    detail=f"    contract {', '.join(sorted(port.format))}\n    {path}   {written}",
                    fix=f"set `format` to what the module writes: {written}",
                )
            )

    found += _dead_ext_routes(contract, spec, path)

    if contract.container and spec.container and contract.container != spec.container:
        found.append(
            Diagnostic(
                code="MD0107",
                where=contract.id,
                summary="the container has drifted from the module",
                detail=f"    module   {spec.container}\n    contract {contract.container}",
                fix=f"container: {spec.container}",
            )
        )

    return found


# `meta.id` is set by every entry channel the compiler emits, so it is never missing.
# Secondary maps — `meta2`, `meta3` — belong to reference channels built from a plain
# `[id: ...]`, not to the reads, and demanding a measurement for them would be noise. A
# check that cries wolf is a check people switch off.
_ALWAYS_SET = {"id"}


# KNOWN AND DELIBERATE: this parses every module a second time, after the per-contract
# loop in `check` already parsed each one. On twelve modules it is free. At two hundred it
# will not be, and the fix is a `dict[Path, ModuleSpec]` cache threaded through both.
#
# Left unoptimised on purpose. A cache now is premature and unmeasured; whoever notices
# this being slow will have a real number to optimise against instead of a guess. Do not
# "fix" it while implementing this task — if you want it fixed, measure first and make it
# its own commit, so the before and after are visible.
def _meta_keys(
    registry: Registry, modules: Mapping[str, Module], measurements: MeasurementRegistry,
    specs: Mapping[str, ModuleSpec],
) -> list[Diagnostic]:
    """Undefined- and unused-symbol analysis, over the meta map.

    A module reading a key nothing sets uses its default silently — that is exactly how
    featureCounts computed `-s 0` for a reverse-stranded library. A declared `meta_key` no
    module reads is a declaration with no effect.
    """
    declared = {
        measurements.get(m).meta_key: m
        for m in measurements.ids()
        if measurements.get(m).meta_key
    }
    read: dict[str, str] = {}
    every_module_was_readable = True
    for contract in registry.all():
        path = module_path(contract, modules)
        if path is None or not path.exists():
            every_module_was_readable = False
            continue
        for entry in specs[contract.id].meta_reads:
            if entry.variable == "meta" and entry.key not in _ALWAYS_SET:
                read.setdefault(entry.key, contract.id)

    found = [
        Diagnostic(
            code="MD0106",
            where=contract_id,
            summary=f"the module reads meta.{key!r} and no declared measurement sets it",
            detail="    it will silently use the module's own default",
            fix=f"declare a measurement with `meta_key: {key}`, or accept the default knowingly",
        )
        for key, contract_id in sorted(read.items())
        if key not in declared
    ]
    # The unused direction is a claim about *every* module, so it needs every module. With
    # any source missing, "nothing reads this" is unfounded — and it fires on a correct
    # registry: a lab wrapping bare containers has no module source at all, so every
    # declared meta_key would look dead and the build would be refused over it. Evidence
    # before assertion, which is the same rule MD0100 exists to state.
    if every_module_was_readable:
        found += [
            Diagnostic(
                code="MD0106",
                where=f"measurements/{declared[key]}",
                summary=f"meta_key {key!r} is declared and no module in this registry reads it",
                detail="    the value would be set on the channel and never consulted",
                fix=f"remove `meta_key: {key}`, or add a module that reads it",
            )
            for key in sorted(set(declared) - set(read))
        ]
    return found


def facts_read(
    registry: Registry, modules: Mapping[str, Module], measurements: MeasurementRegistry,
    specs: Mapping[str, ModuleSpec] | None = None,
) -> dict[str, frozenset[str] | None]:
    """Per contract, the declared facts its module reads off the sample's label (#338).

    Derived from the code, as `_meta_keys` is: a declaration of the same thing would be a third
    copy of what the measurement's `meta_key` and the module already say. `None` when the source
    cannot be read; nothing is assumed about a module nobody could look at.
    """
    by_key = {
        measurements.get(m).meta_key: m
        for m in measurements.ids()
        if measurements.get(m).meta_key
    }
    found: dict[str, frozenset[str] | None] = {}
    specs = specs_of(registry, modules) if specs is None else specs
    for contract in sorted(registry.all(), key=lambda c: c.id):
        path = module_path(contract, modules)
        if path is None or not path.exists():
            found[contract.id] = None
            continue
        found[contract.id] = frozenset(
            by_key[entry.key]
            for entry in specs[contract.id].meta_reads
            if entry.variable == "meta" and entry.key not in _ALWAYS_SET and entry.key in by_key
        )
    return found


def _dead_ext_routes(contract: ModuleContract, spec: ModuleSpec, path: Path) -> list[Diagnostic]:
    """`MD0108` — a setting routed to an `ext` key the module never reads.

    A contract is a hand-written FFI binding, and this is the binding claiming a destination
    that does not exist. `via:` made a route *declared*; it did not make it *true*. A setting
    routed to `ext.args` on a module whose script never mentions `task.ext.args` is exactly
    the deadness issue #10 was about, wearing the fix.

    It costs nothing: `modulespec.py` already parses both as a substring of the source, which
    is why this lands in the reserved conformance band on day one rather than waiting for a
    Groovy parser. Three of the ten vendored modules ignore `task.ext.prefix`, so the prefix
    half has real negatives — a check that can only pass is not a check.

    Only `args`/`args2`/`args3` and `prefix` are checkable this way. `meta` and `directive`
    are Nextflow's own mechanisms rather than the module's, and `MD0209` already guards the
    directive names.
    """
    reads = {
        ExtKey.ARGS: spec.reads_ext_args,
        ExtKey.ARGS2: spec.reads_ext_args,
        ExtKey.ARGS3: spec.reads_ext_args,
        ExtKey.PREFIX: spec.reads_ext_prefix,
    }

    def dead(key: ExtKey) -> bool:
        return not reads.get(key, True)

    found = []
    # The contract's own static flags ride the same channel, and a contract declaring
    # `ext_args` for a module that ignores it is the same lie with no `Param` attached.
    if contract.ext_args and dead(ExtKey.ARGS):
        found.append(
            Diagnostic(
                code="MD0108",
                where=f"{contract.id}.ext_args",
                summary="the module never reads `task.ext.args`, so these flags reach nothing",
                detail=f"    {path}   no `task.ext.args` in the script block",
                fix="drop `ext_args`, or vendor a module that reads it",
            )
        )
    # The `meta` arm, added by Plan 1.14. `MD0108` gated on `via is not Via.EXT` and its own
    # docstring conceded that meta and directive were unchecked — which is exactly the gap
    # A91 hid in: routing `star_ignore_sjdbgtf` to `meta` produced a value the module never
    # reads, no diagnostic fired, and the artifact recorded a documented, human-answered
    # decision that reached nothing. `meta_reads` was already parsed out of `main.nf` for
    # `MD0106`, so this costs a comparison rather than a parser.
    read_keys = {read.key for read in spec.meta_reads}
    for param in contract.params:
        if param.via is Via.META and spec.meta_reads and param.name not in read_keys:
            found.append(
                Diagnostic(
                    code="MD0108",
                    where=f"{contract.id}.params[{param.name}]",
                    summary=(
                        f"{param.name} routes to `meta.{param.name}`, which this module "
                        f"never reads"
                    ),
                    detail=(
                        f"    {path}   reads {', '.join(sorted(read_keys)) or '(no meta keys)'}"
                    ),
                    fix=(
                        "route it somewhere the module reads. A bare `val` in the input "
                        "block takes `via: positional`; a flag takes `via: ext`. A value in "
                        "`meta` that nothing reads is the deadness issue #10 was about."
                    ),
                )
            )
    for param in contract.params:
        if param.via is not Via.EXT or not dead(param.key):
            continue
        found.append(
            Diagnostic(
                code="MD0108",
                where=f"{contract.id}.params[{param.name}]",
                summary=(
                    f"{param.name} routes to ext.{param.key.value}, which this module "
                    f"never reads"
                ),
                detail=f"    {path}   no `task.ext.{param.key.value}` in the script block",
                fix=(
                    "route it somewhere the module reads, or drop the parameter — a value "
                    "reaching no tool is the defect `via:` exists to remove"
                ),
            )
        )
    return found


def _port_formats(contract: ModuleContract, port_name: str,
                  formats: Mapping[str, set[str]]) -> set[str]:
    port = next((p for p in contract.consumes if p.name == port_name), None)
    if port is None:
        return set()
    return {f for a in port.alternatives() for f in formats.get(a.type_id, ())}


def _misplaced(contract: ModuleContract, entry, slot, spec: ModuleSpec, path: Path,
               formats: Mapping[str, set[str]]) -> list[Diagnostic]:
    """**A port in the wrong slot** (#414, MD0112): its type's formats share none with the file
    pattern meta.yml documents for the element it fills. A reversed `nf_inputs` passed every
    other check and failed only at run time. Silent where either side names no format: that
    element is unverified, not confirmed."""
    heads = 1 if slot.kinds[0] == "val" and slot.width > 1 else 0
    documented = {d.name: d for d in spec.documented}
    found = []
    for n, port_name in enumerate(entry.ports):
        at = heads + n
        if at >= len(slot.names):
            break
        element = documented.get(slot.names[at])
        wanted = set(element.formats) if element else set()
        offered = _port_formats(contract, port_name, formats)
        if not wanted or not offered or wanted & offered:
            continue
        fits = sorted(d.name for d in spec.documented if set(d.formats) & offered)
        found.append(Diagnostic(
            code="MD0112",
            where=contract.id,
            summary=(f"port {port_name} ({', '.join(sorted(offered))}) fills slot {slot.position}"
                     f"'s {element.name}, which takes {', '.join(sorted(wanted))}"),
            detail=f"    {path.parent / 'meta.yml'}   {element.name}: {element.pattern}",
            fix=(f"the module takes {', '.join(sorted(offered))} as {', '.join(fits)}: put "
                 f"{port_name} in that slot's entry" if fits
                 else "order nf_inputs as the module's input block declares its slots"),
        ))
    return found
