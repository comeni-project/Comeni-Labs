"""Does a contract tell the truth about its module?

Plan 1.5 shipped a pipeline that could not run, twice, because a contract said something
untrue and nothing compared them. `-stub-run` could not catch it: nf-core stubs never read
their inputs, so a process handed an empty tuple where a genome belongs is exactly as green
as one handed a genome.

Every diagnostic names the code, the contract, the module fact it contradicts, what was
written, and what to write instead. The last one is not decoration — the rule validator's
"parameters that do exist: …" is the single most useful thing about that error, and this
follows it.
"""

from pathlib import Path

from comeni_core.contract import ModuleContract
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from pydantic import BaseModel, ConfigDict

from mendel_compiler.modulespec import ModuleSpec

EXPLANATIONS: dict[str, str] = {
    "M0100": (
        "The contract names a module whose source is not present, so nothing could check\n"
        "it. The build continues and the contract is marked unverified, which is recorded\n"
        "on the IR and reaches a publish bundle. A curator may refuse to curate an\n"
        "unverified contract: a claim about a module, with no module to check it against,\n"
        "is a claim without evidence."
    ),
    "M0101": (
        "`nf_process` must be the process name as written in the module's main.nf. The\n"
        "emitted workflow calls it by that name, so a mismatch fails at launch with\n"
        "'process not found' — after the containers have been pulled."
    ),
    "M0102": (
        "`nf_inputs` declares one entry per channel the process takes. A contract port is\n"
        "not a process argument: featurecounts takes one channel carrying two ports, and\n"
        "samtools/sort takes three of which two model nothing. Nextflow matches arity, so\n"
        "a mismatch fails at launch."
    ),
    "M0103": (
        "`NfInput.empty` is a tuple *width*, not a count of channels. Nextflow matches\n"
        "arity: a 2-tuple handed to a slot declared `tuple val(meta), path(fasta),\n"
        "path(fai)` dies with 'Path value cannot be null'."
    ),
    "M0104": (
        "This slot declares `path(...)`, so the module expects a real file, and the\n"
        "contract supplies an empty placeholder. Sometimes that is correct — samtools/sort\n"
        "only needs a reference to write CRAM — and sometimes it is a hole: STAR was called\n"
        "with no genome for weeks, through a green test suite and a passing stub gate.\n"
        "Saying which, in `because`, is the whole check."
    ),
    "M0105": (
        "The emitted workflow reads `PROCESS.out.<name>` for each produced port, so every\n"
        "`produces[].name` must appear in the module's `emit:` labels. A mismatch fails at\n"
        "runtime against a channel that does not exist."
    ),
    "M0106": (
        "Measured facts reach nf-core modules through the `meta` map, and a module reading\n"
        "a key nothing sets silently uses its default. That is how featureCounts computed\n"
        "-s 0 for a reverse-stranded library and produced a matrix of wrong numbers while\n"
        "every gate stayed green. The reverse also matters: a `meta_key` no module reads is\n"
        "a declaration with no effect."
    ),
    "M0107": (
        "The container must match the module's `container` directive exactly. A contract\n"
        "claiming a container the module does not use is claiming a reproducibility it does\n"
        "not have. Take the *last* quoted string in the ternary: nf-core 4.x puts\n"
        "singularity first and docker second."
    ),
}


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    contract_id: str
    summary: str
    detail: str
    """What the module says, and what the contract says instead."""
    fix: str
    """What to write. A diagnostic without this is half a diagnostic."""

    def render(self) -> str:
        return (
            f"{self.code}  {self.contract_id}\n"
            f"  {self.summary}\n"
            f"{self.detail}\n"
            f"  → {self.fix}"
        )


def explain(code: str) -> str:
    """Long-form, after `rustc --explain`."""
    if code not in EXPLANATIONS:
        return (
            f"{code} is not a diagnostic this version emits.\n"
            f"Known: {', '.join(sorted(EXPLANATIONS))}"
        )
    return f"{code}\n\n{EXPLANATIONS[code]}"


def module_path(contract: ModuleContract, module_root: Path) -> Path:
    """`nf_include` is where a module lands in the *generated* pipeline; `module_root` is
    where the source lives. Deliberately not the same path."""
    return module_root / f"{contract.nf_include}.nf"


def check(
    registry: Registry,
    module_root: Path,
    measurements: MeasurementRegistry | None = None,
) -> list[Diagnostic]:
    """Every way a contract disagrees with the module it claims to describe.

    Sorted, because these are printed and byte-identical output is a hard requirement.

    `measurements` is optional because `check` is called from places that have none, and
    M0106 cannot be evaluated without one. Silence beats a wrong answer.
    """
    found: list[Diagnostic] = []
    for contract in registry.all():
        path = module_path(contract, module_root)
        if not path.exists():
            found.append(
                Diagnostic(
                    code="M0100",
                    contract_id=contract.id,
                    summary="unverified: no module source to check this contract against",
                    detail=f"    looked for {path}",
                    fix="vendor the module, or accept that this contract cannot be curated",
                )
            )
            continue
        found += _against(contract, ModuleSpec.parse(path), path)
    if measurements is not None:
        found += _meta_keys(registry, module_root, measurements)
    return sorted(found, key=lambda d: (d.contract_id, d.code, d.detail))


def _against(contract: ModuleContract, spec: ModuleSpec, path: Path) -> list[Diagnostic]:
    found: list[Diagnostic] = []

    if contract.nf_process != spec.process:
        found.append(
            Diagnostic(
                code="M0101",
                contract_id=contract.id,
                summary=f"process {contract.nf_process!r} is not what this module declares",
                detail=f"    {path}   process {spec.process} {{",
                fix=f"nf_process: {spec.process}",
            )
        )

    signature = contract.input_signature()
    if len(signature) != len(spec.inputs):
        found.append(
            Diagnostic(
                code="M0102",
                contract_id=contract.id,
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
                    code="M0103",
                    contract_id=contract.id,
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
                    code="M0104",
                    contract_id=contract.id,
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
        if port.name not in emitted:
            found.append(
                Diagnostic(
                    code="M0105",
                    contract_id=contract.id,
                    summary=f"the module emits no channel named {port.name!r}",
                    detail=f"    {path}   emit: {', '.join(sorted(emitted)) or '(none)'}",
                    fix=f"rename the port to one of: {', '.join(sorted(emitted)) or '(none)'}",
                )
            )

    if contract.container and spec.container and contract.container != spec.container:
        found.append(
            Diagnostic(
                code="M0107",
                contract_id=contract.id,
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
    registry: Registry, module_root: Path, measurements: MeasurementRegistry
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
        path = module_path(contract, module_root)
        if not path.exists():
            every_module_was_readable = False
            continue
        for entry in ModuleSpec.parse(path).meta_reads:
            if entry.variable == "meta" and entry.key not in _ALWAYS_SET:
                read.setdefault(entry.key, contract.id)

    found = [
        Diagnostic(
            code="M0106",
            contract_id=contract_id,
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
    # before assertion, which is the same rule M0100 exists to state.
    if every_module_was_readable:
        found += [
            Diagnostic(
                code="M0106",
                contract_id=f"measurements/{declared[key]}",
                summary=f"meta_key {key!r} is declared and no module in this registry reads it",
                detail="    the value would be set on the channel and never consulted",
                fix=f"remove `meta_key: {key}`, or add a module that reads it",
            )
            for key in sorted(set(declared) - set(read))
        ]
    return found
