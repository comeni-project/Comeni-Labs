# Conformance Checking Implementation Plan

> **Plan 1.6.** Execute after Plan 1.5 (complete) and **before** Plan 2.5 — see the execution
> order in [`docs/internal/README.md`](../README.md). Implements
> [`docs/design/conformance.md`](../../design/conformance.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax for
> tracking. Do **not** farm the tasks out with subagent-driven-development — subagents are for
> review and design only. This matches the execution decision recorded in `CLAUDE.md`.

**Goal:** Make `mendel build` refuse to emit a pipeline whose contracts disagree with the modules
they claim to describe, and say precisely what to write instead.

**Architecture:** A `ModuleSpec` parsed from the vendored `main.nf` and `meta.yml` becomes the
ground truth a contract is checked against — the same component the forge later uses to *generate*
contracts rather than check them. Checking is a separate stage called by the CLI, not folded into
`Registry.load`, so it stays independently testable and loading stays free of filesystem
archaeology.

**Tech Stack:** Python 3.12, Pydantic v2, `re`, `pathlib`, `yaml`, pytest, ruff, `uv` workspace.
No AI, no network, no new dependency.

## Global Constraints

- **`ModuleSpec` lives in `mendel-compiler`, not `comeni-core`.** `re` is not on `comeni-core`'s
  closed allowlist in `tests/test_purity.py`, and the guard is right: `comeni-core` must not know
  what Nextflow is, because its IR is the platform-neutral interface Wiener will consume. Do not
  "fix" this by widening the allowlist.
- `mendel-compiler` is under a **banlist**, so `re` is already fine there. It needs no new import
  beyond what `emit.py` already uses.
- Determinism: same goal → byte-identical `.nf`. Diagnostics are sorted before printing.
- Ruff line length 100. `make check` passes before every commit.
- **Read every Groovy fragment out of `vendor/modules/**/main.nf`, never out of this plan.** The
  shapes quoted here were measured on 2026-08-05 and should be re-measured.
- **Conformance is a hard error where module source exists, and an `unverified` marker where it
  does not.** A laboratory wrapping a bare container has no nf-core-style module directory; that
  is legitimate, not an error.

## What the parser must handle

Measured across the whole vendored tree — every input line is one of four shapes:

```
 15    tuple val(_), path(_)
  2    tuple val(_), path(_), path(_)
  3    val <name>
  1    tuple val(_), path(_), path(_), path(_), path(_), path(_)
```

Plus one wrinkle to not trip on: `path(reads, stageAs: "input*/*")` carries extra arguments
inside the parentheses, and `emit:` lines may also carry `optional:true` and `topic: versions`.

---

## File Structure

```
packages/mendel-compiler/src/mendel_compiler/
├─ modulespec.py     NEW — parse main.nf + meta.yml into a ModuleSpec
├─ conformance.py    NEW — Diagnostic, the checks, `explain`
├─ cli.py            MODIFY — run the check; `mendel explain`
packages/comeni-core/src/comeni_core/
├─ ir.py             MODIFY — PipelineIR.unverified
tests/
├─ test_modulespec.py    NEW — parses the real vendored tree
├─ test_conformance.py   NEW — each check, with a contract doctored to fail it
├─ test_spine_contracts.py  MODIFY — arity/container tests migrate into the checker
.github/workflows/ci.yml   MODIFY — lint + preview in the fast lane
```

**Ordering rationale.** The parser first, because every check reads a `ModuleSpec`. The four
mechanical checks before the two novel ones, so the diagnostic machinery is proven on easy cases.
CLI integration after the checks exist to integrate. The gate ladder last among code tasks —
independent of everything above, and the cheapest win in the plan.

---

### Task 1: `ModuleSpec` — the module, parsed

**Files:**
- Create: `packages/mendel-compiler/src/mendel_compiler/modulespec.py`
- Test: `tests/test_modulespec.py`

**Interfaces:**
- Consumes: the vendored tree under `vendor/modules/`
- Produces: `InputSlot(position, kinds, names)`; `MetaRead(variable, key)`;
  `DocumentedInput(name, description)`; `ModuleSpec(process, inputs, emits, container,
  meta_reads, reads_ext_args, documented)`; `ModuleSpec.parse(main_nf: Path) -> ModuleSpec`

- [ ] **Step 1: Write the failing test**

```python
"""The vendored module is the specification. This parses it.

Tested against the real tree rather than fixtures, deliberately: a parser for nf-core
modules that works on invented input and not on nf-core is worthless, and the tree is
right there.
"""

import pathlib

import pytest
from mendel_compiler.modulespec import ModuleSpec

VENDOR = pathlib.Path(__file__).parent.parent / "vendor"


def spec(path: str) -> ModuleSpec:
    return ModuleSpec.parse(VENDOR / "modules/nf-core" / path / "main.nf")


def test_it_reads_the_process_name():
    assert spec("star/align").process == "STAR_ALIGN"
    assert spec("subread/featurecounts").process == "SUBREAD_FEATURECOUNTS"


def test_it_reads_every_input_slot_in_order():
    star = spec("star/align")
    assert [s.kinds for s in star.inputs] == [
        ["val", "path"],   # tuple val(meta), path(reads, stageAs: "input*/*")
        ["val", "path"],   # tuple val(meta2), path(index)
        ["val", "path"],   # tuple val(meta3), path(gtf)
        ["val"],           # val star_ignore_sjdbgtf
    ]
    assert star.inputs[0].names == ["meta", "reads"]
    assert star.inputs[3].names == ["star_ignore_sjdbgtf"]


def test_it_survives_stageas_inside_the_parentheses():
    """`path(reads, stageAs: "input*/*")` is one element, not two."""
    assert spec("star/align").inputs[0].names == ["meta", "reads"]


def test_it_reads_a_three_element_tuple():
    """samtools/sort takes tuple val(meta2), path(fasta), path(fai) — width 3."""
    sort = spec("samtools/sort")
    assert sort.inputs[1].kinds == ["val", "path", "path"]


def test_it_reads_a_single_channel_carrying_a_wide_tuple():
    """featurecounts takes one channel of (meta, bams, annotation)."""
    fc = spec("subread/featurecounts")
    assert len(fc.inputs) == 1
    assert fc.inputs[0].kinds == ["val", "path", "path"]


def test_it_reads_emit_labels():
    star = spec("star/align")
    assert "bam" in star.emits
    assert "log_final" in star.emits


def test_it_ignores_optional_and_topic_on_an_emit_line():
    """`, optional:true, emit: bam` and `, emit: versions_star, topic: versions` both
    appear. Only the emit name is wanted."""
    star = spec("star/align")
    assert "true" not in star.emits
    assert "versions" not in star.emits
    assert "versions_star" in star.emits


def test_it_reads_the_container():
    assert spec("subread/featurecounts").container.startswith("quay.io/biocontainers/subread")


def test_it_reads_which_meta_keys_the_script_uses():
    """The finding that produced `-s 0`: featurecounts reads meta.strandedness, which
    nf-core's own guidelines say is not a standard key."""
    fc = spec("subread/featurecounts")
    keys = {r.key for r in fc.meta_reads}
    assert {"id", "single_end", "strandedness"} <= keys


def test_it_distinguishes_meta_from_meta2():
    """`meta2.id` belongs to a reference channel, not the reads channel. Conflating them
    would make M0106 demand a measurement for the genome's id."""
    star = spec("star/align")
    variables = {r.variable for r in star.meta_reads}
    assert "meta" in variables


def test_it_notices_whether_the_module_reads_ext_args():
    assert spec("star/align").reads_ext_args is True


def test_it_reads_input_documentation_from_meta_yml():
    genome = spec("star/genomegenerate")
    fasta = next(d for d in genome.documented if d.name == "fasta")
    assert "genome" in fasta.description.lower()


def test_every_vendored_module_parses():
    """A parser that works on the six modules someone tested it against is not a parser."""
    failures = []
    for main_nf in sorted(VENDOR.rglob("modules/nf-core/**/main.nf")):
        try:
            parsed = ModuleSpec.parse(main_nf)
            assert parsed.process, main_nf
            assert parsed.inputs, main_nf
        except Exception as exc:  # noqa: BLE001 — the message is the point
            failures.append(f"{main_nf}: {exc}")
    assert failures == [], "\n".join(failures)


def test_a_missing_module_raises_rather_than_returning_empty():
    with pytest.raises(FileNotFoundError):
        ModuleSpec.parse(VENDOR / "modules/nf-core/nope/main.nf")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_modulespec.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_compiler.modulespec'`

- [ ] **Step 3: Write `modulespec.py`**

```python
"""The vendored module, parsed. The specification a contract is checked against.

A `ModuleContract` is a hand-written binding to a foreign, dynamically-typed unit, and the
bindgen literature is unambiguous about what happens next: "the declarations need to be
kept in sync, and the toolchain wouldn't help with this — mismatches would be silently
ignored, hiding problems that would arise later." That is exactly how a contract came to
call STAR with an empty tuple where the genome belongs.

This lives in `mendel-compiler` rather than `comeni-core` because it reads Nextflow DSL and
`comeni-core` must not know what Nextflow is — its IR is the platform-neutral interface
Wiener will consume. The purity guard is what made that argument; `re` is not on the core's
allowlist, and asking why gave the better answer.

Deliberately a regex parser rather than a Groovy grammar. Every input line in the vendored
tree is one of four shapes, and a real parser would be a dependency, a maintenance surface
and a reason to stop checking when it breaks. If nf-core adopts a syntax this cannot read,
the right response is to notice loudly — `parse` raises — not to guess.
"""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

_PROCESS = re.compile(r"^process\s+(\w+)\s*\{", re.M)
_INPUT_BLOCK = re.compile(r"^    input:\n(.*?)^    (?:output|script|stub|exec):", re.S | re.M)
_OUTPUT_BLOCK = re.compile(r"^    output:\n(.*?)^    (?:script|stub|exec|when):", re.S | re.M)
_ELEMENT = re.compile(r"\b(val|path|eval|env|stdout)\s*\(")
_EMIT = re.compile(r"\bemit:\s*(\w+)")
_META = re.compile(r"\b(meta\d*)\.(\w+)")
_CONTAINER = re.compile(r"container\s+\"(.*?)\"", re.S)


class InputSlot(BaseModel):
    """One channel the process declares, and the shape of its elements."""

    model_config = ConfigDict(extra="forbid")

    position: int
    kinds: list[str]
    """`['val', 'path']` for `tuple val(meta), path(fasta)`."""
    names: list[str]
    """`['meta', 'fasta']`. Best-effort: an element may be a literal rather than a name."""

    @property
    def width(self) -> int:
        """Tuple arity. `NfInput.empty` must equal this or Nextflow dies on a null path."""
        return len(self.kinds)

    @property
    def needs_a_file(self) -> bool:
        """True if any element is a `path(...)`, so a placeholder here is suspicious."""
        return "path" in self.kinds


class MetaRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variable: str
    """`meta`, `meta2`, … — different channels carry different maps."""
    key: str


class DocumentedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str


class ModuleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process: str
    inputs: list[InputSlot] = Field(default_factory=list)
    emits: list[str] = Field(default_factory=list)
    container: str | None = None
    meta_reads: list[MetaRead] = Field(default_factory=list)
    reads_ext_args: bool = False
    documented: list[DocumentedInput] = Field(default_factory=list)

    @classmethod
    def parse(cls, main_nf: Path) -> "ModuleSpec":
        source = main_nf.read_text()

        process = _PROCESS.search(source)
        if process is None:
            raise ValueError(f"{main_nf}: no `process NAME {{` declaration")

        container = _CONTAINER.search(source)
        return cls(
            process=process.group(1),
            inputs=_slots(source, main_nf),
            emits=_emits(source),
            # The last quoted string in the container ternary is the one that applies —
            # nf-core 4.x puts singularity first and docker second.
            container=(
                re.findall(r"'([^']+)'", container.group(1))[-1] if container else None
            ),
            meta_reads=[
                MetaRead(variable=v, key=k) for v, k in dict.fromkeys(_META.findall(source))
            ],
            reads_ext_args="task.ext.args" in source,
            documented=_documented(main_nf.parent / "meta.yml"),
        )


def _slots(source: str, main_nf: Path) -> list[InputSlot]:
    block = _INPUT_BLOCK.search(source)
    if block is None:
        raise ValueError(f"{main_nf}: no `input:` block")
    slots = []
    for line in block.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        kinds = _ELEMENT.findall(stripped)
        if kinds:
            names = _names(stripped, len(kinds))
        elif stripped.split(maxsplit=1)[0] in {"val", "path", "each", "stdin"}:
            # A bare declaration: `val star_ignore_sjdbgtf`.
            head, _, rest = stripped.partition(" ")
            kinds, names = [head], [rest.strip()]
        else:
            continue
        slots.append(InputSlot(position=len(slots), kinds=kinds, names=names))
    return slots


def _names(line: str, expected: int) -> list[str]:
    """First identifier inside each `kind(...)`.

    `path(reads, stageAs: "input*/*")` is one element named `reads`; the extra arguments
    are staging instructions, not elements. An element whose contents are an expression —
    `val("${task.process}")` — yields an empty name, which is honest: it has none.
    """
    found = [
        (match[0] or "").strip()
        for match in re.findall(r"\b(?:val|path|eval|env|stdout)\s*\(\s*([\w]*)", line)
    ]
    return (found + [""] * expected)[:expected]


def _emits(source: str) -> list[str]:
    block = _OUTPUT_BLOCK.search(source)
    return list(dict.fromkeys(_EMIT.findall(block.group(1)))) if block else []


def _documented(meta_yml: Path) -> list[DocumentedInput]:
    """nf-core's `input:` is a list of lists of single-key maps. Walk it defensively —
    the shape has changed twice upstream and a parse failure here must not block a build
    over documentation."""
    if not meta_yml.exists():
        return []
    data = yaml.safe_load(meta_yml.read_text()) or {}
    found: list[DocumentedInput] = []

    def visit(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            for name, body in node.items():
                if isinstance(body, dict) and "description" in body:
                    found.append(
                        DocumentedInput(
                            name=str(name), description=str(body["description"]).strip()
                        )
                    )
                else:
                    visit(body)

    visit(data.get("input", []))
    return found
```

- [ ] **Step 4: Run tests and lint**

Run: `uv run pytest tests/test_modulespec.py -v && uv run ruff check .`
Expected: PASS, 13 tests. `test_every_vendored_module_parses` is the one that matters — if it
fails, the parser is wrong about a shape that actually exists, and the fix is the parser rather
than the test.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-compiler/src/mendel_compiler/modulespec.py tests/test_modulespec.py
git commit -m "feat(compiler): parse a vendored module into a ModuleSpec"
```

---

### Task 2: The four mechanical checks

**Files:**
- Create: `packages/mendel-compiler/src/mendel_compiler/conformance.py`
- Test: `tests/test_conformance.py`

**Interfaces:**
- Consumes: `ModuleSpec` (Task 1), `Registry`, `ModuleContract`
- Produces: `Diagnostic(code, contract_id, summary, detail, fix)`;
  `check(registry, module_root) -> list[Diagnostic]`; codes `M0101`, `M0102`, `M0103`, `M0105`,
  `M0107`

> **The spec says six checks; this plan implements seven.** `M0107` is the container match,
> which already exists as `test_contract_containers_match_the_vendored_modules`. It is
> conformance by any definition, and leaving it in a test file while its five siblings live in a
> checker would be filing by accident of history. Update the spec's table when this lands.

- [ ] **Step 1: Write the failing test**

```python
"""Each check, against a contract doctored to fail exactly it.

A conformance checker verified only on contracts that pass is a checker nobody has seen
work. Every test here breaks one thing and asserts one code.
"""

import pathlib

import pytest
from comeni_core.registry import Registry
from mendel_compiler.conformance import check
from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent
VENDOR = ROOT / "vendor"


@pytest.fixture
def registry():
    return layers.load(ROOT / "examples").registry


def _doctored(registry: Registry, contract_id: str, **changes) -> Registry:
    """The registry with one contract altered. Returns a copy; the fixture is untouched."""
    contracts = dict(registry.contracts)
    contracts[contract_id] = contracts[contract_id].model_copy(update=changes)
    return Registry(contracts=contracts)


def codes(diagnostics) -> set[str]:
    return {d.code for d in diagnostics}


def test_the_shipped_registry_is_conformant(registry):
    """The baseline. If this fails, the checker or the contracts are wrong — and after
    Plan 1.5 the contracts have been run against real data, so suspect the checker."""
    assert check(registry, VENDOR) == []


def test_M0101_a_process_name_that_does_not_exist(registry):
    doctored = _doctored(registry, "nf-core/star/align@1.11.0", nf_process="STAR_ALIGNN")
    assert "M0101" in codes(check(doctored, VENDOR))


def test_M0102_wrong_number_of_channels(registry):
    from comeni_core.contract import NfInput

    doctored = _doctored(
        registry, "nf-core/star/align@1.11.0", nf_inputs=[NfInput(ports=["reads"])]
    )
    assert "M0102" in codes(check(doctored, VENDOR))


def test_M0103_an_empty_placeholder_of_the_wrong_width(registry):
    from comeni_core.contract import NfInput

    sort = registry.get("nf-core/samtools/sort@1.21.0")
    wrong = [
        NfInput(ports=["bam"]),
        NfInput(empty=2, because="deliberately wrong width for this test"),
        NfInput(literal="bai"),
    ]
    doctored = _doctored(registry, sort.id, nf_inputs=wrong)
    diagnostics = check(doctored, VENDOR)
    assert "M0103" in codes(diagnostics)
    assert "3" in next(d for d in diagnostics if d.code == "M0103").detail


def test_M0105_an_output_the_module_does_not_emit(registry):
    from comeni_core.contract import OutputPort

    doctored = _doctored(
        registry,
        "nf-core/star/align@1.11.0",
        produces=[OutputPort(name="bams", type_id="alignment.bam")],
    )
    diagnostics = check(doctored, VENDOR)
    assert "M0105" in codes(diagnostics)
    # The fix must name what the module *does* emit, or it is half a diagnostic.
    assert "bam" in next(d for d in diagnostics if d.code == "M0105").fix


def test_M0107_a_container_that_has_drifted(registry):
    doctored = _doctored(
        registry, "nf-core/star/align@1.11.0", container="quay.io/biocontainers/star:2.7.0"
    )
    assert "M0107" in codes(check(doctored, VENDOR))


def test_a_contract_with_no_module_source_is_unverified_not_broken(registry, tmp_path):
    """A laboratory wrapping a bare container has no nf-core-style module directory.
    That is legitimate, and must not fail a build."""
    diagnostics = check(registry, tmp_path)
    assert codes(diagnostics) == {"M0100"}
    assert all("unverified" in d.summary for d in diagnostics)


def test_diagnostics_are_sorted(registry):
    """Byte-identical output is a hard requirement, and these are printed."""
    doctored = _doctored(registry, "nf-core/star/align@1.11.0", nf_process="NOPE")
    twice = [check(doctored, VENDOR), check(doctored, VENDOR)]
    assert [d.model_dump() for d in twice[0]] == [d.model_dump() for d in twice[1]]


def test_every_diagnostic_says_what_to_write_instead(registry):
    """The rule from the design record: a diagnostic that does not say what to write is
    half a diagnostic."""
    doctored = _doctored(registry, "nf-core/star/align@1.11.0", nf_process="NOPE")
    assert all(d.fix for d in check(doctored, VENDOR))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_conformance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mendel_compiler.conformance'`

- [ ] **Step 3: Write `conformance.py`**

```python
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
        return f"{code} is not a diagnostic this version emits.\nKnown: {', '.join(sorted(EXPLANATIONS))}"
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
        found.append(Diagnostic(
            code="M0101", contract_id=contract.id,
            summary=f"process {contract.nf_process!r} is not what this module declares",
            detail=f"    {path}   process {spec.process} {{",
            fix=f"nf_process: {spec.process}",
        ))

    signature = contract.input_signature()
    if len(signature) != len(spec.inputs):
        found.append(Diagnostic(
            code="M0102", contract_id=contract.id,
            summary=(
                f"the contract declares {len(signature)} channels; "
                f"the module takes {len(spec.inputs)}"
            ),
            detail="\n".join(
                f"    slot {slot.position}: {' '.join(slot.kinds)}  ({', '.join(slot.names)})"
                for slot in spec.inputs
            ),
            fix=f"nf_inputs needs exactly {len(spec.inputs)} entries, in the module's order",
        ))
        return found  # positional checks below are meaningless once the count is wrong

    for entry, slot in zip(signature, spec.inputs, strict=True):
        if entry.empty and entry.empty != slot.width:
            found.append(Diagnostic(
                code="M0103", contract_id=contract.id,
                summary=f"slot {slot.position} placeholder is width {entry.empty}, "
                        f"the module declares {slot.width}",
                detail=f"    {path}   {' '.join(slot.kinds)}",
                fix=f"{{empty: {slot.width}, because: ...}}",
            ))

    emitted = set(spec.emits)
    for port in contract.produces:
        if port.name not in emitted:
            found.append(Diagnostic(
                code="M0105", contract_id=contract.id,
                summary=f"the module emits no channel named {port.name!r}",
                detail=f"    {path}   emit: {', '.join(sorted(emitted)) or '(none)'}",
                fix=f"rename the port to one of: {', '.join(sorted(emitted)) or '(none)'}",
            ))

    if contract.container and spec.container and contract.container != spec.container:
        found.append(Diagnostic(
            code="M0107", contract_id=contract.id,
            summary="the container has drifted from the module",
            detail=f"    module   {spec.container}\n    contract {contract.container}",
            fix=f"container: {spec.container}",
        ))

    return found
```

- [ ] **Step 4: Run tests and lint**

Run: `uv run pytest tests/test_conformance.py -v && uv run ruff check .`
Expected: PASS. `test_the_shipped_registry_is_conformant` is the one to watch — after Plan 1.5
these contracts have been run against real data, so a failure here is far more likely to be the
checker than the contract.

- [ ] **Step 5: Commit**

```bash
git add packages/mendel-compiler/src/mendel_compiler/conformance.py tests/test_conformance.py
git commit -m "feat(compiler): conformance — a contract must tell the truth about its module"
```

---

### Task 3: The two checks that catch the real defects

`M0104` and `M0106` are the reason this plan exists. Both were earned by a pipeline that ran
and produced wrong output.

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/conformance.py`
- Test: `tests/test_conformance.py`

**Interfaces:**
- Consumes: `ModuleSpec.meta_reads`, `InputSlot.needs_a_file`, `MeasurementRegistry`
- Produces: `check(registry, module_root, measurements=None)` — the signature gains an optional
  measurement registry, because `M0106` cannot be evaluated without one

- [ ] **Step 1: Write the failing test**

```python
def test_M0104_a_placeholder_where_the_module_wants_a_file(registry):
    """The missing genome. STAR_GENOMEGENERATE slot 0 is path(fasta), and for weeks the
    contract supplied an empty tuple — through a green suite and a passing stub gate."""
    from comeni_core.contract import NfInput

    doctored = _doctored(
        registry,
        "nf-core/star/genomegenerate@1.11.0",
        consumes=registry.get("nf-core/star/genomegenerate@1.11.0").consumes[1:],
        nf_inputs=[NfInput(empty=2), NfInput(ports=["gtf"])],
    )
    diagnostics = check(doctored, VENDOR)
    assert "M0104" in codes(diagnostics)
    detail = next(d for d in diagnostics if d.code == "M0104").detail
    assert "fasta" in detail
    assert "genome" in detail.lower(), "meta.yml's description must reach the diagnostic"


def test_M0104_is_satisfied_by_saying_why(registry):
    """samtools/sort genuinely does not need a reference to write BAM. The check is not
    'never use a placeholder' — it is 'say which of the two this is'."""
    assert "M0104" not in codes(check(registry, VENDOR))


def test_M0106_a_meta_key_the_module_reads_that_nothing_sets(registry, tmp_path):
    """The -s 0 defect, made unrepresentable. featurecounts reads meta.strandedness; if no
    declared measurement carries it, the module silently uses its default."""
    from comeni_core.measurement import MeasurementRegistry

    (tmp_path / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
    thin = MeasurementRegistry.load(tmp_path)

    diagnostics = check(registry, VENDOR, measurements=thin)
    assert "M0106" in codes(diagnostics)
    assert any("strandedness" in d.summary for d in diagnostics if d.code == "M0106")


def test_M0106_is_satisfied_by_the_shipped_measurements(registry):
    """strandedness declares meta_key: strandedness, and paired declares single_end."""
    measurements = layers.load(ROOT / "examples").measurements
    assert "M0106" not in codes(check(registry, VENDOR, measurements=measurements))


def test_M0106_the_other_direction_a_meta_key_nobody_reads(registry, tmp_path):
    """A declaration with no effect. Dead code, in data."""
    from comeni_core.measurement import MeasurementRegistry

    (tmp_path / "strandedness.yml").write_text(
        "kind: enum\nvalues: [forward, reverse, unstranded]\n"
        "describes: fastq.reads\nmeta_key: strandedness\n"
    )
    (tmp_path / "paired.yml").write_text(
        "kind: boolean\ndescribes: fastq.reads\nmeta_key: single_end\n"
    )
    (tmp_path / "moon_phase.yml").write_text(
        "kind: enum\nvalues: [waxing, waning]\n"
        "describes: fastq.reads\nmeta_key: moon_phase\n"
    )
    measurements = MeasurementRegistry.load(tmp_path)

    diagnostics = check(registry, VENDOR, measurements=measurements)
    dead = [d for d in diagnostics if d.code == "M0106" and "moon_phase" in d.summary]
    assert dead, "a meta_key no module reads should be reported"
    assert "no module in this registry reads" in dead[0].summary


def test_M0106_does_not_fire_without_a_measurement_registry(registry):
    """`check` is called from places that have no measurements. Silence beats a wrong
    answer."""
    assert "M0106" not in codes(check(registry, VENDOR))


def test_M0106_ignores_meta_id_and_secondary_meta_variables(registry):
    """`meta.id` is set by every entry channel, and `meta2.id` belongs to a reference
    channel rather than the reads. Demanding a measurement for either would be noise, and
    a check that cries wolf is a check people switch off."""
    measurements = layers.load(ROOT / "examples").measurements
    diagnostics = [d for d in check(registry, VENDOR, measurements=measurements)
                   if d.code == "M0106"]
    assert not any("id" == d.summary.split("'")[1] for d in diagnostics if "'" in d.summary)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_conformance.py -v -k "M0104 or M0106"`
Expected: FAIL — `check()` takes no `measurements` argument, and neither code is emitted.

- [ ] **Step 3: Add `M0104`**

In `_against`, inside the `zip` loop that already emits `M0103`:

```python
        if entry.empty and slot.needs_a_file and not entry.because:
            documented = next(
                (d for d in spec.documented if d.name in slot.names), None
            )
            described = f'\n    meta.yml   {documented.name}: "{documented.description}"' \
                if documented else ""
            found.append(Diagnostic(
                code="M0104", contract_id=contract.id,
                summary=(
                    f"slot {slot.position} declares "
                    f"{'path(' + (documented.name if documented else slot.names[-1]) + ')'}"
                    " and the contract supplies a placeholder"
                ),
                detail=f"    {path}   {' '.join(slot.kinds)}"
                       f"  ({', '.join(n for n in slot.names if n)}){described}",
                fix=(
                    "declare a port with a type_id for it, or say why the type system "
                    "does not model it with `because`"
                ),
            ))
```

- [ ] **Step 4: Add `M0106`**

Change the signature and thread the registry through:

```python
def check(
    registry: Registry,
    module_root: Path,
    measurements: "MeasurementRegistry | None" = None,
) -> list[Diagnostic]:
```

Import `MeasurementRegistry` from `comeni_core.measurement`, and after the per-contract loop:

```python
    if measurements is not None:
        found += _meta_keys(registry, module_root, measurements)
```

Then:

```python
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
    for contract in registry.all():
        path = module_path(contract, module_root)
        if not path.exists():
            continue
        for entry in ModuleSpec.parse(path).meta_reads:
            if entry.variable == "meta" and entry.key not in _ALWAYS_SET:
                read.setdefault(entry.key, contract.id)

    found = [
        Diagnostic(
            code="M0106", contract_id=contract_id,
            summary=f"the module reads meta.{key!r} and no declared measurement sets it",
            detail=f"    it will silently use the module's own default",
            fix=f"declare a measurement with `meta_key: {key}`, or accept the default knowingly",
        )
        for key, contract_id in sorted(read.items())
        if key not in declared
    ]
    found += [
        Diagnostic(
            code="M0106", contract_id=f"measurements/{declared[key]}",
            summary=f"meta_key {key!r} is declared and no module in this registry reads it",
            detail="    the value would be set on the channel and never consulted",
            fix=f"remove `meta_key: {key}`, or add a module that reads it",
        )
        for key in sorted(set(declared) - set(read))
    ]
    return found
```

- [ ] **Step 5: Run tests and lint**

Run: `make check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/mendel-compiler tests/test_conformance.py
git commit -m "feat(compiler): M0104 and M0106 — the two checks the defects earned"
```

---

### Task 4: Wire it into the build

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/ir.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Test: `tests/test_conformance_cli.py`

**Interfaces:**
- Consumes: `check`, `explain` (Tasks 2–3)
- Produces: `PipelineIR.unverified: list[ContractId]`; `mendel build` exits 2 on any diagnostic
  other than `M0100`; `mendel explain <code>`

> **The design record says `unverified` sits "beside `shadowed`" on the IR. `PipelineIR.shadowed`
> does not exist** — it arrives in Plan 2.5 Task 4. They are independent fields; add `unverified`
> here and let 2.5 add its neighbour.

- [ ] **Step 1: Write the failing test**

```python
import pathlib
import subprocess
import sys

from mendel_compiler.cli import main

ROOT = pathlib.Path(__file__).parent.parent


def test_a_conformant_build_succeeds(tmp_path):
    assert main([
        "build", "--goal", str(ROOT / "examples/rnaseq-goal.yml"),
        "--out", str(tmp_path / "p"), "--root", str(ROOT),
    ]) == 0


def test_a_nonconformant_contract_refuses_to_build(tmp_path, capsys):
    """The whole point: `mendel build` succeeding must mean something."""
    import shutil

    layer = tmp_path / "examples"
    shutil.copytree(ROOT / "examples", layer)
    star = next(layer.rglob("star-align.yml"))
    star.write_text(star.read_text().replace("nf_process: STAR_ALIGN", "nf_process: STAR_ALIGNN"))

    code = main([
        "build", "--goal", str(ROOT / "examples/rnaseq-goal.yml"),
        "--out", str(tmp_path / "p"), "--root", str(ROOT), "--registry", str(layer),
    ])
    assert code == 2
    err = capsys.readouterr().err
    assert "M0101" in err
    assert "nf_process: STAR_ALIGN" in err, "the diagnostic must say what to write"
    assert not (tmp_path / "p" / "main.nf").exists(), "a refused build emits nothing"


def test_an_unverified_contract_warns_and_builds(tmp_path, capsys):
    """A lab wrapping a bare container is legitimate. It is recorded, not refused."""
    code = main([
        "build", "--goal", str(ROOT / "examples/rnaseq-goal.yml"),
        "--out", str(tmp_path / "p"), "--root", str(tmp_path),
    ])
    assert code == 0
    assert "unverified" in capsys.readouterr().err


def test_unverified_contracts_reach_the_ir(tmp_path):
    import json

    main([
        "build", "--goal", str(ROOT / "examples/rnaseq-goal.yml"),
        "--out", str(tmp_path / "p"), "--root", str(tmp_path),
    ])
    ir = json.loads((tmp_path / "p" / "pipeline.ir.json").read_text())
    assert ir["unverified"], "a publish bundle must carry which contracts were unchecked"


def test_mendel_explain_prints_the_long_form():
    result = subprocess.run(
        [sys.executable, "-m", "mendel_compiler.cli", "explain", "M0104"],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )
    assert result.returncode == 0
    assert "path(" in result.stdout
    assert "because" in result.stdout


def test_mendel_explain_on_an_unknown_code_lists_the_known_ones():
    result = subprocess.run(
        [sys.executable, "-m", "mendel_compiler.cli", "explain", "M9999"],
        capture_output=True, text=True, check=False, cwd=ROOT,
    )
    assert "M0104" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_conformance_cli.py -v`
Expected: FAIL — argparse rejects `explain`, and a doctored contract still builds.

- [ ] **Step 3: Add `unverified` to the IR**

In `packages/comeni-core/src/comeni_core/ir.py`, add to `PipelineIR`:

```python
    unverified: list[ContractId] = Field(default_factory=list)
    """Contracts whose module source was not present, so nothing checked them.

    Carried on the artifact rather than only printed, because it reaches a publish bundle:
    a curator may refuse to curate an unverified contract. A claim about a module, with no
    module to check it against, is a claim without evidence.
    """
```

- [ ] **Step 4: Run the check in the CLI**

In `cli.py`, add the command and the flag:

```python
    parser.add_argument("command", choices=["build", "profile", "publish", "explain"])
    parser.add_argument("code", nargs="?", default=None, help="a diagnostic code, for `explain`")
```

Handle `explain` before anything loads:

```python
    if args.command == "explain":
        if not args.code:
            parser.error("explain needs a code, e.g. `mendel explain M0104`")
        print(explain(args.code))
        return 0
```

After `layers.load(...)` and before resolving:

```python
    # Conformance: does each contract tell the truth about its module? `-stub-run` cannot
    # answer this — nf-core stubs never read their inputs, so a process handed an empty
    # tuple where a genome belongs is exactly as green as one handed a genome.
    diagnostics = conformance.check(
        registry, args.root / "vendor", measurements=loaded.measurements
    )
    unverified = [d.contract_id for d in diagnostics if d.code == "M0100"]
    blocking = [d for d in diagnostics if d.code != "M0100"]
    for diagnostic in diagnostics:
        print(diagnostic.render(), file=sys.stderr)
    if blocking:
        print(
            f"\nmendel: {len(blocking)} contract(s) disagree with their modules. "
            f"Nothing was emitted.\n"
            f"`mendel explain {blocking[0].code}` for the long form.",
            file=sys.stderr,
        )
        return 2
```

Set it on the IR:

```python
    ir = resolve(goal, registry, rules, layer_names=[p.name for p in loaded.paths])
    ir.unverified = unverified
```

with `from mendel_compiler import conformance` and `from mendel_compiler.conformance import explain`.

> **`args.root / "vendor"` is the module root**, not `nf_include`'s prefix. `nf_include` says
> where a module lands in the *generated* pipeline; `vendor/` is where this repository keeps the
> source. Deliberately not the same path, and `module_path()` already encodes that.

- [ ] **Step 5: Run the full suite and lint**

Run: `make check`
Expected: PASS. Several existing CLI tests build against `--root tmp_path` with no `vendor/`; they
will now emit `M0100` warnings and still exit 0, which is correct. If one asserts on exact stderr,
update it.

- [ ] **Step 6: Commit**

```bash
git add packages/ tests/test_conformance_cli.py
git commit -m "feat(compiler): mendel build refuses a contract that disagrees with its module"
```

---

### Task 5: Wire the gate ladder

`Gate.PREVIEW` exists and is connected to nothing. It catches name resolution in ~15 seconds with
**no Docker**, so it belongs in the fast pull-request lane beside `lint` — not nightly.

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `Makefile`
- Test: `packages/mendel-compiler/tests/test_gates.py`

- [ ] **Step 1: Write the failing test**

```python
def test_every_gate_that_executes_processes_names_a_container_engine():
    """Gate.TEST ran `-profile test` with no docker for its whole existence and could
    never have passed. It had never been run, so nothing noticed."""
    from mendel_compiler.gates import _ARGS, Gate

    for gate in (Gate.STUB, Gate.TEST):
        profile = _ARGS[gate][_ARGS[gate].index("-profile") + 1]
        assert "docker" in profile or "singularity" in profile, gate


def test_preview_needs_no_container_engine():
    """It does dataflow analysis without executing, which is why it can sit in the fast
    lane. Adding docker here would cost minutes and buy nothing."""
    from mendel_compiler.gates import _ARGS, Gate

    profile = _ARGS[Gate.PREVIEW][_ARGS[Gate.PREVIEW].index("-profile") + 1]
    assert "docker" not in profile
```

- [ ] **Step 2: Run test to verify it passes, then prove it can fail**

Run: `uv run pytest packages/mendel-compiler/tests/test_gates.py -v`
Expected: PASS.

Now break it: remove `,docker` from `Gate.TEST` in `gates.py`, re-run, confirm the failure names
`Gate.TEST`. Restore it.

**Run this step.** Every guard in this repository that was not watched failing turned out to have
a hole. This one encodes a bug that shipped and survived for the life of the project.

- [ ] **Step 3: Add the gates to the fast lane**

In `.github/workflows/ci.yml`, in the `check` job after the tests step:

```yaml
      - name: Install Nextflow
        uses: nf-core/setup-nextflow@v2

      - name: Emit the spine and check it statically
        run: |
          uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate lint
          uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate preview
        # `lint` is syntax; `preview` is name resolution and dataflow. Neither needs Docker
        # and together they take about 25 seconds. `nextflow lint` alone accepts
        # `STAR_ALIGN.out.NOSUCHCHANNEL`; `-preview` rejects it — measured 2026-08-05.
```

- [ ] **Step 4: Add a make target**

```make
static:         ## conformance + lint + preview — everything checkable without Docker
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate lint
	uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate preview
```

and add `static` to the `.PHONY` line.

- [ ] **Step 5: Verify locally and commit**

Run: `make check && make static`
Expected: PASS, and `gate lint: PASS` then `gate preview: PASS`.

```bash
git add .github/workflows/ci.yml Makefile packages/mendel-compiler/tests/test_gates.py
git commit -m "ci: lint and preview run on every pull request"
```

---

### Task 6: Record it

**Files:**
- Modify: `docs/design/conformance.md` — six checks becomes seven
- Modify: `docs/internal/plans/2026-08-02-mendel-ai-and-forge.md` — the forge depends on this
- Modify: `docs/internal/README.md`, `CLAUDE.md`, `CHANGELOG.md`, `docs/reference/cli.md`
- Create: `docs/internal/journal/<today>.md`

- [ ] **Step 1: Correct the spec's table**

`docs/design/conformance.md` §6.2 lists six checks; seven shipped. Add `M0107` (container) and
`M0100` (unverified) with a line saying they were folded in from existing tests during execution,
because a checker that owns five conformance rules while two live in a test file is filed by
accident of history.

- [ ] **Step 2: Make Plan 2 depend on this**

In `docs/internal/plans/2026-08-02-mendel-ai-and-forge.md`, before Task 8 (`nf-core meta.yml
ingestion`), add:

```markdown
> **Prerequisite: Plan 1.6, conformance checking.** Tasks 8–10 draft contracts for a human to
> approve, and `forge-review.md` §3 calls a `copied` field "zero risk" — which is only true if
> something compared it to the module. `mendel_compiler.conformance.check` is that something,
> and `ModuleSpec` is what these tasks should draft *from* rather than re-parsing modules a
> second way. Two parsers for one file format is the drift this project keeps being bitten by.
```

Then in Task 9 (contract drafting), add a step: **a draft that fails conformance never reaches
the queue** — the forge runs `check()` on its own output and fixes or discards, so a human only
ever reviews drafts that are already true about their module.

- [ ] **Step 3: Update the indexes**

`docs/internal/README.md` — Plan 1.6 becomes complete, Plan 2.5 becomes next.
`CLAUDE.md` — the reading table gains the plan and the spec; add a gotcha:

```markdown
- **A contract is a hand-written FFI binding.** `mendel build` checks every contract against
  the vendored module and refuses to emit if they disagree — `mendel explain M0104`. Where
  module source is absent the contract is marked `unverified` on the IR rather than trusted.
```

`docs/reference/cli.md` — document `mendel explain`, and the conformance stage in `build`.

- [ ] **Step 4: Update `CHANGELOG.md`**

An `Unreleased` entry: conformance checking with seven diagnostics, `mendel explain`,
`PipelineIR.unverified`, and lint + preview on every pull request.

- [ ] **Step 5: Write the journal entry**

Follow `docs/internal/journal/README.md`. Record which of the five Plan 1.5 defects are now
statically unrepresentable, which are not, and why — that is the ratchet, and the next entry
should be able to check whether it held.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: conformance checking, and the forge's dependency on it"
```

---

## Self-Review

**Spec coverage.**

| `conformance.md` | Task |
|---|---|
| §6.1 `ModuleSpec` in `mendel-compiler` | 1 |
| §6.2 `M0101`, `M0102`, `M0103`, `M0105` | 2 |
| §6.2 `M0104`, `M0106` | 3 |
| §6.3 diagnostics, `mendel explain` | 2 (shape), 4 (command) |
| §6.4 build-time hard error, `unverified` on the IR | 4 |
| §5 the gate ladder, `preview` in the PR lane | 5 |
| §7 why this precedes the forge | 6, as a Plan 2 prerequisite |
| §9 the ratchet | 6, in the journal entry |

**Two corrections to the spec, made here rather than discovered later.** The spec says *six*
checks; seven ship, because the container match already existed as a test and belongs with its
siblings — plus `M0100` for unverified, which is a diagnostic even though it is not a failure.
And the spec says `unverified` sits "beside `shadowed`" on the IR; **`PipelineIR.shadowed` does
not exist yet** — it arrives in Plan 2.5 Task 4. The fields are independent.

**Placeholder scan.** No TBDs. Every code step contains runnable code. Task 3 shows the two new
blocks in place rather than repeating `_against` whole, and names the loop each belongs in.

**Type consistency.** `check(registry, module_root, measurements=None)` takes the same three
arguments in Tasks 2, 3 and 4. `Diagnostic` has `code, contract_id, summary, detail, fix`
throughout, and `render()` is used only by the CLI. `ModuleSpec.parse(main_nf: Path)` takes the
`main.nf` itself, not its directory — `module_path()` builds that path and is used by both
`check` and `_meta_keys`. `InputSlot.width` is `len(kinds)`, which is what `NfInput.empty` is
compared against.

**Known risk.** `_meta_keys` parses every module a second time, after `check` already parsed it
per contract. On twelve modules that is free; at two hundred it is not. Left unoptimised
deliberately — a cache is easy and premature, and the first person to notice it being slow will
have a real number to optimise against instead of a guess.

---

## Verification

```bash
uv sync
make check                       # includes conformance; still under a minute
make static                      # lint + preview, no Docker
uv run pytest -m slow -v         # the counts matrix, unchanged by this plan
uv run mendel explain M0104
uv run mendel build --goal examples/rnaseq-goal.yml --out build/ --gate stub
```

Complete when a contract doctored to disagree with its module refuses to build and names what to
write instead, the shipped registry is conformant, `mendel explain` prints the long form, lint and
preview run on every pull request, and `tests/test_modulespec.py::test_every_vendored_module_parses`
passes across the whole vendored tree.
