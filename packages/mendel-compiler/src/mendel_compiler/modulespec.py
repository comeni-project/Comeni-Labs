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

from comeni_core import yaml_strict
from pydantic import BaseModel, ConfigDict, Field

_PROCESS = re.compile(r"^process\s+(\w+)\s*\{", re.M)
_INPUT_BLOCK = re.compile(r"^    input:\n(.*?)^    (?:output|script|stub|exec):", re.S | re.M)
_OUTPUT_BLOCK = re.compile(r"^    output:\n(.*?)^    (?:script|stub|exec|when):", re.S | re.M)
_ELEMENT = re.compile(r"\b(val|path|eval|env|stdout)\s*\(")
_NAMED_ELEMENT = re.compile(r"\b(?:val|path|eval|env|stdout)\s*\(\s*(\w*)")
_EMIT = re.compile(r"\bemit:\s*(\w+)")
_META = re.compile(r"\b(meta\d*)\.(\w+)")
_CONTAINER = re.compile(r"container\s+\"(.*?)\"", re.S)
_QUOTED = re.compile(r"'([^']+)'")

_BARE_DECLARATIONS = {"val", "path", "each", "stdin"}


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
    reads_ext_prefix: bool = False
    """Whether the module reads `task.ext.prefix`.

    Absent from three of the ten vendored modules, which is what gives `MD0108` real
    negatives to find rather than a check that can only ever pass."""
    documented: list[DocumentedInput] = Field(default_factory=list)

    @classmethod
    def parse(cls, main_nf: Path) -> "ModuleSpec":
        source = main_nf.read_text()

        process = _PROCESS.search(source)
        if process is None:
            raise ValueError(f"{main_nf}: no `process NAME {{` declaration")

        return cls(
            process=process.group(1),
            inputs=_slots(source, main_nf),
            emits=_emits(source),
            container=_container(source),
            meta_reads=[
                MetaRead(variable=v, key=k) for v, k in dict.fromkeys(_META.findall(source))
            ],
            reads_ext_args="task.ext.args" in source,
            reads_ext_prefix="task.ext.prefix" in source,
            documented=_documented(main_nf.parent / "meta.yml"),
        )


def _container(source: str) -> str | None:
    """The image the process actually runs in.

    nf-core 4.x writes a ternary picking singularity first and docker second, so the *last*
    quoted alternative is the one a docker-profile run uses. A module wrapping a single
    image names it directly and has no alternatives to choose between — that is what a
    laboratory hand-wrapping a container writes, and it must parse rather than crash.
    """
    directive = _CONTAINER.search(source)
    if directive is None:
        return None
    alternatives = _QUOTED.findall(directive.group(1))
    return alternatives[-1] if alternatives else directive.group(1).strip() or None


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
        elif stripped.split(maxsplit=1)[0] in _BARE_DECLARATIONS:
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
    found = [name.strip() for name in _NAMED_ELEMENT.findall(line)]
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
    data = yaml_strict.load(meta_yml) or {}
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
