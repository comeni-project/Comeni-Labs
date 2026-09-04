"""The half of a source adapter that is the same for every source.

**A common base with capability hooks, not inheritance from nf-core's layout.** That
distinction is §1.2 of the plan and it is the failure this file exists to avoid: the first
`Source` protocol had one implementation, so everything nf-core happened to do looked like
what a source *is*. A container registry has no `meta.yml`, no process, no versions file and
no tests, and an abstraction shaped around the one source that existed would have made it a
special case rather than an equal.

What the base owns, and what it therefore cannot be got wrong twice:

- **conditional requests** — an `ETag` from the last snapshot, and a `304` that means *reuse
  what you have* rather than *the catalogue is empty*;
- **retry with bounded backoff**, and the distinction between a status worth retrying and one
  that will never change;
- **pagination**, including refusing a truncated result rather than reporting a short total;
- **stable digests and evidence ids**, assigned in a deterministic order;
- **normalisation** into `CatalogueItem`, so two sources cannot disagree about what a field
  means.

A subclass implements two methods and answers only source-specific questions: where the list
comes from, and how one tool's files are fetched.

**Refusing beats under-reporting, everywhere in this file.** A partial catalogue is worse than
no catalogue: it produces a plausible total that is wrong, a progress bar with a wrong
denominator, and an "up to date" claim about tools the sync never saw. `MF0200` is that
refusal and it is deliberately unconditional — there is no flag to accept a partial list.

**No `Source.discover(root)` here.** That verb answered *what has already been vendored into
this layer*, which is a question about the registry rather than about the source, and issue #77
records that it was never the size of the known world. The old protocol stays in
`sources/__init__.py` for the deprecated `forge draft` path until Task 13 retires it.
"""

import asyncio
import hashlib
import random
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import httpx
from comeni_core.diagnostics import coded
from comeni_core.review.question import Excerpt
from pydantic import BaseModel, ConfigDict

from mendel_forge.catalogue import (
    BundleFact,
    BundleFile,
    CatalogueItem,
    ContainerRef,
    LandedSource,
    NumberedExcerpt,
    SourceBundle,
    SourceCapabilities,
    SourceSnapshot,
)
from mendel_forge.observe import Observation

_FROZEN = ConfigDict(extra="forbid", frozen=True)

RETRYABLE = frozenset({408, 425, 429, 500, 502, 503, 504})
"""Statuses worth trying again.

**A blocklist would have been wrong here and an allowlist is right.** `404` and `422` will
never change and retrying them turns one clear failure into three slow ones; `403` is
deliberately absent even though a rate-limited GitHub returns it, because a `403` with no
`Retry-After` is far more often a token problem — `_retry_after` is what handles the rate-limit
case by reading the header rather than by guessing from the status.
"""

MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 0.5
BACKOFF_CAP_SECONDS = 8.0


class UpstreamError(RuntimeError):
    """A source could not be read. `MF0200`–`MF0204`.

    A `RuntimeError` rather than a `ValueError`: every other refusal in the forge is *this
    input is wrong*, and this one is *the world did not answer*. A caller retries this one and
    does not retry the others, so they must be distinguishable without reading the message.
    """


class RawEvidence(BaseModel):
    """An excerpt before it has an id. See `NumberedExcerpt` for why the base assigns them."""

    model_config = _FROZEN

    locator: str
    text: str
    kind: str = "prose"


class RawItem(BaseModel):
    """One catalogue entry as its own source describes it, before normalisation.

    **`content_digest` is the adapter's**, not the base's, and that is the one substantive
    field a subclass must compute rather than describe. Only the adapter knows what "this
    tool's content" is — a directory tree digest for nf-core, an image manifest digest plus its
    documentation for a container source — and §1.3's rule that an unrelated upstream commit
    must not age every module is a rule about exactly that choice.
    """

    model_config = _FROZEN

    ref: str
    display_name: str = ""
    summary: str = ""
    homepage_url: str | None = None
    documentation_url: str | None = None
    repository_url: str | None = None
    licence: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    maintainers: tuple[str, ...] = ()
    latest_version: str | None = None
    container_refs: tuple[ContainerRef, ...] = ()
    last_updated_at: datetime | None = None
    input_hints: tuple[str, ...] = ()
    output_hints: tuple[str, ...] = ()
    capabilities: SourceCapabilities = SourceCapabilities()
    adaptable: bool = True
    unsupported_reason: str | None = None
    evidence: tuple[RawEvidence, ...] = ()
    content_digest: str


class RawCatalogue(BaseModel):
    """What `_fetch_catalogue` returns.

    `complete` is the field that matters. GitHub's tree endpoint truncates at a documented
    limit and says so; Docker Hub pages. An adapter that cannot prove it saw everything sets
    this false, and the base refuses rather than publishing a short total.
    """

    model_config = _FROZEN

    source_revision: str
    etag: str | None = None
    items: tuple[RawItem, ...] = ()
    complete: bool = True
    unchanged: bool = False
    """The source answered `304`. `items` is then empty and the previous snapshot is reused —
    which is why this is a separate flag rather than an empty list: *nothing changed* and
    *there is nothing* are opposite facts with identical shapes."""


class RawBundle(BaseModel):
    """What `_fetch_bundle` returns: one tool's files and evidence, at a fixed revision."""

    model_config = _FROZEN

    source_revision: str
    files: tuple[BundleFile, ...] = ()
    evidence: tuple[RawEvidence, ...] = ()
    facts: tuple[BundleFact, ...] = ()
    """Machine-read values the adapter is willing to stand behind — a process name, an entry
    point, an arity. `observe()` turns these into an `Observation`; they are not a contract and
    nothing here decides what any of them *means*.

    `evidence_id` on each is an index into `evidence` **as this adapter ordered it**, resolved
    by `number()` at the same moment the ids are assigned, so the two cannot drift apart."""


def digest_of(*parts: str | bytes) -> str:
    """One spelling of "hash these things", so two adapters cannot disagree about salting.

    Each part is length-prefixed, because `("ab", "c")` and `("a", "bc")` are different inputs
    and a plain concatenation would give them the same digest.
    """
    hasher = hashlib.sha256()
    for part in parts:
        raw = part.encode() if isinstance(part, str) else part
        hasher.update(str(len(raw)).encode())
        hasher.update(b"\0")
        hasher.update(raw)
    return hasher.hexdigest()


def item_id(source: str, ref: str) -> str:
    """`sha256(source + "\\n" + ref)`. Opaque, stable, and not a path."""
    return digest_of(source, ref)


class BaseSourceAdapter(ABC):
    """One upstream catalogue, read safely.

    Subclasses set `name` and `capabilities` and implement the two `_fetch_*` methods. The
    client is injected so a test never reaches the network and CI never can — which is
    acceptance criterion 17, held by fixtures rather than by discipline.
    """

    name: str
    capabilities: SourceCapabilities

    def __init__(self, client: httpx.AsyncClient, *, now: datetime | None = None) -> None:
        self._client = client
        self._now = now
        """A fixed clock for tests. Production passes `None` and reads the real one at the
        moment of the sync — a snapshot's `synced_at` is a fact about when, and freezing it in
        a constructor would date every future sync to process start."""

    # ── the two source-specific questions ──────────────────────────────────────────────

    @abstractmethod
    async def _fetch_catalogue(self, previous: SourceSnapshot | None) -> RawCatalogue:
        """Everything the source lists. Pass `previous.etag` for a conditional request."""

    @abstractmethod
    async def _fetch_bundle(self, item: CatalogueItem) -> RawBundle:
        """One tool's files, at `item.source_revision`."""

    # ── what every source gets for free ────────────────────────────────────────────────

    async def sync(self, previous: SourceSnapshot | None = None) -> SourceSnapshot:
        """Read the catalogue and normalise it into a snapshot.

        **A refusal here leaves `previous` untouched**, because it raises rather than returning
        a degraded snapshot. The caller records the failure and keeps showing the last good
        data marked stale, which is §4.3's rule and the reason the empty state can honestly say
        *no successful source sync* rather than *0 tools*.
        """
        raw = await self._fetch_catalogue(previous)
        if raw.unchanged:
            if previous is None:
                raise UpstreamError(
                    coded("MF0203", f"{self.name}: the source reported no change and there is")
                    + " no previous snapshot to reuse"
                )
            return previous.model_copy(update={"synced_at": self._clock(), "etag": raw.etag})
        if not raw.complete:
            raise UpstreamError(
                coded("MF0200", f"{self.name}: the catalogue came back incomplete")
                + f"\n  {len(raw.items)} item(s) read, and the source said there are more"
                + "\n  a partial list produces a wrong total and a wrong denominator, so it"
                + " is refused rather than published"
            )
        return SourceSnapshot(
            source=self.name,
            source_revision=raw.source_revision,
            etag=raw.etag,
            synced_at=self._clock(),
            items=tuple(
                self._normalise(item, raw.source_revision)
                for item in sorted(raw.items, key=lambda i: i.ref)
            ),
        )

    async def bundle(self, item: CatalogueItem) -> SourceBundle:
        """Fetch one tool's content and freeze it."""
        raw = await self._fetch_bundle(item)
        files = tuple(
            file.model_copy(update={"digest": digest_of(file.text)}) for file in raw.files
        )
        numbered = number(raw.evidence)
        known = {entry.id for entry in numbered}
        unknown = sorted(
            fact.evidence_id
            for fact in raw.facts
            if fact.evidence_id is not None and fact.evidence_id not in known
        )
        if unknown:
            # A fact citing an id the bundle does not carry is a citation a reviewer cannot
            # follow, which is the exact failure `evidence_id: None` exists to make unnecessary.
            raise UpstreamError(
                coded("MF0204", f"{self.name}: {item.ref} cites evidence it does not carry")
                + f"\n  missing: {', '.join(unknown)}"
                + "\n  use evidence_id=None for a derived value rather than inventing an id"
            )
        return SourceBundle(
            item=item.model_copy(update={"source_revision": raw.source_revision}),
            source_digest=digest_of(*(f"{f.path}\0{f.digest}" for f in sorted(files, key=_path))),
            files=tuple(sorted(files, key=_path)),
            evidence=numbered,
            facts=tuple(sorted(raw.facts, key=lambda fact: fact.name)),
        )

    def observe(self, bundle: SourceBundle) -> Observation:
        """The bundle as the pre-existing `Observation` shape.

        **An adapter into the old type, not a replacement of it.** `scaffold.py`, `assemble.py`
        and the verification ladder all speak `Observation`, and rewriting them to speak
        `SourceBundle` is Task 5's business rather than this file's. Keeping the translation
        here and explicit means the catalogue path can land without touching any of them.
        """
        from mendel_forge.observe import Fact

        return Observation(
            source=bundle.item.source,
            ref_id=f"{bundle.item.source}:{bundle.item.ref}",
            facts={
                fact.name: Fact(value=fact.value, evidence=_cited(bundle, fact))
                for fact in bundle.facts
            },
            prose=[e.excerpt for e in bundle.evidence if e.kind == "prose"],
        )

    def freshness(self, item: CatalogueItem, landed: LandedSource | None):
        """Delegates, so there is one implementation of the comparison. See `CatalogueItem`."""
        return item.freshness(landed)

    # ── the machinery a subclass calls rather than reimplements ─────────────────────────

    async def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        etag: str | None = None,
        accept_304: bool = False,
    ) -> httpx.Response:
        """One request, retried on the statuses that can change, and never on the ones that
        cannot.

        **`Retry-After` is honoured when the server sends it.** Guessing a backoff against a
        server that has just told you how long to wait is how a client earns a longer ban.
        """
        sent = dict(headers or {})
        if etag:
            sent["If-None-Match"] = etag
        last: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await self._client.get(url, headers=sent)
            except httpx.HTTPError as failure:
                last = failure
                if attempt == MAX_ATTEMPTS - 1:
                    break
                await self._sleep(self._backoff(attempt))
                continue
            if response.status_code == 304:
                # **A 304 the caller did not ask for is an error, not a success.** It is below
                # 400, so the `< 400` branch below would hand back a response with an empty
                # body — and an empty body parsed as a catalogue is zero tools, which is the
                # one failure this whole file is arranged to prevent. Found by a test rather
                # than by reading: `304 < 400` is true and looks like nothing.
                if accept_304:
                    return response
                raise UpstreamError(
                    coded("MF0201", f"{self.name}: {url} answered 304 and nothing asked it to")
                    + "\n  no validator was sent, so there is no cached response to reuse"
                )
            if response.status_code < 400:
                return response
            if response.status_code not in RETRYABLE or attempt == MAX_ATTEMPTS - 1:
                raise UpstreamError(
                    coded("MF0201", f"{self.name}: {url} answered {response.status_code}")
                    + _hint(response)
                )
            await self._sleep(self._retry_after(response) or self._backoff(attempt))
        raise UpstreamError(
            coded("MF0202", f"{self.name}: {url} could not be reached")
            + f"\n  {MAX_ATTEMPTS} attempts, last error: {last}"
        )

    async def paginate(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        page_size: int = 100,
        limit: int = 200,
    ) -> list[dict]:
        """Follow a `next` cursor to the end, and refuse to stop early quietly.

        `limit` is a **circuit breaker, not a page budget**: hitting it raises rather than
        returning what was collected, because a truncated list that looks complete is exactly
        the failure `complete` exists to prevent. A source that legitimately grows past it
        needs the number raised deliberately.
        """
        collected: list[dict] = []
        following: str | None = f"{url}{'&' if '?' in url else '?'}page_size={page_size}"
        pages = 0
        while following:
            body = (await self.get(following, headers=headers)).json()
            collected.extend(body.get("results") or [])
            following = body.get("next")
            pages += 1
            if pages > limit:
                raise UpstreamError(
                    coded("MF0200", f"{self.name}: {url} paged past {limit} pages")
                    + f"\n  {len(collected)} collected and more remain — raise the limit"
                    + " deliberately rather than accepting a partial catalogue"
                )
        return collected

    # ── internals ──────────────────────────────────────────────────────────────────────

    def _clock(self) -> datetime:
        return self._now or datetime.now(UTC)

    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    @staticmethod
    def _backoff(attempt: int) -> float:
        """Exponential with full jitter, capped.

        Jitter because every worker in a fleet retrying on the same schedule reconstructs the
        thundering herd the backoff exists to prevent.
        """
        ceiling = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2**attempt))
        return random.uniform(0, ceiling)  # noqa: S311 — backoff jitter, not a secret

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        if not raw:
            return None
        try:
            return min(float(raw), BACKOFF_CAP_SECONDS * 4)
        except ValueError:
            return None

    def _normalise(self, raw: RawItem, source_revision: str) -> CatalogueItem:
        return CatalogueItem(
            id=item_id(self.name, raw.ref),
            source=self.name,
            ref=raw.ref,
            display_name=raw.display_name or raw.ref,
            summary=raw.summary,
            homepage_url=raw.homepage_url,
            documentation_url=raw.documentation_url,
            repository_url=raw.repository_url,
            licence=raw.licence,
            keywords=raw.keywords,
            categories=raw.categories,
            maintainers=raw.maintainers,
            latest_version=raw.latest_version,
            container_refs=raw.container_refs,
            source_revision=source_revision,
            content_digest=raw.content_digest,
            last_updated_at=raw.last_updated_at,
            input_hints=raw.input_hints,
            output_hints=raw.output_hints,
            capabilities=raw.capabilities,
            adaptable=raw.adaptable,
            unsupported_reason=raw.unsupported_reason,
            evidence=tuple(e.excerpt for e in number(raw.evidence)),
        )


def number(evidence: Sequence[RawEvidence]) -> tuple[NumberedExcerpt, ...]:
    """`E001`, `E002`, … in the order given.

    **In the order given, deliberately, and not sorted.** An adapter assembles evidence in a
    reading order that means something — a description before its ports, a Dockerfile before
    its README — and re-sorting would scatter it. What must not happen is *renumbering between
    syncs*, which is a property of the adapter emitting a stable order, and
    `test_evidence_ids_are_stable_across_syncs` is what checks it.
    """
    return tuple(
        NumberedExcerpt(
            id=f"E{index:03d}",
            excerpt=Excerpt(locator=item.locator, text=item.text),
            kind=item.kind,
        )
        for index, item in enumerate(evidence, start=1)
    )


def _path(file: BundleFile) -> str:
    return file.path


def _cited(bundle: SourceBundle, fact: BundleFact) -> Excerpt:
    """The excerpt a fact points at, or an honest statement that it was derived.

    **Never a fabricated quotation, and never a guess at which excerpt "looks related".** An
    earlier draft matched an excerpt whose locator merely ended with the fact's name, which
    invents a citation out of a string coincidence — exactly what `nfcore.py` records as worse
    than citing nothing, because a reviewer who follows a false citation finds text that does
    not support the claim and cannot tell that from a claim that is simply wrong.

    A fact with no `evidence_id` gets a locator naming the bundle and a text that *says* it was
    derived, so the absence is legible rather than disguised.
    """
    if fact.evidence_id is not None:
        found = bundle.excerpt(fact.evidence_id)
        if found is not None:
            return found.excerpt
    at = f"{bundle.item.source}:{bundle.item.ref}@{bundle.item.source_revision}"
    return Excerpt(locator=at, text=f"derived from the {bundle.item.source} bundle, not quoted")


def _hint(response: httpx.Response) -> str:
    if response.status_code == 404:
        return "\n  the source lists it and the fetch found nothing — the revision may have moved"
    if response.status_code in (401, 403):
        return (
            "\n  set a token if the source needs one; public development works within the"
            " provider's anonymous rate limit"
        )
    return ""
