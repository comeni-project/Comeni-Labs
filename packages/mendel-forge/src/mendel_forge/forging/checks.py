"""What the engine notices about a type question's options, before anyone answers (#452).

Findings are advice, never decisions: they do not pick, remove or refuse an option. The page
shows them as "Engine check", and the drafter and reviewer read them. They are recomputed from
the current items on every read and never stored, so they describe what is there now.

Three checks, each on input questions only (an output's arrival is the tool's own):

- **scope**: nf-core names the per-sample map `meta` and a reference's `meta2`, `meta3` … A
  type with the other `scope` is probably wrong. This is a convention, so the finding says so.
- **duplicate**: two inputs of one tool with the same type are filled from one source.
- **format**: the module's file format (its meta.yml pattern, or the input's name when that is
  a format's name) differs from the format the type ID names.
"""

import re

from comeni_core.declared.signature import split
from mendel_compiler.modulespec import ModuleSpec
from pydantic import BaseModel, JsonValue

from mendel_forge.model import Channel
from mendel_forge.topics import COMPRESSION, _expand

FORMATS: dict[str, str] = {
    "fastq": "fastq", "fq": "fastq",
    "fasta": "fasta", "fa": "fasta", "fna": "fasta", "fas": "fasta", "fsa": "fasta",
    "ffn": "fasta", "faa": "fasta",
    "bam": "bam", "sam": "sam", "cram": "cram", "bai": "bai", "crai": "crai",
    "vcf": "vcf", "bcf": "bcf", "bed": "bed", "gff": "gff", "gff3": "gff", "gtf": "gtf",
    "tsv": "tsv", "csv": "csv", "json": "json", "yaml": "yaml", "yml": "yaml",
    "html": "html", "pdf": "pdf", "txt": "txt", "bigwig": "bigwig", "bw": "bigwig",
    "h5ad": "h5ad", "mtx": "mtx", "newick": "newick", "nwk": "newick",
}
"""Spellings of one file format. Stricter than `topics.ALIASES`, which folds GTF into GFF and
TSV into a table for browsing: here a GFF reader is not a GTF reader."""

_REFERENCE_META = re.compile(r"meta\d+")

Arrival = str  # "sample" | "run"


class QuestionFinding(BaseModel):
    code: str
    """An advisory `MF052x` diagnostic."""
    says: str
    option: str | None = None
    """The option it concerns; none when it concerns the question."""


def arrival(spec: ModuleSpec, name: str) -> Arrival | None:
    """How an input arrives, by its tuple's meta name; none when the module has no meta map."""
    for slot in spec.inputs:
        if name in slot.names and len(slot.names) > 1 and "val" in slot.kinds:
            first = slot.names[slot.kinds.index("val")]
            if first == "meta":
                return "sample"
            if _REFERENCE_META.fullmatch(first):
                return "run"
    return None


def channel_formats(channel: Channel | None, name: str) -> set[str]:
    """The formats a module documents for a channel: its pattern, else its name if a format."""
    found = set()
    for pattern in _expand(channel.pattern or "") if channel else []:
        suffixes = [s.lower() for s in pattern.split(".")[1:]]
        meaningful = [s for s in suffixes if s not in COMPRESSION and s in FORMATS]
        found.update(FORMATS[s] for s in meaningful[-1:])
    if not found and name.lower() in FORMATS:
        found.add(FORMATS[name.lower()])
    return found


def type_format(type_id: str) -> str | None:
    """The format a type ID names: its last segment that is a format (`fastq.reads` → fastq)."""
    for segment in reversed(type_id.split(".")):
        if segment in FORMATS:
            return FORMATS[segment]
    return None


def _effective(value: JsonValue) -> str | None:
    """What a question currently points at: the answer, else the AI's suggestion."""
    if not isinstance(value, dict):
        return None
    return value.get("choice") or value.get("suggested")


def findings(items: dict[str, JsonValue], scopes: dict[str, str], spec: ModuleSpec,
             channels: dict[str, Channel],
             asked: dict[str, dict]) -> dict[str, list[QuestionFinding]]:
    """Findings per question key. `items` holds current values (an answer once answered);
    `asked` the question (its options and suggestion) for each key; `scopes` each declared
    type's scope."""
    prefix = "questions:input_type:"
    keys = sorted(k for k in asked if k.startswith(prefix))
    pointed: dict[str, str] = {}
    for key in keys:
        current = _effective(items.get(key)) or _effective(asked[key])
        if current:
            try:
                pointed[key] = split(current)[0]
            except ValueError:
                continue
    out: dict[str, list[QuestionFinding]] = {}
    for key in keys:
        name = key.removeprefix(prefix)
        found: list[QuestionFinding] = []
        chosen = pointed.get(key)
        comes = arrival(spec, name)
        scope = scopes.get(chosen) if chosen else None
        # A type not declared yet has no scope to compare.
        if comes and scope and scope != comes:
            found.append(QuestionFinding(code="MF0520", option=chosen, says=(
                f"{name} arrives one per {comes} (the module's meta naming suggests so), "
                f"but {chosen} is one per {scope}.")))
        if chosen:
            for other in keys:
                if other != key and pointed.get(other) == chosen:
                    found.append(QuestionFinding(code="MF0521", option=chosen, says=(
                        f"Same type as {other.removeprefix(prefix)}: a tool rarely reads one "
                        "kind of file twice.")))
            documented = channel_formats(channels.get(name), name)
            named = type_format(chosen)
            if documented and named and named not in documented:
                found.append(QuestionFinding(code="MF0522", option=chosen, says=(
                    f"Format: {', '.join(sorted(documented))}, type: {named}.")))
        if found:
            out[key] = found
    return out
