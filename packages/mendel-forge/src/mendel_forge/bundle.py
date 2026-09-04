"""One adaptation's working directory, computed rather than written.

**Nothing here touches a filesystem, and that is the design rather than a restriction.** A
`ScaffoldBundle` carries the whole directory as `(relative path, text)` pairs; `workspace.py`
writes them. Three things follow, and each of them was going to be a test with a `tmp_path` in
it otherwise:

- **The write-boundary guard stays as strong as it was.** `test_forge_write_boundary.py` allows
  exactly two files to write — `land.py` and `workspace.py` — and adding a third to that list is
  a real weakening of a claim about the whole package. There is nothing here to add.
- **Byte-identity is testable with no I/O at all.** *Two scaffolds from the same source and
  registry digests are byte-identical* is `a.files() == b.files()`, not a directory comparison
  that has to know which differences to forgive.
- **An absolute host path cannot get in by accident.** Every path is composed here, from parts
  that are validated, and `contains_a_host_path` scans the emitted text.

**The layout is six named areas and one manifest.** Splitting them is what keeps the immutable
half immutable: `source/` is what upstream said and nothing may write back into it, because a
proposal that could edit a source fact would make the whole provenance chain unfalsifiable.
`candidate/`, `prompt/`, `response/` and `validation/` are filled in later, by Tasks 6 and 7 —
they are declared here so that a path is validated in one place rather than composed at four
call sites.
"""

import json
import re
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Self

from comeni_core.diagnostics import coded
from comeni_vendor.ops import digest_of_contents
from mendel_compiler.modulespec import ModuleSpec
from mendel_resolver.layers import Layers
from pydantic import BaseModel, ConfigDict, model_validator

from mendel_forge import assemble, modulegen
from mendel_forge.catalogue import CatalogueItem, SourceBundle
from mendel_forge.hole_manifest import HoleKind, ScaffoldHole, pointer_for, port_hole_id
from mendel_forge.observe import Excerpt, Fact, Observation
from mendel_forge.scaffold import Hole, Scaffold

_FROZEN = ConfigDict(extra="forbid", frozen=True)

_ADAPTATION_ID = re.compile(r"^[a-f0-9]{32}$")
"""`secrets.token_hex(16)`, which is what `forge_state.begin` mints.

**Anchored, and hex only.** The id becomes a directory name under the workspace root, so
anything that could contain a separator or a `..` is a path traversal with extra steps. The
same argument `MF0008` makes about a draft name, and the same resolution: prevention by
construction rather than validating the joined path afterwards.
"""

_HOST_PATH = re.compile(r"(?:^|[\s\"'=(:])(/(?:home|Users|root|tmp|var|opt|mnt|media)/\S+)")
"""What an absolute host path looks like in emitted text.

**A pattern over named roots rather than any leading `/`**, because Nextflow and container
references are full of legitimate absolute-looking strings — `/usr/bin/env`, a `publishDir` of
`/results`, a POSIX path inside a quoted tool invocation. Matching every `/` would fire on all
of them and be switched off within a week.

The roots listed are where a *developer machine* puts things, which is the actual failure:
`digest_of_directory` once made a layer digest depend on the checkout path while `make verify`
stayed green, and the old nf-core adapter wrote absolute locators into every draft until
somebody noticed the golden files were machine-specific.
"""


class Area(StrEnum):
    """The named subdirectories, and the only legal first segment of a bundle path.

    Declared as an enum rather than as string constants so that a typo is a `ValueError` at the
    call site instead of a seventh directory nobody meant to create — which is how a bundle
    ends up with both `responses/` and `response/` and half the files in each.
    """

    SOURCE = "source"
    """What upstream said, verbatim. **Immutable** — nothing downstream writes here."""
    SCAFFOLD = "scaffold"
    """What the deterministic half derived: a partial contract, a hole manifest, and a module
    skeleton when the source ships none."""
    CANDIDATE = "candidate"
    """What a model proposed. Task 6."""
    PROMPT = "prompt"
    """Rendered prompts, with their digests. Task 6."""
    RESPONSE = "response"
    """Raw responses, before validation. Task 6 — kept separate from `candidate/` because a
    response that failed to validate has no candidate and still has to be readable."""
    VALIDATION = "validation"
    """Verdicts. Task 7."""


MANIFEST = "bundle.json"
"""The bundle's own record, at the root rather than in an area. It describes the areas, so
putting it inside one of them would make it a member of what it describes."""


def joined(adaptation_id: str, area: Area, *parts: str) -> str:
    """A workspace-relative path inside one area, validated.

    **Every joined path goes through here**, which is the plan's requirement written as a
    function rather than as a rule people follow. It refuses an absolute part, a `..`, an empty
    part and a backslash — the last because a Windows-style separator is not a separator to
    `PurePosixPath` and would sail through a check that only looked for `/`.
    """
    if not _ADAPTATION_ID.match(adaptation_id):
        raise ValueError(
            coded("MF0008", f"{adaptation_id!r} is not an adaptation id")
            + "\n  it becomes a directory name, so it is 32 hex characters and nothing else"
        )
    for part in parts:
        if not part or part != part.strip():
            raise ValueError(coded("MF0008", f"{part!r} is not a usable path segment"))
        if "\\" in part:
            raise ValueError(
                coded("MF0008", f"{part!r} contains a backslash")
                + "\n  it is not a separator here, which is exactly why it is refused"
            )
        candidate = PurePosixPath(part)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(coded("MF0008", f"{part!r} escapes the bundle"))
    return "/".join(["forge", adaptation_id, area.value, *parts])


def contains_a_host_path(text: str) -> tuple[str, ...]:
    """Absolute host paths found in `text`, in order.

    Returned rather than raised, so a caller can name every one at once. A scaffold with three
    leaked paths reported one at a time is three runs to find out.
    """
    return tuple(found.group(1) for found in _HOST_PATH.finditer(text))


class ScaffoldBundle(BaseModel):
    """Everything one adaptation starts from, as values.

    `source_digest` and `registry_digest` together are the bundle's identity: the same pair
    produces the same files, byte for byte. Nothing here reads a clock, and nothing here is
    ordered by anything but its own name — an insertion-ordered mapping serialises in parse
    order, and parse order moves under a refactor nobody asked for.
    """

    model_config = _FROZEN

    adaptation_id: str
    item: CatalogueItem
    source_digest: str
    registry_digest: str
    holes: tuple[ScaffoldHole, ...] = ()
    deterministic: tuple[tuple[str, str], ...] = ()
    """`(relative path, text)` for everything the forge derived. Sorted by path."""
    source_files: tuple[tuple[str, str], ...] = ()
    """`(relative path, text)` for everything upstream shipped, copied unchanged."""

    @model_validator(mode="after")
    def _nothing_leaks_a_host_path(self) -> Self:
        """The plan asks for this as an assertion in a test. It is a validator instead, so that
        a bundle carrying one cannot be constructed rather than merely cannot be committed.

        **Source files are exempt and that is not an oversight.** They are upstream's bytes and
        we do not edit them; an nf-core module legitimately writes `/usr/bin/env`, and a PEGiS
        Dockerfile legitimately names paths inside its own image. What must not carry a host
        path is what *we* composed, because that is what would differ between two machines.
        """
        leaked = {
            path: found
            for path, text in self.deterministic
            if (found := contains_a_host_path(text))
        }
        if leaked:
            raise ValueError(
                f"a generated scaffold file names an absolute host path: {leaked}. "
                "A path from the machine that built it makes the bundle unreproducible and "
                "puts that machine's layout into every prompt built from it."
            )
        return self

    def files(self) -> tuple[tuple[str, str], ...]:
        """Every file in the bundle, sorted by path. **This is the byte-identity claim.**"""
        return tuple(sorted([*self.deterministic, *self.source_files]))

    def path(self, area: Area, *parts: str) -> str:
        return joined(self.adaptation_id, area, *parts)

    def manifest_path(self) -> str:
        return f"forge/{self.adaptation_id}/{MANIFEST}"

    def module_digest(self) -> str:
        """The digest of the module directory as it would be vendored.

        **`comeni_vendor.ops.digest_of_contents`, not a local reimplementation.** A scaffolded
        module and a vendored one have to be comparable, and two functions that agreed today
        would be two functions that stopped agreeing on the first change to either.
        """
        prefix = self.path(Area.SOURCE) + "/"
        return digest_of_contents(
            {
                path.removeprefix(prefix): text.encode()
                for path, text in self.source_files
                if path.startswith(prefix)
            }
        )


def _dumps(payload: object) -> str:
    """JSON that does not move between two runs.

    `sort_keys` because a mapping's insertion order is parse order; a trailing newline because
    a file without one is a diff with a `\\ No newline at end of file` in it forever.
    """
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def scaffold(
    *,
    adaptation_id: str,
    source: SourceBundle,
    registry_digest: str,
    holes: tuple[ScaffoldHole, ...],
    contract: dict,
    module: str | None = None,
) -> ScaffoldBundle:
    """Compose one adaptation's starting directory.

    `contract` is the partial contract the deterministic half derived — a plain mapping rather
    than a `ModuleContract`, because a half-contract is deliberately unrepresentable
    (`scaffold.py` says why) and constructing one here would be that guarantee spent for the
    convenience of a type.

    `module` is the generated `main.nf` for a source that ships none. When the source ships one
    it is already in `source.files` and generating a second would be the forge authoring over
    upstream — the thing every `verbatim=True` in this codebase exists to prevent.
    """
    into = lambda area, *parts: joined(adaptation_id, area, *parts)  # noqa: E731

    deterministic = [
        (into(Area.SCAFFOLD, "contract.yml.json"), _dumps(contract)),
        (
            into(Area.SCAFFOLD, "holes.json"),
            _dumps([hole.model_dump(mode="json") for hole in holes]),
        ),
        (into(Area.SOURCE, "item.json"), _dumps(source.item.model_dump(mode="json"))),
        (
            into(Area.SOURCE, "evidence.json"),
            _dumps([entry.model_dump(mode="json") for entry in source.evidence]),
        ),
        (
            into(Area.SOURCE, "facts.json"),
            _dumps([fact.model_dump(mode="json") for fact in source.facts]),
        ),
    ]
    if module is not None:
        deterministic.append((into(Area.SCAFFOLD, "module", "main.nf"), module))

    return ScaffoldBundle(
        adaptation_id=adaptation_id,
        item=source.item,
        source_digest=source.source_digest,
        registry_digest=registry_digest,
        holes=holes,
        deterministic=tuple(sorted(deterministic)),
        source_files=tuple(
            sorted((into(Area.SOURCE, *file.path.split("/")), file.text) for file in source.files)
        ),
    )


def module_for(item: CatalogueItem, *, process: str) -> str | None:
    """The generated `main.nf`, or `None` when the source shipped its own.

    A source that supplies Nextflow is the whole of the test, and `SourceCapabilities` is where
    that is recorded — reading it here rather than guessing from the file list means a source
    that starts shipping modules needs no change in this file.
    """
    if item.capabilities.supplies_nextflow:
        return None
    container = _container_ref(item)
    if container is None:
        return None
    return modulegen.module_text(process=process, container=container)


def _container_ref(item: CatalogueItem) -> str | None:
    """The image this tool runs in, spelled the way Nextflow wants it.

    **A digest wins over a tag**, and that is not a preference. A tag is mutable — the image
    `pegi3s/clustalw:2.1` names today can be replaced tomorrow — so a pipeline pinned by tag is
    reproducible only by convention. PEGiS publishes digests, which is the single axis on which
    it beats nf-core, and reaching for the tag when a digest is present would discard it.
    """
    return next(
        (
            f"{ref.registry}/{ref.repository}@{ref.digest}"
            if ref.digest
            else f"{ref.registry}/{ref.repository}:{ref.tag}"
            for ref in item.container_refs
            if ref.digest or ref.tag
        ),
        None,
    )


# ── deriving one from a fetched source ─────────────────────────────────────────────────
#
# **`assemble.scaffold_for` is reused rather than reimplemented**, and that is the largest
# decision in this file. Its rules are measured, not guessed: which fields a source can prove
# outright, that a port's *name* is a separate choice from its type and must be asked after it,
# that a hole carries its own port's documentation rather than every port's, and that
# `priority_because` needs a question rather than a placeholder. Each cost a measurement, and a
# second derivation here would start by getting them wrong again.
#
# What is new is the *addressing*. `assemble` names a hole `consumes[0].type_id`; this
# translates that into a stable semantic id plus a pointer, which is the plan's requirement and
# the one thing the old shape cannot express.

_KINDS: dict[str, tuple[HoleKind, str]] = {
    "type_id": (HoleKind.TYPE, ""),
    "name": (HoleKind.TYPE, "ports.name.v1"),
    "roles": (HoleKind.ROLE, ""),
    "priority_because": (HoleKind.CITATION, ""),
    "nf_process": (HoleKind.NEXTFLOW, ""),
    "nf_include": (HoleKind.NEXTFLOW, ""),
    "container": (HoleKind.VERSION, ""),
}
"""Field -> its kind, and an instruction fragment when the kind's default is the wrong one.

**A port's name is a `TYPE` hole with its own fragment**, which is the case that shows why the
override exists. The kind is coarse by design — it groups holes on a page and picks a default
fragment — and a name and a type are the same *sort* of question about the same port. They are
not the same question, and `ports.name.v1` is where that difference is written down once
instead of inside each draft.
"""

_PORT = re.compile(r"^(consumes|produces)\[(\d+)\]\.(\w+)$")


def _kind_of(subject: str) -> tuple[HoleKind, str]:
    found = _PORT.match(subject)
    return _KINDS.get(found.group(3) if found else subject, (HoleKind.PARAM, ""))


def observation_of(source: SourceBundle, *, ident: str) -> Observation:
    """The fetched bundle, in the shape `assemble` reads.

    **`ModuleSpec.of` is what makes this possible**, and it is the same parser conformance uses.
    The adapters deliberately do not parse Nextflow — a catalogue sync reads sixteen hundred
    tools and has no business running a DSL parser over any of them — so a module's shape is
    derived here, once, for the one tool somebody is adapting.

    A source that ships no `main.nf` yields the facts it does have and no more. That is not a
    degraded observation: `assemble` opens a hole for every fact it cannot find, which is
    exactly the right outcome for a container with a README and no process.
    """
    facts: dict[str, Fact] = {}

    def note(name: str, value: object, locator: str) -> None:
        facts[name] = Fact(
            value=value, evidence=Excerpt(locator=locator, text=f"read from {locator}")
        )

    for fact in source.facts:
        found = source.excerpt(fact.evidence_id) if fact.evidence_id else None
        facts[fact.name] = Fact(
            value=fact.value,
            evidence=found.excerpt
            if found
            else Excerpt(locator=source.item.ref, text="derived, not read"),
        )

    main_nf = source.file("main.nf")
    if main_nf is not None:
        meta = source.file("meta.yml")
        spec = ModuleSpec.of(main_nf.text, meta_yml=meta.text if meta else None, where="main.nf")
        # **`process`, not `nf_process`** — `assemble.DERIVED_FIELDS` maps the *fact* `process`
        # onto the contract *field* `nf_process`, and naming the fact after the field leaves the
        # mapping looking for something nothing wrote. The symptom is quiet: `assemble` opens a
        # hole for every fact it cannot find, so a module that plainly declares
        # `process FASTQC {` produces a scaffold asking somebody what the process is called.
        # Nothing failed; there was simply one more hole than there should have been.
        note("process", spec.process, "main.nf")
        note("emits", list(spec.emits), "main.nf")
        note("input_arity", len(spec.inputs), "main.nf")
        note("input_names", [slot.names for slot in spec.inputs], "main.nf")
        note("meta_reads", sorted({read.key for read in spec.meta_reads}), "main.nf")
        note("reads_ext_args", spec.reads_ext_args, "main.nf")
        note("reads_ext_prefix", spec.reads_ext_prefix, "main.nf")
        if spec.container:
            note("container", spec.container, "main.nf")

    if "container" not in facts and (pinned := _container_ref(source.item)):
        # **A registry digest is proof, and PEGiS is the source that has one.** It is the single
        # axis on which the weaker source beats nf-core — nf-core pins a *tag*, which is
        # mutable — so leaving `container` open here would open a hole over the one fact PEGiS
        # actually proves, and ask a human to retype a digest that was fetched from an API.
        note("container", pinned, f"{source.item.source}:{source.item.ref}")

    return Observation(
        source=source.item.source,
        ref_id=ident,
        facts=facts,
        prose=[entry.excerpt for entry in source.evidence],
    )


def _channel_for(hole: Hole, observation: Observation, group: str, index: int) -> str:
    """What upstream calls this port, which is what a stable id is built from.

    Falls back to the index, and that fallback is the honest answer rather than a shortcut: a
    source naming none of its ports offers no stable handle at all, and inventing one from
    ordering would produce an id that *looks* stable and is not. A reviewer reading
    `consumes.1.type_id` can see it is positional; one reading `consumes.input.type_id` cannot.
    """
    if hole.channels:
        return hole.channels[0]
    if group == "produces":
        emits = observation.fact("emits") or []
        return str(emits[index]) if index < len(emits) else str(index)
    names = observation.fact("input_names") or []
    if index < len(names):
        named = [name for name in names[index] if not name.startswith("meta")]
        if named:
            return named[0]
    return str(index)


def holes_of(derived: Scaffold, observation: Observation) -> tuple[ScaffoldHole, ...]:
    """`assemble`'s holes, re-addressed by something that will not move.

    Sorted by id rather than kept in `assemble`'s order: that order is by *subject*, which is a
    different order once the subjects are renamed, and keeping it would make the manifest
    silently positional again.
    """
    found: list[ScaffoldHole] = []
    for hole in derived.holes:
        port = _PORT.match(hole.subject)
        kind, hint = _kind_of(hole.subject)
        if port:
            group, index, field = port.group(1), int(port.group(2)), port.group(3)
            identifier = port_hole_id(group, _channel_for(hole, observation, group, index), field)
            pointer = pointer_for(group, index, field)
        else:
            identifier = hole.subject
            # `"/".join(split(...))` rather than `str.replace`: the write-boundary guard is an
            # AST scan over attribute names and cannot tell `str.replace` from `Path.replace`,
            # so using the name here would mean widening a guard that protects the whole
            # package for the sake of one string. Second time this has come up; same answer.
            pointer = "/" + "/".join(hole.subject.split("."))
        legal = tuple(candidate.value for candidate in hole.candidates)
        found.append(
            ScaffoldHole(
                id=identifier,
                pointer=pointer,
                kind=kind,
                question=hole.what,
                why_open=hole.why_open,
                legal_values=legal,
                # **`Question.closed` is the source of truth here, not the emptiness of the
                # list.** *We listed everything* and *we listed what we found* are the two
                # answers a reviewer most needs told apart, and inferring one from a length
                # collapses them the first time a vocabulary runs dry.
                exhaustive=hole.closed and bool(legal),
                suggested=hole.suggested,
                prompt_hint_id=hint,
            )
        )
    return tuple(sorted(found, key=lambda hole: hole.id))


def derive(
    source: SourceBundle,
    stack: Layers,
    *,
    adaptation_id: str,
    registry_digest: str,
    version: str = "",
) -> ScaffoldBundle:
    """The whole deterministic half: fetched source in, scaffold bundle out.

    **The same inputs give the same bytes.** Nothing here reads a clock, an environment variable
    or a path, and the one thing that could vary — which registry the candidates were ranked
    against — is named in `registry_digest` rather than left implicit. Two calls that disagree
    are two different registries, which is a fact the bundle records rather than a
    nondeterminism it hides.

    **The contract's two lists use two spellings, deliberately.** `open` holds stable hole ids —
    `produces.html.type_id` — and `settled` is keyed by `assemble`'s field names —
    `produces[0].name`. They are not converted to one vocabulary because they are not the same
    thing: a hole id has to survive a channel being added upstream, and a settled key has to be
    the key `assemble.contract_from` reads when the draft is finally assembled. Normalising
    `settled` would make the bundle prettier and make Task 6 convert it back.
    """
    ident = f"{source.item.source}/{source.item.ref}"
    observation = observation_of(source, ident=ident)
    derived = assemble.scaffold_for(
        observation, stack, ident=ident, version=version or source.item.latest_version or "0"
    )
    settled = derived.filled.get("process")
    return scaffold(
        adaptation_id=adaptation_id,
        source=source,
        registry_digest=registry_digest,
        holes=(holes := holes_of(derived, observation)),
        contract={
            "id": derived.filled["id"].value,
            "kind": derived.kind.value,
            "target": derived.target,
            "settled": {name: value.value for name, value in sorted(derived.filled.items())},
            "open": [hole.id for hole in holes],
        },
        module=module_for(
            source.item,
            process=str(settled.value) if settled else _process_name(source.item.ref),
        ),
    )


def _process_name(ref: str) -> str:
    """`samtools/sort` -> `SAMTOOLS_SORT`, the convention every nf-core module follows.

    **A default, not a derivation**, and it is only reached when no source proved a process name
    — a PEGiS image, where nothing upstream has ever written one. The scaffold still opens an
    `nf_process` hole, so this is what the placeholder module is *called* while somebody
    decides, not an answer standing in for a decision.
    """
    return re.sub(r"[^A-Za-z0-9]+", "_", ref).upper()
