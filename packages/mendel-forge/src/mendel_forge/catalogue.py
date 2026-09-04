"""What a source says exists, before anybody decides to adapt it.

**A catalogue is not a registry.** Every record here describes a tool *upstream* — what
nf-core's module tree holds, what the PEGiS namespace publishes — and none of it is declared
data. Nothing in this module is loaded by `mendel build`, nothing is stacked, and a row going
stale costs a person a re-sync rather than costing a pipeline its meaning. Keeping that
separation is what lets the catalogue be cached in Postgres while invariant 11's declared data
stays files in git (issue #43).

**A count here has an exact meaning, and the plan's §1.3 is the definition.** Three of the four
totals a source card shows are different questions and were routinely conflated:

- **discovered** — what the source's own API returned. For nf-core, leaf directories under
  `modules/nf-core/` holding both `main.nf` and `meta.yml`; for PEGiS, public repositories in
  the namespace. Never subworkflows, tests or pipeline-local modules.
- **adaptable** — of those, the ones a dossier can actually be assembled for. An unsupported
  entry stays *visible* and carries its reason; making it disappear is how a catalogue starts
  lying about its own size.
- **adapted** — a registry contract exists for the source ref, current or stale.

`discovered` and `adaptable` are both shown whenever they differ, because a progress bar whose
denominator silently excludes things is a progress bar that reports the wrong fraction and
cannot be questioned.

**`content_digest` is per tool, and that is load-bearing.** Freshness compares the landed
digest against the latest synced one, never a date and never the repository HEAD — otherwise
an unrelated commit to some other module marks every adapted tool in the registry outdated at
once, and the outdated count becomes noise nobody reads.
`test_an_unrelated_tree_change_does_not_age_a_module` is what holds it.

**An unknown version is `null` and a visible hole, never a guessed tag.** `latest` is an alias
a publisher can repoint; calling it a version writes a claim nobody made into a record a
reviewer will later approve.
"""

from datetime import datetime
from enum import StrEnum
from typing import Self

from comeni_core.review.question import Excerpt
from pydantic import BaseModel, ConfigDict, model_validator

_FROZEN = ConfigDict(extra="forbid", frozen=True)

EvidenceId = str
"""`E001`, `E002`, … — an excerpt's address inside one dossier.

Stable within a bundle and meaningless outside it. A model cites these and a reviewer clicks
them, which is the whole reason evidence is numbered rather than quoted inline twice.
"""


class SourceCapabilities(BaseModel):
    """What a source can prove, as opposed to what a tool happens to have.

    This is a property of the *adapter's reach*, not of the tool: nf-core supplies a Nextflow
    process and structured port metadata for every module it lists, and a container registry
    supplies neither for any image in it. The Forge branches on these — an nf-core scaffold
    copies the process and never asks a model to write one; a container-only scaffold must ask
    — so they belong in the catalogue where a person can see them before choosing.
    """

    model_config = _FROZEN

    supplies_nextflow: bool = False
    """A DSL2 process exists upstream and is copied verbatim. When false, a module has to be
    authored, which is the single largest difference in how much a model is trusted with."""
    supplies_structured_ports: bool = False
    """Inputs and outputs are declared in a machine-readable file (`meta.yml`), not only in
    prose. Absent, every port is a hole."""
    supplies_container_digest: bool = False
    """An image can be pinned by digest rather than by tag. A tag is repointable; a digest is
    the only reference that makes a run reproducible."""
    supplies_tests: bool = False
    """Upstream ships something runnable. It is a validation rung when present and its absence
    is not a defect — most container-only sources have none."""


class ContainerRef(BaseModel):
    """One image, pinned as well as the source allows.

    **`digest` is what gets written into a proposal; `tag` is how a human recognises it.** Both
    are kept because a digest with no tag beside it is unreadable in review, and a tag with no
    digest is unreproducible in a run.
    """

    model_config = _FROZEN

    registry: str
    repository: str
    tag: str | None = None
    digest: str | None = None
    platform: str | None = None
    """`os/arch`, as OCI spells it. The MVP selects `linux/amd64` and keeps the rest, because
    dropping the others makes a future arm64 decision unrecoverable without a re-sync."""

    @model_validator(mode="after")
    def _one_of_them_identifies_it(self) -> Self:
        if not self.tag and not self.digest:
            raise ValueError("a container reference needs a tag or a digest; it has neither")
        return self

    def pinned(self) -> str:
        """How it is spelled in a proposal. Digest wins whenever there is one."""
        if self.digest:
            return f"{self.registry}/{self.repository}@{self.digest}"
        return f"{self.registry}/{self.repository}:{self.tag}"


class Freshness(StrEnum):
    """Where one catalogue item stands against the registry.

    **`IN_PROGRESS` is not `ADAPTED`.** Work that is scaffolded, queued, generating, validating,
    in review or awaiting changes has produced no contract, and counting it as adapted makes
    the registry look more complete than it is — which is the one direction a progress figure
    must never err in.
    """

    UNADAPTED = "unadapted"
    IN_PROGRESS = "in_progress"
    CURRENT = "current"
    OUTDATED = "outdated"
    UNSUPPORTED = "unsupported"
    """Outside the denominator entirely, and stated beneath the bar rather than inside it."""


class LandedSource(BaseModel):
    """What the registry remembers about a tool it already carries.

    Read out of a contract's provenance, not out of this cache — the registry is the authority
    on what has landed, and a second copy of that answer is a second thing to keep honest.
    """

    model_config = _FROZEN

    source: str
    ref: str
    content_digest: str
    """The digest of the source content *as it was when it landed*. Comparing this against the
    current item's digest is the whole of the freshness question."""
    contract_id: str | None = None


class CatalogueItem(BaseModel):
    """One tool a source says exists.

    Frozen, because a snapshot is a record of what a source said at a revision. Mutating one
    in place would make the digest describe something other than the fields beside it.
    """

    model_config = _FROZEN

    id: str
    """`sha256(source + "\\n" + ref)`, hex. Opaque and stable across syncs, so an adaptation
    started today still points at the same row after tomorrow's sync renamed nothing.

    **Derived rather than supplied.** `BaseSourceAdapter` computes it; an adapter that invented
    its own would be free to make it collide or make it move."""
    source: str
    ref: str
    """The source's own id — `samtools/sort`, `fastqc`. Not a path and not a URL."""

    display_name: str
    summary: str = ""
    homepage_url: str | None = None
    documentation_url: str | None = None
    repository_url: str | None = None
    licence: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    maintainers: tuple[str, ...] = ()

    latest_version: str | None = None
    """`None` when the source does not *prove* one. A container tagged only `latest` has no
    proved version, and writing `"latest"` here would turn an alias into a claim."""

    container_refs: tuple[ContainerRef, ...] = ()
    source_revision: str = ""
    """The commit or registry digest the fetch was made at, so a bundle is reproducible."""
    content_digest: str
    """This tool's content, and nothing else's. See the module docstring."""
    last_updated_at: datetime | None = None
    """A source fact, nullable. Never used for freshness — see `content_digest`."""

    input_hints: tuple[str, ...] = ()
    output_hints: tuple[str, ...] = ()
    """What the source suggests goes in and comes out, in its own words. **Hints, in the name,
    because they are not ports**: a filename pattern is evidence and a channel name is not a
    semantic type. They exist so a person can judge a tool before importing it."""

    capabilities: SourceCapabilities = SourceCapabilities()
    adaptable: bool = True
    unsupported_reason: str | None = None
    evidence: tuple[Excerpt, ...] = ()

    @model_validator(mode="after")
    def _unsupported_says_why(self) -> Self:
        """An entry that cannot be adapted must say why, and one that can must not pretend.

        The first half is the plan's rule — *show unsupported entries and their reason* — and
        the second half is what stops a reason from lingering after the obstacle is gone, which
        would leave a usable tool wearing a stale excuse.
        """
        if not self.adaptable and not (self.unsupported_reason or "").strip():
            raise ValueError(f"{self.ref}: unsupported with no reason — say what is missing")
        if self.adaptable and self.unsupported_reason:
            raise ValueError(f"{self.ref}: adaptable and carrying an unsupported reason")
        return self

    def freshness(self, landed: LandedSource | None, in_progress: bool = False) -> Freshness:
        """Where this stands. **Digest equality, never a date.**"""
        if not self.adaptable:
            return Freshness.UNSUPPORTED
        if landed is None:
            return Freshness.IN_PROGRESS if in_progress else Freshness.UNADAPTED
        return (
            Freshness.CURRENT
            if landed.content_digest == self.content_digest
            else Freshness.OUTDATED
        )


class SourceCounts(BaseModel):
    """One source card's numbers, with the denominator stated.

    **`adaptable` is the denominator and `discovered` is printed beside it.** A bar drawn over
    a hidden denominator cannot be questioned; §1.3 asks for both whenever they differ.
    """

    model_config = _FROZEN

    discovered: int
    adaptable: int
    unsupported: int
    adapted: int
    current: int
    outdated: int
    in_progress: int

    @model_validator(mode="after")
    def _the_parts_fit_the_whole(self) -> Self:
        """Arithmetic a reader would do anyway, done here so a wrong card fails loudly.

        The four bar segments — current, outdated, in progress, unadapted — are mutually
        exclusive and sum to `adaptable`; unsupported sits outside it. A card that violated
        this would draw a bar past its own end, which is the sort of thing that reaches a
        screenshot before it reaches a test.
        """
        if self.adaptable + self.unsupported != self.discovered:
            raise ValueError(
                f"adaptable {self.adaptable} + unsupported {self.unsupported} "
                f"!= discovered {self.discovered}"
            )
        if self.adapted != self.current + self.outdated:
            raise ValueError(
                f"adapted {self.adapted} != current {self.current} + outdated {self.outdated}"
            )
        if self.adapted + self.in_progress > self.adaptable:
            raise ValueError(
                f"adapted {self.adapted} + in progress {self.in_progress} "
                f"exceeds adaptable {self.adaptable}"
            )
        return self

    @property
    def unadapted(self) -> int:
        """The fourth bar segment, derived rather than stored — a stored one is a fifth number
        that can disagree with the other four."""
        return self.adaptable - self.adapted - self.in_progress


class SourceSnapshot(BaseModel):
    """One successful sync of one source.

    **A snapshot is only ever a success.** A failed sync does not produce a degraded snapshot;
    it leaves the previous one in place and records its own error elsewhere, which is what lets
    a page say *stale, and here is why* instead of showing zero tools. §4.3 asks for exactly
    that, and the empty state says "no successful source sync" rather than "0".
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    source_revision: str
    """The commit or catalogue revision every item in this snapshot was read at."""
    etag: str | None = None
    """For the next conditional request. `None` when the source offers no validator."""
    synced_at: datetime
    items: tuple[CatalogueItem, ...]

    @model_validator(mode="after")
    def _every_item_belongs_to_this_source(self) -> Self:
        wrong = sorted({item.source for item in self.items} - {self.source})
        if wrong:
            raise ValueError(f"{self.source} snapshot carries items from {wrong}")
        seen = [item.ref for item in self.items]
        if len(seen) != len(set(seen)):
            duplicated = sorted({ref for ref in seen if seen.count(ref) > 1})
            raise ValueError(f"{self.source} snapshot lists {duplicated} more than once")
        return self

    def counts(
        self,
        landed: dict[str, LandedSource] | None = None,
        in_progress: frozenset[str] = frozenset(),
    ) -> SourceCounts:
        """The card's numbers, derived from the items rather than stored beside them.

        `landed` and `in_progress` are keyed by `ref`. Both are the registry's and the
        workflow's business respectively, and are passed in rather than cached here — a
        catalogue that remembered what had landed would be a second answer to a question the
        registry already answers.
        """
        landed = landed or {}
        tally = {state: 0 for state in Freshness}
        for item in self.items:
            tally[item.freshness(landed.get(item.ref), item.ref in in_progress)] += 1
        return SourceCounts(
            discovered=len(self.items),
            adaptable=sum(1 for item in self.items if item.adaptable),
            unsupported=tally[Freshness.UNSUPPORTED],
            adapted=tally[Freshness.CURRENT] + tally[Freshness.OUTDATED],
            current=tally[Freshness.CURRENT],
            outdated=tally[Freshness.OUTDATED],
            in_progress=tally[Freshness.IN_PROGRESS],
        )


class SourceBundle(BaseModel):
    """Everything fetched for one tool, at one revision, frozen.

    **This is the immutable half of an adaptation.** The scaffold, the prompts and the
    candidate all derive from it, and none of them may write back into it — an AI proposal that
    could edit a source fact would make the whole provenance chain unfalsifiable. Task 5's
    workspace layout keeps it in its own directory for the same reason.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    item: CatalogueItem
    source_digest: str
    """Of the fetched content as a whole. Distinct from `item.content_digest`, which is what the
    *catalogue* said before anything was fetched; the two agreeing is a check, not a given."""
    files: tuple["BundleFile", ...] = ()
    evidence: tuple["NumberedExcerpt", ...] = ()
    facts: tuple["BundleFact", ...] = ()

    def excerpt(self, evidence_id: EvidenceId) -> "NumberedExcerpt | None":
        return next((e for e in self.evidence if e.id == evidence_id), None)

    def file(self, path: str) -> "BundleFile | None":
        return next((f for f in self.files if f.path == path), None)


class BundleFact(BaseModel):
    """Something the adapter read, and the excerpt it read it from.

    **`evidence_id` may be `None`, and that means derived rather than read.** `nfcore.py`
    learned this the expensive way and the rule is repeated here because it is the one that
    keeps citations worth following: citing a line for a value nothing was read from is worse
    than citing nothing at all, because a reviewer who follows it finds text that does not
    support the claim and has no way to tell that from a claim that is simply wrong.
    """

    model_config = _FROZEN

    name: str
    value: object
    evidence_id: EvidenceId | None = None


class BundleFile(BaseModel):
    """One fetched file, and whether the Forge may regenerate it.

    `verbatim` marks upstream content that is copied and never authored — an nf-core `main.nf`
    is the case the plan names twice. A validation rung compares the candidate's copy against
    this, so *"AI rewrote a source file"* is a check rather than a hope.
    """

    model_config = _FROZEN

    path: str
    """Relative to the bundle root, and validated as such. Never absolute, never `..`."""
    text: str
    verbatim: bool = True
    digest: str = ""

    @model_validator(mode="after")
    def _the_path_stays_inside(self) -> Self:
        from pathlib import PurePosixPath

        candidate = PurePosixPath(self.path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"{self.path!r} escapes the bundle root")
        return self


class NumberedExcerpt(BaseModel):
    """An `Excerpt` with an address a model can cite and a reviewer can click.

    **The id is assigned by the base adapter, in a deterministic order.** An adapter numbering
    its own would be free to renumber between two syncs, and a stored review citing `E014`
    would then point at different text than the reviewer read.
    """

    model_config = _FROZEN

    id: EvidenceId
    excerpt: Excerpt
    kind: str = "prose"
    """What sort of evidence this is — `prose`, `metadata`, `source`, `container`. Coarse on
    purpose: it orders the dossier and tells a reviewer whether a claim rests on documentation
    or on something machine-readable."""


SourceBundle.model_rebuild()
