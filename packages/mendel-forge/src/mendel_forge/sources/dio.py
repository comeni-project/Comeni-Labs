"""PEGiS's central metadata and its classification ontology, parsed.

**Three files, three jobs, and conflating any two of them is the mistake this module exists to
prevent.** They live together in `pegi3s/dockerfiles/metadata/` and the project's own
`CONTRIBUTING.md` is what says so:

- `metadata.json` — what each image *is*: description, status, invocation, manual, versions.
- `dio.obo` — the **vocabulary**. An ontology of classification terms and how they nest.
- `dio.diaf` — the **assignments**. Which terms apply to which image, many-to-many.

The split is the whole design. `dio.obo` alone tells you the shape of the filter tree and
nothing about any tool; `dio.diaf` alone gives you term ids with no names, no definitions and no
hierarchy. A filter that works — click *Sequences*, see `fastqc` — needs both, and needs them
kept apart, because the ontology changes on its own schedule and an assignment file is a flat
join table.

**A category's identity is its DIO id, never its name.** PEGiS has more than one term called
`Alignment` under different parents, and treating the display name as a key silently merges
them: one filter, two meanings, and a tool appearing under a branch it was never assigned to.
Every structure here is keyed by id and carries a `path` so a person can tell the two apart.

**Nothing here reaches the network and nothing here is inferred.** These are parsers over text
the adapter fetched. No category is guessed from a description, no assignment is invented from a
keyword — §8's rule, and the reason a classification is safe to hand to a model as evidence.

**Malformed input yields a diagnostic, never an exception.** A sync that dies because one line
of a 200-line assignment file names a term that was renamed upstream is a sync that reports zero
tools for a typo. Every parser here collects what it could not use and hands it back.
"""

import json
from collections.abc import Iterable, Mapping
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

_FROZEN = ConfigDict(extra="forbid", frozen=True)

TERM_PREFIX = "DIO:"


class ParseWarning(BaseModel):
    """Something the source said that could not be used, and what was skipped because of it.

    Carried rather than raised. §7's rule is that an imperfect join must not hide tools, and a
    parser that throws on the first bad line hides all of them.
    """

    model_config = _FROZEN

    code: str
    """A `MF02xx` diagnostic code. The adapter emits it; this module names it, so the reason a
    warning exists and the reason it is coded stay in one place."""
    detail: str
    subject: str = ""
    """What it was about — a term id, a tool name — so a reader can find it upstream."""


class Term(BaseModel):
    """One `[Term]` block of `dio.obo`."""

    model_config = _FROZEN

    id: str
    name: str
    definition: str = ""
    parents: tuple[str, ...] = ()
    """Direct `is_a` ids. **Zero, one or many** — an OBO term may sit under several parents, and
    a parser assuming one would drop branches of the filter tree without saying so."""


class Ontology(BaseModel):
    """`dio.obo`, indexed by id, with ancestry resolved safely."""

    model_config = _FROZEN

    terms: Mapping[str, Term]

    def get(self, term_id: str) -> Term | None:
        return self.terms.get(term_id)

    def ancestors(self, term_id: str) -> tuple[str, ...]:
        """Every id above `term_id`, nearest first, without repeating one.

        **Cycle-safe by construction, and that is defensive rather than theoretical.** An OBO
        file is hand-maintained; `A is_a B` and `B is_a A` is one careless edit away, and a
        naive walk would recurse until the process died. A `seen` set turns that into a
        truncated ancestry — wrong, but visible and survivable.
        """
        seen: set[str] = {term_id}
        order: list[str] = []
        frontier = [term_id]
        while frontier:
            current = frontier.pop(0)
            term = self.terms.get(current)
            if term is None:
                continue
            for parent in term.parents:
                if parent in seen:
                    continue
                seen.add(parent)
                order.append(parent)
                frontier.append(parent)
        return tuple(order)

    def path(self, term_id: str, _seen: frozenset[str] = frozenset()) -> tuple[str, ...]:
        """A readable breadcrumb, root first: `("Data_type", "Sequences", "Quality")`.

        **One path, and the deepest chain is the one chosen.** A term with several parents has
        several honest paths; a breadcrumb has room for one. The longest is picked because it is
        the most specific placement, and `ancestors()` remains the complete answer for anything
        that needs all of them — filtering uses `ancestors`, never this.

        **`_seen` is the cycle guard, and it was missing.** `ancestors()` was written
        breadth-first with a `seen` set and is safe; this was written recursively and was not,
        so `A is_a B, B is_a A` raised `RecursionError` — in the one function whose module
        docstring promises cycles cannot cause infinite recursion. Found by the test written
        for that promise, not by reading the code beside it. Two traversals, one of them
        guarded, is the shape to distrust.
        """
        term = self.terms.get(term_id)
        if term is None or term_id in _seen:
            return ()
        deeper = _seen | {term_id}
        best: tuple[str, ...] = ()
        for parent in term.parents:
            candidate = self.path(parent, deeper)
            if len(candidate) > len(best):
                best = candidate
        return (*best, term.name)

    def roots(self) -> tuple[str, ...]:
        """Terms with no parent — the top of the filter tree."""
        return tuple(sorted(i for i, t in self.terms.items() if not t.parents))

    def children_of(self, term_id: str | None) -> tuple[str, ...]:
        return tuple(
            sorted(
                i
                for i, t in self.terms.items()
                if (term_id in t.parents) if term_id is not None
            )
        )


class Assignments(BaseModel):
    """`dio.diaf`: which terms apply to which tool. Many-to-many, both ways."""

    model_config = _FROZEN

    by_tool: Mapping[str, tuple[str, ...]]
    """Normalised tool name → its **direct** term ids, sorted and deduplicated."""

    def for_tool(self, tool: str) -> tuple[str, ...]:
        return self.by_tool.get(normalise(tool), ())


def normalise(name: str) -> str:
    """How a tool name is keyed across the three files.

    Case-folded and trimmed, and nothing more. Upstream spells a name one way in Docker Hub and
    the same way in `dio.diaf`; anything cleverer — stripping punctuation, collapsing separators
    — would join two genuinely different tools and produce a classification nobody assigned.
    """
    return name.strip().casefold()


# ── dio.obo ────────────────────────────────────────────────────────────────────────────


def parse_obo(text: str) -> tuple[Ontology, tuple[ParseWarning, ...]]:
    """`[Term]` stanzas into an `Ontology`.

    A deliberately small OBO subset: `id`, `name`, `def`, `is_a`. The format has dozens of other
    tags and PEGiS uses none of them for the filter tree, so parsing more would be code with no
    consumer — and adding an OBO library for four tags is the dependency §"Scope constraints"
    rules out.

    **Stanzas other than `[Term]` are skipped, not refused.** `[Typedef]` is legal OBO and
    carries no filter meaning; treating an unknown stanza as an error would make a routine
    upstream addition break every sync.
    """
    terms: dict[str, Term] = {}
    warnings: list[ParseWarning] = []

    for block in _stanzas(text):
        kind, lines = block
        if kind != "Term":
            continue
        fields = _obo_fields(lines)
        term_id = _one(fields.get("id"))
        if not term_id:
            warnings.append(
                ParseWarning(code="MF0206", detail="an OBO term stanza declares no id")
            )
            continue
        if term_id in terms:
            # Upstream declaring one id twice is ambiguous in a way this cannot resolve: the
            # two stanzas may disagree about parents. The first wins and the collision is
            # reported, because silently taking the last is the `yaml_strict` defect one
            # format over.
            warnings.append(
                ParseWarning(
                    code="MF0206",
                    detail=f"{term_id} is declared more than once; the first stanza is used",
                    subject=term_id,
                )
            )
            continue
        terms[term_id] = Term(
            id=term_id,
            name=_one(fields.get("name")) or term_id,
            definition=_definition(_one(fields.get("def"))),
            parents=tuple(
                sorted({_ref(value) for value in fields.get("is_a", []) if _ref(value)})
            ),
        )

    for term in terms.values():
        for parent in term.parents:
            if parent not in terms:
                warnings.append(
                    ParseWarning(
                        code="MF0206",
                        detail=f"{term.id} is_a {parent}, which no stanza declares",
                        subject=term.id,
                    )
                )
    return Ontology(terms=terms), tuple(warnings)


def _stanzas(text: str) -> Iterable[tuple[str, list[str]]]:
    kind: str | None = None
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            if kind is not None:
                yield kind, lines
            kind, lines = line[1:-1], []
            continue
        if kind is not None and line:
            lines.append(line)
    if kind is not None:
        yield kind, lines


def _obo_fields(lines: list[str]) -> dict[str, list[str]]:
    """Tag/value pairs. A tag may repeat — `is_a` routinely does — so every value is kept."""
    found: dict[str, list[str]] = {}
    for line in lines:
        if line.startswith("!") or ":" not in line:
            continue
        tag, _, value = line.partition(":")
        found.setdefault(tag.strip(), []).append(value.strip())
    return found


def _one(values: list[str] | None) -> str:
    return values[0].strip() if values else ""


def _ref(value: str) -> str:
    """An `is_a` value, stripped of its OBO trailing comment.

    OBO writes `is_a: DIO:0000004 ! Sequences`, and the part after `!` is a human annotation
    that changes when somebody renames a term. Keeping it would make the parent id a different
    string after a cosmetic edit, which reparents the whole subtree.
    """
    return value.split("!")[0].strip()


def _definition(value: str) -> str:
    """An OBO `def:` is a quoted string followed by an xref list: `"text" [ref, ref]`."""
    text = value.strip()
    if text.startswith('"'):
        closing = text.find('"', 1)
        if closing > 0:
            return text[1:closing].strip()
    return text.split("[")[0].strip()


# ── dio.diaf ───────────────────────────────────────────────────────────────────────────


def parse_diaf(
    text: str, known_terms: Iterable[str], known_tools: Iterable[str]
) -> tuple[Assignments, tuple[ParseWarning, ...]]:
    """The two-column assignment file: `<DIO term id>\\t<tool name>`.

    **Both unknown sides are reported and neither is fatal.** An id the ontology does not carry
    is an assignment nobody can render — §7 wants a diagnostic. A tool nobody discovered must
    *not* become a catalogue row: a fabricated entry would be a tool a person could click and
    never run, which is worse than an absence.
    """
    terms = set(known_terms)
    tools = {normalise(name) for name in known_tools}
    collected: dict[str, set[str]] = {}
    warnings: list[ParseWarning] = []
    seen: set[tuple[str, str]] = set()

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        parts = [part.strip() for part in line.split("\t") if part.strip()]
        if len(parts) < 2:
            # Fall back to whitespace, because a hand-edited file loses tabs to an editor and
            # refusing the whole line would drop a real assignment over a formatting slip.
            parts = line.split()
        if len(parts) < 2:
            warnings.append(
                ParseWarning(
                    code="MF0205",
                    detail=f"line {number} is not a term/tool pair: {line!r}",
                )
            )
            continue
        term_id, tool = parts[0], parts[1]
        if not term_id.startswith(TERM_PREFIX):
            warnings.append(
                ParseWarning(
                    code="MF0205",
                    detail=f"line {number} does not begin with a {TERM_PREFIX} id: {line!r}",
                )
            )
            continue
        if (term_id, normalise(tool)) in seen:
            # Deduplicated deterministically and silently: an identical repeated row is a
            # harmless upstream duplicate, not something a reader needs told about.
            continue
        seen.add((term_id, normalise(tool)))
        if term_id not in terms:
            warnings.append(
                ParseWarning(
                    code="MF0205",
                    detail=f"{term_id} is assigned to {tool} and no OBO stanza declares it",
                    subject=term_id,
                )
            )
            continue
        if normalise(tool) not in tools:
            warnings.append(
                ParseWarning(
                    code="MF0207",
                    detail=f"{tool} is classified upstream and no image was discovered for it",
                    subject=tool,
                )
            )
            continue
        collected.setdefault(normalise(tool), set()).add(term_id)

    return (
        Assignments(by_tool={tool: tuple(sorted(ids)) for tool, ids in collected.items()}),
        tuple(warnings),
    )


# ── metadata.json ──────────────────────────────────────────────────────────────────────

FACT_FIELDS: tuple[str, ...] = (
    "description",
    "project_active",
    "status",
    "recommended",
    "latest",
    "bug_found",
    "not_working",
    "no_longer_tested",
    "manual_url",
    "source_url",
    "comments",
    "gui",
    "gui_command",
    "podman",
    "singularity",
    "invocation_general",
    "usual_invocation_specific",
    "usual_invocation_specific_comments",
    "test_invocation",
    "test_data",
    "test_result",
    "input_data_type",
    "auto_tests",
    "icon",
)
"""What is carried through from a metadata entry, and the order a dossier reads them in.

**A list rather than typed fields on `CatalogueItem`.** These are PEGiS's vocabulary, not the
catalogue's: `gui_command` and `singularity` mean nothing to nf-core, and two dozen optional
columns on a shared record would be two dozen fields every other source leaves null. They
travel as `SourceFact` name/value pairs, which is the smallest extension that loses nothing.

**`description` is here as well as becoming `summary`**, and the duplication is deliberate.
Leaving it out kept it out of the digest too, so an upstream rewrite of a tool's description
changed nothing a reviewer would be told about — found by a freshness test, not by reading. A
field that has a typed home still has to be *in* the canonical set that the digest covers.

**Absent and empty are both preserved as absent.** §3's rule — nothing here invents a value, and
an empty string upstream is an unknown rather than a claim of emptiness.
"""


class Entry(BaseModel):
    """One `metadata.json` object, keyed by its `name`."""

    model_config = ConfigDict(extra="allow", frozen=True)
    """**`extra="allow"`, uniquely in this codebase.** Everywhere else a declared shape forbids
    extras so an unexpected key is a loud failure. This is not a declared shape — it is a
    foreign document that PEGiS extends on its own schedule, and refusing a sync because
    upstream added a field would make every future improvement to their metadata an outage
    here. `FACT_FIELDS` is what decides which keys are *read*; this only decides which are
    tolerated.
    """

    name: str

    @model_validator(mode="after")
    def _named(self) -> Self:
        if not self.name.strip():
            raise ValueError("a metadata entry has no name")
        return self

    def facts(self) -> tuple[tuple[str, str], ...]:
        """The declared fields that carry a value, in `FACT_FIELDS` order."""
        found: list[tuple[str, str]] = []
        for field in FACT_FIELDS:
            value = _render(getattr(self, field, None))
            if value:
                found.append((field, value))
        return tuple(found)


def parse_metadata(text: str) -> tuple[Mapping[str, Entry], tuple[ParseWarning, ...]]:
    """The JSON array, indexed by normalised `name`."""
    warnings: list[ParseWarning] = []
    try:
        payload = json.loads(text)
    except ValueError as failure:
        return {}, (
            ParseWarning(code="MF0205", detail=f"metadata.json did not parse: {failure}"),
        )
    if not isinstance(payload, list):
        return {}, (
            ParseWarning(
                code="MF0205",
                detail=f"metadata.json is a {type(payload).__name__}, not an array",
            ),
        )

    entries: dict[str, Entry] = {}
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            warnings.append(
                ParseWarning(code="MF0205", detail=f"metadata.json entry {index} is not an object")
            )
            continue
        try:
            entry = Entry(**row)
        except ValueError as failure:
            warnings.append(
                ParseWarning(code="MF0205", detail=f"metadata.json entry {index}: {failure}")
            )
            continue
        key = normalise(entry.name)
        if key in entries:
            warnings.append(
                ParseWarning(
                    code="MF0205",
                    detail=f"{entry.name} appears more than once; the first entry is used",
                    subject=entry.name,
                )
            )
            continue
        entries[key] = entry
    return entries, tuple(warnings)


def _render(value: object) -> str:
    """A metadata value as one canonical string, or `""` for absent.

    JSON here is loosely typed by hand: a field is a string, a bool, a number, or a list of
    strings depending on the entry. One canonical rendering keeps the digest stable and the
    dossier readable, and `""` for every falsy-but-present value is what implements §3's
    *preserve explicit empty values as unknown*.
    """
    if value is None or value is False:
        return ""
    if value is True:
        return "true"
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        rendered = [_render(item) for item in value]
        return ", ".join(part for part in rendered if part)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)
