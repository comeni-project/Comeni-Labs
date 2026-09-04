"""PEGiS: a Docker Hub namespace, and the source documentation that makes it adaptable.

**This is issue #65, and it is the source the `Source` protocol was designed against rather
than built for.** `tests/fixtures/opaque` has stood in for it since Phase 1 — no module, almost
everything a hole — and this is the real thing. The difference from nf-core is total: there is
no Nextflow process, no structured port metadata, no versions block, and no `meta.yml`. What
there is: an image, a Dockerfile, and some English.

**Two upstreams joined, and neither is scraped.** Docker Hub's namespace API says what images
exist; `pegi3s/dockerfiles` at a recorded commit says what they *are*. HTML is never parsed —
the plan says so and it is the right rule, because a rendered page is a presentation that
changes without notice and an API is a contract.

**An entry with no matching source stays visible.** This is the rule that keeps the catalogue
honest about its own size: a Docker Hub repository the adapter cannot assemble a dossier for is
marked `adaptable=False` with a reason a person can read, not filtered out. `discovered` and
`adaptable` then differ, both are shown, and the progress bar's denominator is the smaller one
with the larger stated beside it.

**`latest` is an alias and never a version.** A publisher can repoint it tomorrow. An entry
whose only tag is `latest` has `latest_version=None` — a visible hole — and is still adaptable,
because the image can be pinned by *digest* even when its version is unknown. Those are two
different facts and conflating them is how a proposal ends up pinning a moving tag.

**One platform is selected and the rest are kept.** The MVP writes `linux/amd64` into a
proposal; dropping the other platforms from the record would make a future arm64 decision
unrecoverable without a full re-sync, so they are all preserved in `container_refs`.
"""

import asyncio
import base64
import re
from datetime import datetime

import httpx
from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.catalogue import (
    BundleFile,
    CatalogueItem,
    ContainerRef,
    SourceCapabilities,
    SourceSnapshot,
)
from mendel_forge.sources.base import (
    BaseSourceAdapter,
    RawBundle,
    RawCatalogue,
    RawEvidence,
    RawItem,
    UpstreamError,
    digest_of,
)

HUB = "https://hub.docker.com/v2"
NAMESPACE = "pegi3s"
REGISTRY = "docker.io"
GITHUB = "https://api.github.com"
SOURCE_OWNER = "pegi3s"
SOURCE_REPO = "dockerfiles"
SOURCE_BRANCH = "master"
PLATFORM = ("linux", "amd64")

CAPABILITIES = SourceCapabilities(
    supplies_nextflow=False,
    supplies_structured_ports=False,
    supplies_container_digest=True,
    supplies_tests=False,
)
"""The mirror image of nf-core's, and the reason `SourceCapabilities` exists at all.

A scaffold reads these and behaves differently: with no Nextflow upstream a module has to be
*authored*, which is the single largest difference in how much a model is trusted with, and
with no structured ports every port is a hole rather than a hole in a known shape.
"""

SEMVER = re.compile(r"^v?\d+(\.\d+)*([.-][A-Za-z0-9]+)*$")
"""What counts as a version tag.

Deliberately loose — `1.2`, `v3`, `2.10.1-2` are all real PEGiS tags — and deliberately
anchored, so `latest`, `stable` and `dev` do not match. A tag that is not a version is not
evidence of one.
"""

ALIASES = frozenset({"latest", "stable", "master", "main", "dev", "edge"})
"""Tags that name a moving target rather than a release. Never a `latest_version`.

**Redundant today, and that is recorded rather than hidden.** Anchored `SEMVER` already rejects
every name in this set — none of them starts with a digit — so deleting this line changes no
current answer. It was written as a guard and it is, right now, a guard that cannot fire, which
is the shape CLAUDE.md names: a check that reads as protection while doing nothing.

It is kept for one reason and the reason is testable: `SEMVER` is the *only* thing standing
between an alias and a version claim, and it is a regex somebody will eventually loosen to
accept a tag shape PEGiS starts using.
`test_the_alias_list_is_redundant_only_while_semver_is_strict` fails the moment that happens,
which turns this from dead code into a second line that somebody has been told is now
load-bearing.

What neither can catch: a *floating numeric* tag — `pegi3s/tool:1` meaning "latest 1.x" — which
is an alias wearing a version's clothes and is indistinguishable from a release by name alone.
That is a real limit, and the digest beside the version is what makes it survivable."""

CONCURRENCY = 8


class _Repo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str = ""
    last_updated: datetime | None = None


class Pegi3sAdapter(BaseSourceAdapter):
    """The `pegi3s` Docker Hub namespace, joined to its Dockerfile repository."""

    name = "pegi3s"
    capabilities = CAPABILITIES

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        token: str | None = None,
        now: datetime | None = None,
    ) -> None:
        super().__init__(client, now=now)
        self._token = token

    def _github(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    # ── catalogue ──────────────────────────────────────────────────────────────────────

    async def _fetch_catalogue(self, previous: SourceSnapshot | None) -> RawCatalogue:
        commit = await self._source_head()
        repositories = await self._repositories()
        documented = await self._documented(commit)

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def one(repo: _Repo) -> RawItem:
            async with semaphore:
                tags = await self._tags(repo.name)
            return _item(repo, tags, documented.get(repo.name), commit)

        items = await asyncio.gather(*(one(r) for r in repositories))
        return RawCatalogue(
            source_revision=commit,
            items=tuple(items),
            # **Docker Hub is paged and `paginate` refuses a partial read**, so reaching here
            # means the list is whole. `complete` is not a guess.
            complete=True,
        )

    async def _repositories(self) -> list[_Repo]:
        """Every public repository in the namespace.

        Through the **namespace-scoped v2 endpoint**, not the deprecated
        `/v2/repositories/{namespace}` form. `paginate` follows `next` to the end and raises
        rather than stopping early.
        """
        rows = await self.paginate(f"{HUB}/namespaces/{NAMESPACE}/repositories")
        return sorted(
            (
                _Repo(
                    name=str(row["name"]),
                    description=str(row.get("description") or "").strip(),
                    last_updated=_when(row.get("last_updated")),
                )
                for row in rows
                if row.get("name")
            ),
            key=lambda r: r.name,
        )

    async def _tags(self, repository: str) -> list[dict]:
        return await self.paginate(
            f"{HUB}/namespaces/{NAMESPACE}/repositories/{repository}/tags"
        )

    async def _source_head(self) -> str:
        url = f"{GITHUB}/repos/{SOURCE_OWNER}/{SOURCE_REPO}/commits/{SOURCE_BRANCH}"
        body = (await self.get(url, headers=self._github())).json()
        sha = body.get("sha")
        if not sha:
            raise UpstreamError(
                coded("MF0201", f"{self.name}: {SOURCE_REPO} resolved to no commit")
            )
        return str(sha)

    async def _documented(self, commit: str) -> dict[str, dict[str, str]]:
        """`{tool: {filename: blob sha}}` for every directory in `pegi3s/dockerfiles`.

        Read once for the whole catalogue rather than per repository: one tree request answers
        *which images have source* for all ~190 of them, where 190 directory probes would be
        190 requests against a rate limit.
        """
        url = f"{GITHUB}/repos/{SOURCE_OWNER}/{SOURCE_REPO}/git/trees/{commit}?recursive=1"
        body = (await self.get(url, headers=self._github())).json()
        if body.get("truncated"):
            raise UpstreamError(
                coded("MF0200", f"{self.name}: the {SOURCE_REPO} tree came back truncated")
                + "\n  every image would read as undocumented, which is a false total"
            )
        found: dict[str, dict[str, str]] = {}
        for entry in body.get("tree", []):
            if entry.get("type") != "blob":
                continue
            path = str(entry["path"])
            if "/" not in path:
                continue
            tool, _, filename = path.partition("/")
            found.setdefault(tool, {})[filename] = str(entry["sha"])
        return found

    # ── bundle ─────────────────────────────────────────────────────────────────────────

    async def _fetch_bundle(self, item: CatalogueItem) -> RawBundle:
        """The image's documentation, and nothing invented.

        **No Nextflow is written here.** The scaffold marks an open section and a model may
        author the module later under review; this adapter's job is to prove what the container
        *is*, and a generated process would be a proposal wearing a source's authority.
        """
        if not item.adaptable:
            raise UpstreamError(
                coded("MF0201", f"{self.name}: {item.ref} is not adaptable")
                + f"\n  {item.unsupported_reason}"
            )
        commit = item.source_revision
        documented = await self._documented(commit)
        blobs = documented.get(item.ref) or {}
        if not blobs:
            raise UpstreamError(
                coded("MF0201", f"{self.name}: {item.ref} has no source at {commit[:7]}")
                + "\n  the catalogue said it was documented and the revision disagrees — re-sync"
            )

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def one(filename: str, sha: str) -> tuple[str, str]:
            async with semaphore:
                return filename, await self._blob(sha)

        texts = dict(await asyncio.gather(*(one(n, s) for n, s in sorted(blobs.items()))))
        files = tuple(
            BundleFile(path=name, text=text, verbatim=True)
            for name, text in sorted(texts.items())
        )
        return RawBundle(
            source_revision=commit,
            files=files,
            evidence=_bundle_evidence(item, texts),
        )

    async def _blob(self, sha: str) -> str:
        url = f"{GITHUB}/repos/{SOURCE_OWNER}/{SOURCE_REPO}/git/blobs/{sha}"
        body = (await self.get(url, headers=self._github())).json()
        if body.get("encoding") != "base64":
            return str(body.get("content") or "")
        return base64.b64decode(body.get("content") or "").decode("utf-8", errors="replace")


# ── normalisation ──────────────────────────────────────────────────────────────────────


def _item(
    repo: _Repo, tags: list[dict], blobs: dict[str, str] | None, commit: str
) -> RawItem:
    """One catalogue row, and the decision about whether it can be adapted at all."""
    refs = _container_refs(repo.name, tags)
    version = _proved_version(tags)
    reason = _why_not(refs, blobs)
    documentation = sorted(blobs or {})

    return RawItem(
        ref=repo.name,
        display_name=repo.name,
        summary=repo.description,
        homepage_url=f"https://hub.docker.com/r/{NAMESPACE}/{repo.name}",
        documentation_url=(
            f"https://github.com/{SOURCE_OWNER}/{SOURCE_REPO}/tree/{commit}/{repo.name}"
            if blobs
            else None
        ),
        repository_url=f"https://github.com/{SOURCE_OWNER}/{SOURCE_REPO}",
        latest_version=version,
        container_refs=refs,
        last_updated_at=repo.last_updated,
        capabilities=CAPABILITIES,
        adaptable=reason is None,
        unsupported_reason=reason,
        # **The digest covers the image and its documentation together.** Either moving is a
        # reason to re-adapt: a new image is new behaviour, and a rewritten README is new
        # evidence for ports that were inferred from prose.
        content_digest=digest_of(
            *(ref.pinned() for ref in refs),
            *(f"{name}\0{sha}" for name, sha in sorted((blobs or {}).items())),
        ),
        evidence=_catalogue_evidence(repo, refs, documentation),
    )


def _why_not(refs: tuple[ContainerRef, ...], blobs: dict[str, str] | None) -> str | None:
    """Why this entry cannot be adapted, in words a person can act on, or `None`.

    **Both halves are required and they fail differently**, so they say different things. An
    image with no source has nothing to write a contract *from*; source with no pullable image
    has nothing to *run*. A single "unsupported" would leave a reader guessing which.
    """
    if not refs:
        return (
            "no pullable linux/amd64 image — Docker Hub lists the repository and no tag "
            "publishes a manifest for this platform"
        )
    if not blobs:
        return (
            f"no matching directory in {SOURCE_OWNER}/{SOURCE_REPO}, so there is no Dockerfile "
            "or documentation to build a dossier from"
        )
    if not any(name.lower().startswith("readme") for name in blobs) and "Dockerfile" not in blobs:
        return (
            "the source directory holds neither a Dockerfile nor a README, so nothing "
            "describes what the image does"
        )
    return None


def _container_refs(repository: str, tags: list[dict]) -> tuple[ContainerRef, ...]:
    """Every tag that publishes a manifest, with its digest and platform.

    A tag with no `images` is one Docker Hub knows the name of and holds no manifest for; it is
    dropped rather than recorded as a pin that would fail at run time.
    """
    found: list[ContainerRef] = []
    for tag in tags:
        name = str(tag.get("name") or "").strip()
        if not name:
            continue
        for image in tag.get("images") or []:
            digest = str(image.get("digest") or "").strip()
            operating_system = str(image.get("os") or "").strip()
            architecture = str(image.get("architecture") or "").strip()
            if not digest:
                continue
            found.append(
                ContainerRef(
                    registry=REGISTRY,
                    repository=f"{NAMESPACE}/{repository}",
                    tag=name,
                    digest=digest,
                    platform=f"{operating_system}/{architecture}"
                    if operating_system and architecture
                    else None,
                )
            )
    # linux/amd64 first, then the rest, then by tag — so `container_refs[0]` is the one the MVP
    # pins and the others stay recorded for a future decision.
    wanted = f"{PLATFORM[0]}/{PLATFORM[1]}"
    return tuple(
        sorted(found, key=lambda r: (r.platform != wanted, r.tag or "", r.digest or ""))
    )


def _proved_version(tags: list[dict]) -> str | None:
    """The highest version tag, or `None`.

    **`None` is a visible hole and `latest` is never the answer.** An image tagged only `latest`
    has an unknown version and a knowable digest, which are different facts — the entry stays
    adaptable and the version becomes something a reviewer resolves.
    """
    versions = [
        name
        for tag in tags
        if (name := str(tag.get("name") or "").strip())
        and name.lower() not in ALIASES
        and SEMVER.match(name)
    ]
    if not versions:
        return None
    return max(versions, key=_sortable)


def _sortable(tag: str) -> tuple:
    """`1.10` after `1.9`, which a string sort gets wrong.

    Non-numeric trailing parts sort last within their numeric prefix, so `2.1` beats `2.1-rc`.
    """
    core = tag.lstrip("vV")
    parts: list[int] = []
    for chunk in re.split(r"[.-]", core):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            return (tuple(parts), 0, tag)
    return (tuple(parts), 1, tag)


def _catalogue_evidence(
    repo: _Repo, refs: tuple[ContainerRef, ...], documentation: list[str]
) -> tuple[RawEvidence, ...]:
    found: list[RawEvidence] = []
    if repo.description:
        found.append(
            RawEvidence(
                locator=f"hub.docker.com/r/{NAMESPACE}/{repo.name}",
                text=repo.description,
                kind="metadata",
            )
        )
    if refs:
        found.append(
            RawEvidence(
                locator=f"hub.docker.com/r/{NAMESPACE}/{repo.name}/tags",
                text=refs[0].pinned(),
                kind="container",
            )
        )
    if documentation:
        found.append(
            RawEvidence(
                locator=f"{SOURCE_OWNER}/{SOURCE_REPO}/{repo.name}",
                text=f"source directory holds: {', '.join(documentation)}",
                kind="metadata",
            )
        )
    return tuple(found)


def _bundle_evidence(item: CatalogueItem, texts: dict[str, str]) -> tuple[RawEvidence, ...]:
    """The dossier, in reading order: what it is, then how it is built, then how it runs.

    A README before a Dockerfile because the README says what the tool *does* and the Dockerfile
    says how it was assembled — and a model reading the second first has to infer the first from
    `apt-get install` lines.
    """
    found: list[RawEvidence] = []
    if item.container_refs:
        found.append(
            RawEvidence(
                locator=f"hub.docker.com/r/{NAMESPACE}/{item.ref}/tags",
                text=item.container_refs[0].pinned(),
                kind="container",
            )
        )

    def add(filename: str, kind: str) -> None:
        text = texts.get(filename)
        if text and text.strip():
            found.append(
                RawEvidence(
                    locator=f"{SOURCE_OWNER}/{SOURCE_REPO}/{item.ref}/{filename}",
                    text=text.strip(),
                    kind=kind,
                )
            )

    for name in sorted(texts):
        if name.lower().startswith("readme"):
            add(name, "prose")
    add("Dockerfile", "source")
    for name in sorted(texts):
        if name.lower().startswith("readme") or name == "Dockerfile":
            continue
        add(name, "source")
    return tuple(found)


def _when(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        # `fromisoformat` has accepted a trailing `Z` since 3.11, so the usual
        # `.replace("Z", "+00:00")` is unnecessary — and it would trip the forge write
        # boundary scan, which matches the attribute name and cannot tell a string
        # substitution from `Path.replace`.
        return datetime.fromisoformat(value)
    except ValueError:
        return None
