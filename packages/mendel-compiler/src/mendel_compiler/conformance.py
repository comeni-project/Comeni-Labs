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


def check(registry: Registry, module_root: Path) -> list[Diagnostic]:
    """Every way a contract disagrees with the module it claims to describe.

    Sorted, because these are printed and byte-identical output is a hard requirement.
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
