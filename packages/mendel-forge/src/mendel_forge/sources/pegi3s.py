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
from collections.abc import Iterable, Mapping
from datetime import datetime

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.catalogue import (
    BundleFile,
    CatalogueItem,
    Classification,
    ContainerRef,
    FilterNode,
    SourceCapabilities,
    SourceFact,
    SourceSnapshot,
    SyncWarning,
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
from mendel_forge.sources.dio import (
    Assignments,
    Entry,
    Ontology,
    normalise,
    parse_diaf,
    parse_metadata,
    parse_obo,
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

**The floor, not the answer.** `_capabilities` raises `supplies_tests` per tool when its
metadata entry carries one — see there. nf-core's constant is genuinely uniform across its
catalogue; PEGiS's is not, and a class constant that under-reports what a particular tool
supplies costs that tool a validation rung it could have had.
"""

TEST_FIELDS = ("test_invocation", "test_data", "test_result")
"""What makes a PEGiS entry runnable, and the reason it matters more here than anywhere else.

nf-core ships nf-test files; PEGiS ships three strings — a command, an input, and the file that
command should produce. That is a weaker artefact and it is the **only** executable check these
tools have, which makes it the thing standing between a model-authored module and nobody
knowing whether it works.

A tool with all three can have a stub fixture generated for it. One with none cannot, and the
scaffold needs to know which it is looking at rather than assuming the worse case for both."""

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

CENTRAL: dict[str, str] = {
    "metadata": "metadata/metadata.json",
    "obo": "metadata/dio.obo",
    "diaf": "metadata/dio.diaf",
}
"""PEGiS's authoritative central files, and the three jobs they do.

Categories are **not** stored inside a tool's directory and are **not** inferrable from a
description or a Docker Hub topic. They live here, and the project's own `CONTRIBUTING.md` is
what says which file does what: `metadata.json` describes each image, `dio.obo` defines the
classification ontology, `dio.diaf` assigns ontology terms to images.

Fetched from one resolved commit per sync — see `_central` for why independently is wrong."""

RESERVED = frozenset({"metadata", ".github"})
"""Top-level directories in `dockerfiles` that are not tools.

Their files sit one level down exactly like a tool's do, so the path partition that finds tool
directories files them under a phantom tool. Excluded by name because there is no structural
signal to distinguish them; a real Docker Hub repository called `metadata` would collide and is
a decision for whoever meets it."""


class _Repo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str = ""
    last_updated: datetime | None = None


class _SourceTree(BaseModel):
    """One read of `pegi3s/dockerfiles`, split into the two things it answers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commit: str
    tools: Mapping[str, dict[str, str]]
    """`{tool directory: {filename: blob sha}}`."""
    central: Mapping[str, str]
    """`{path: blob sha}` for the files in `CENTRAL`, from this same tree."""


class _Central(BaseModel):
    """The three central files, parsed and indexed, for one sync."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    entries: Mapping[str, Entry]
    ontology: Ontology
    assignments: Assignments
    warnings: tuple[SyncWarning, ...] = ()

    def classifications(self, tool: str) -> tuple[Classification, ...]:
        """Every category for `tool`, direct first, then inherited.

        **Direct and inherited are both present and stay distinguishable.** A tool assigned to
        *Quality* must be findable under *Sequences* — §6 — and a reviewer must still be able to
        see that *Sequences* is not a claim the source made about it. Flattening them into one
        undifferentiated list is the loss that rule forbids.
        """
        direct = self.assignments.for_tool(tool)
        found: list[Classification] = [
            self._one(term_id, direct=True) for term_id in direct if self.ontology.get(term_id)
        ]
        inherited: list[str] = []
        for term_id in direct:
            for ancestor in self.ontology.ancestors(term_id):
                if ancestor not in direct and ancestor not in inherited:
                    inherited.append(ancestor)
        found += [
            self._one(term_id, direct=False)
            for term_id in sorted(inherited)
            if self.ontology.get(term_id)
        ]
        return tuple(found)

    def _one(self, term_id: str, *, direct: bool) -> Classification:
        term = self.ontology.terms[term_id]
        return Classification(
            id=term.id,
            name=term.name,
            definition=term.definition,
            parents=term.parents,
            ancestors=self.ontology.ancestors(term_id),
            path=self.ontology.path(term_id),
            direct=direct,
        )


class Pegi3sAdapter(BaseSourceAdapter):
    """The `pegi3s` Docker Hub namespace, joined to its Dockerfile repository."""

    name = "pegi3s"
    capabilities = CAPABILITIES

    _hub_session: str | None = None
    """The Docker Hub JWT, minted on first use and held for the life of the adapter.

    A class attribute read through the instance, so a subclass or a test can set it without an
    `__init__` existing only to declare it — this adapter has none, and adding one to hold a
    cache would be the whole reason it existed."""

    def _github(self) -> dict[str, str]:
        """**The GitHub half only.** Docker Hub says what images exist and needs no credential
        for a public namespace; the token is a GitHub rate limit and belongs on the requests
        that spend it."""
        return {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **self._github_auth(),
        }

    # ── catalogue ──────────────────────────────────────────────────────────────────────

    async def _fetch_catalogue(self, previous: SourceSnapshot | None) -> RawCatalogue:
        """Discovery from Docker Hub, enriched from the central metadata at one commit.

        **The order is the design.** Docker Hub says what images exist — that is discovery and
        it is unchanged. The GitHub files say what those images *are* and where they sit in the
        taxonomy — that is enrichment. Reversing it would make a tool's existence depend on
        somebody having written it into `metadata.json`, which is a different and worse
        catalogue.
        """
        commit = await self._source_head()
        repositories = await self._repositories()
        tree = await self._tree(commit)
        central = await self._central(tree, (repo.name for repo in repositories))

        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def one(repo: _Repo) -> RawItem:
            async with semaphore:
                tags = await self._tags(repo.name)
            return _item(repo, tags, tree.tools.get(repo.name), commit, central)

        items = await asyncio.gather(*(one(r) for r in repositories))
        return RawCatalogue(
            source_revision=commit,
            items=tuple(items),
            filters=_filters(central, items),
            warnings=(*central.warnings, *_missing_metadata(central, items)),
            # **Docker Hub is paged and `paginate` refuses a partial read**, so reaching here
            # means the list is whole. `complete` is not a guess.
            complete=True,
        )

    async def _hub(self) -> dict[str, str]:
        """Docker Hub headers, with a session when one can be minted.

        **This is the one credential that buys reach rather than rate.** The namespace is
        public and every field read from it is public, but Hub caps `page_size` at 100 and
        refuses any offset without a session — *pagination offset too large for anonymous
        requests; sign in to page further*. The pegi3s namespace holds 199 repositories, so
        anonymous access sees exactly the first 100 and `paginate` refuses the short list
        rather than publishing two thirds of a catalogue. Measured 2026-09-06.

        **Minted once per adapter and never logged.** Hub has no bearer form that takes the
        token directly: a username and token are exchanged for a JWT, which is why the setting
        is a pair. A failure here raises rather than falling back to anonymous, because a silent
        downgrade lands back on the 100-of-199 wall with a credential configured and nothing
        saying it was ignored.
        """
        if self._hub_session is not None:
            return {"Authorization": f"Bearer {self._hub_session}"}
        if self._credentials.dockerhub is None:
            return {}

        user, secret = self._credentials.dockerhub
        response = await self._client.post(
            f"{HUB}/auth/token",
            json={"identifier": user, "secret": secret},
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise UpstreamError(
                coded("MF0201", f"{self.name}: Docker Hub refused the credential")
                + f"\n  {response.status_code} from {HUB}/auth/token"
                + "\n  check COMENI_FORGE_DOCKERHUB_USER and COMENI_FORGE_DOCKERHUB_TOKEN;"
                + " the token needs only public repository read"
            )
        session = str(response.json().get("access_token") or "")
        if not session:
            raise UpstreamError(
                coded("MF0201", f"{self.name}: Docker Hub returned no access token")
            )
        self._hub_session = session
        return {"Authorization": f"Bearer {session}"}

    async def _repositories(self) -> list[_Repo]:
        """Every public repository in the namespace.

        Through the **namespace-scoped v2 endpoint**, not the deprecated
        `/v2/repositories/{namespace}` form. `paginate` follows `next` to the end and raises
        rather than stopping early.
        """
        rows = await self.paginate(
            f"{HUB}/namespaces/{NAMESPACE}/repositories", headers=await self._hub()
        )
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
            f"{HUB}/namespaces/{NAMESPACE}/repositories/{repository}/tags",
            headers=await self._hub(),
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

    async def _tree(self, commit: str) -> _SourceTree:
        """One tree read, answering two questions: which images have source, and where the
        central metadata files are.

        Read once for the whole catalogue rather than per repository: one request answers *which
        images have source* for all ~190 of them, where 190 directory probes would be 190
        requests against a rate limit. The three `metadata/` blobs come out of the **same**
        response, which is what makes "all three files from one commit" structural rather than a
        convention somebody has to remember.

        **`metadata/` is not a tool.** Its files sit one directory down like every tool's do, so
        the naive partition below files them under a phantom tool called `metadata`. It is
        excluded by name; a Docker Hub repository called `metadata` would be a real collision and
        `RESERVED` is where that would be argued out.
        """
        url = f"{GITHUB}/repos/{SOURCE_OWNER}/{SOURCE_REPO}/git/trees/{commit}?recursive=1"
        body = (await self.get(url, headers=self._github())).json()
        if body.get("truncated"):
            raise UpstreamError(
                coded("MF0200", f"{self.name}: the {SOURCE_REPO} tree came back truncated")
                + "\n  every image would read as undocumented, which is a false total"
            )
        tools: dict[str, dict[str, str]] = {}
        central: dict[str, str] = {}
        for entry in body.get("tree", []):
            if entry.get("type") != "blob":
                continue
            path = str(entry["path"])
            if "/" not in path:
                continue
            if path in CENTRAL.values():
                central[path] = str(entry["sha"])
                continue
            directory, _, filename = path.partition("/")
            if directory in RESERVED:
                continue
            tools.setdefault(directory, {})[filename] = str(entry["sha"])
        return _SourceTree(commit=commit, tools=tools, central=central)

    async def _central(self, tree: _SourceTree, discovered: Iterable[str]) -> _Central:
        """`metadata.json`, `dio.obo` and `dio.diaf`, read once and indexed.

        **Three blob reads per sync, from the commit the tree came from.** Not per tool, and not
        from `master` independently — fetching `dio.obo` from one commit and `dio.diaf` from
        another lets an assignment reference a term the ontology read does not carry, which
        looks exactly like upstream corruption and is entirely self-inflicted.

        Order matters: the ontology is parsed first because `parse_diaf` needs the known term
        ids to tell a renamed term from a real one, and the discovered tool names because it
        must refuse to fabricate a tool nobody can run.
        """
        warnings: list[SyncWarning] = []

        async def text(key: str) -> str:
            sha = tree.central.get(CENTRAL[key])
            if sha is None:
                warnings.append(
                    SyncWarning(
                        code="MF0205",
                        detail=(
                            f"{CENTRAL[key]} is not in {SOURCE_REPO} at {tree.commit[:7]}; "
                            "every tool loses its classifications for this sync"
                        ),
                        subject=CENTRAL[key],
                    )
                )
                return ""
            return await self._blob(sha)

        metadata_text, obo_text, diaf_text = (
            await text("metadata"),
            await text("obo"),
            await text("diaf"),
        )

        entries, metadata_warnings = parse_metadata(metadata_text)
        ontology, obo_warnings = parse_obo(obo_text)
        assignments, diaf_warnings = parse_diaf(diaf_text, ontology.terms, discovered)
        warnings += [
            SyncWarning(code=w.code, detail=w.detail, subject=w.subject)
            for w in (*metadata_warnings, *obo_warnings, *diaf_warnings)
        ]
        return _Central(
            entries=entries,
            ontology=ontology,
            assignments=assignments,
            warnings=tuple(warnings),
        )

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
        blobs = (await self._tree(commit)).tools.get(item.ref) or {}
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
    repo: _Repo,
    tags: list[dict],
    blobs: dict[str, str] | None,
    commit: str,
    central: _Central,
) -> RawItem:
    """One catalogue row: Docker Hub discovery, enriched from the central metadata."""
    refs = _container_refs(repo.name, tags)
    reason = _why_not(refs, blobs)
    documentation = sorted(blobs or {})
    entry = central.entries.get(normalise(repo.name))
    facts = entry.facts() if entry else ()
    by_name = dict(facts)
    classifications = central.classifications(repo.name)

    return RawItem(
        ref=repo.name,
        display_name=repo.name,
        # **`metadata.json` outranks Docker Hub's blurb.** It is the description PEGiS
        # maintains; the Hub's is a one-line summary that is often empty or stale. Falling back
        # rather than replacing keeps a tool with no entry exactly as readable as before.
        summary=_first(by_name.get("description"), repo.description),
        homepage_url=f"https://hub.docker.com/r/{NAMESPACE}/{repo.name}",
        # `manual_url` when PEGiS publishes one, else the source directory. A manual is
        # documentation; a directory listing is where the recipe lives.
        documentation_url=_first(
            by_name.get("manual_url"),
            f"https://github.com/{SOURCE_OWNER}/{SOURCE_REPO}/tree/{commit}/{repo.name}"
            if blobs
            else None,
        ),
        repository_url=f"https://github.com/{SOURCE_OWNER}/{SOURCE_REPO}",
        # **`latest` from metadata beats the tag heuristic**, because it is the publisher
        # stating a version rather than this adapter recognising a tag shape. The heuristic
        # stays as the fallback for a tool with no entry — that is discovery behaviour and §1
        # says not to replace it without cause.
        latest_version=_first(by_name.get("latest"), _proved_version(tags)),
        container_refs=refs,
        last_updated_at=repo.last_updated,
        # `input_data_type` is PEGiS stating what the tool eats, in its own words. A *hint*, in
        # the field's own sense — not a port, not a type id, and never resolved into one here.
        input_hints=tuple(_split(by_name.get("input_data_type"))),
        # **`test_result` is the only machine-readable output signal PEGiS has**, and it is one
        # filename rather than a port list. A tool that writes four files names one of them
        # here, so this is a floor on the outputs and never the set of them — which is exactly
        # what `output_hints` means and why it is not `produces`.
        output_hints=tuple(_split(by_name.get("test_result"))),
        classifications=classifications,
        source_facts=tuple(SourceFact(name=name, value=value) for name, value in facts),
        capabilities=_capabilities(entry),
        adaptable=reason is None,
        unsupported_reason=reason,
        content_digest=_digest(repo, refs, blobs, entry, classifications, central),
        evidence=_catalogue_evidence(repo, refs, documentation, entry, classifications),
    )


def _digest(
    repo: _Repo,
    refs: tuple[ContainerRef, ...],
    blobs: dict[str, str] | None,
    entry: Entry | None,
    classifications: tuple[Classification, ...],
    central: _Central,
) -> str:
    """Everything about *this* tool that a person would want to re-review, canonically.

    §9's list, and the reason each part is here:

    - **image pins** — a new image is new behaviour;
    - **source files** — a rewritten README is new evidence for ports inferred from prose;
    - **its `metadata.json` entry** — a changed invocation or status changes what the tool is;
    - **its direct assignments** — a reclassification changes where it belongs;
    - **every referenced term and its ancestors**, by id *and* by name and definition, because
      renaming `Quality` changes what a reviewer reads without changing any id.

    **Ancestors are included deliberately and the cost is stated.** Renaming a term high in the
    tree — `Data_type` — will age every tool beneath it. That is correct rather than
    unfortunate: the breadcrumb those tools display has genuinely changed. What it must not do
    is age tools on *other* branches, and it does not, because only this tool's own ancestry is
    hashed.

    Nothing here reads the repository HEAD, a timestamp or an HTTP header. Two syncs of
    unchanged content produce the same digest.
    """
    ontology = central.ontology
    return digest_of(
        *(ref.pinned() for ref in refs),
        *(f"{name}\0{sha}" for name, sha in sorted((blobs or {}).items())),
        *(f"{name}\0{value}" for name, value in (entry.facts() if entry else ())),
        # Direct assignments are hashed as ids; the terms themselves carry their own text, so a
        # renamed category moves the digest of every tool that displays it.
        *(f"direct\0{c.id}" for c in classifications if c.direct),
        *(
            f"term\0{c.id}\0{term.name}\0{term.definition}\0{','.join(term.parents)}"
            for c in classifications
            if (term := ontology.get(c.id)) is not None
        ),
    )


def _capabilities(entry: Entry | None) -> SourceCapabilities:
    """`CAPABILITIES`, with `supplies_tests` raised for a tool that carries a runnable check.

    **Per tool, because PEGiS is not uniform.** nf-core's capabilities are a fact about the
    whole catalogue — every module there ships a process, structured ports and nf-test files.
    PEGiS's are a fact about the *adapter's reach* for most fields and a fact about the
    *entry* for this one: some tools name a test command, an input and an expected result, and
    most do not.

    Why it is worth distinguishing: the module for a PEGiS tool has to be **authored**, and an
    authored module is exactly the artefact nobody can trust on inspection. A tool that can be
    stub-run against a known input and a known output file can be *checked*; one that cannot
    reaches review on prose alone. Flattening both to `supplies_tests=False` throws away the
    difference at the moment it matters most.

    All three fields are required. A command with no expected result proves the process starts,
    which is not the same as proving it did anything.
    """
    if entry is None:
        return CAPABILITIES
    facts = dict(entry.facts())
    return CAPABILITIES.model_copy(
        update={"supplies_tests": all(facts.get(field) for field in TEST_FIELDS)}
    )


def _first(*values: str | None) -> str | None:
    """The first value that is present and non-empty.

    An explicitly empty upstream field is an unknown, not a claim — §3 — so it falls through to
    the next candidate rather than winning as a blank.
    """
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _split(value: str | None) -> list[str]:
    """A comma-separated metadata field as a list, unchanged otherwise."""
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _missing_metadata(central: _Central, items: Iterable[RawItem]) -> tuple[SyncWarning, ...]:
    """A discovered image with no `metadata.json` entry.

    **A diagnostic, and the tool stays visible.** §7's first rule. An image PEGiS publishes and
    has not documented centrally is a real, pullable tool with less evidence behind it — hiding
    it would make the catalogue smaller than the namespace, and quietly.
    """
    return tuple(
        SyncWarning(
            code="MF0208",
            detail=(
                f"{item.ref} is published on Docker Hub and has no metadata.json entry, so it "
                "carries no central description or classifications"
            ),
            subject=item.ref,
        )
        for item in items
        if normalise(item.ref) not in central.entries
    )


def _filters(central: _Central, items: Iterable[RawItem]) -> tuple[FilterNode, ...]:
    """The whole ontology as a filter tree, whether or not any tool uses a branch.

    **Built from `dio.obo`, not from the tools.** A tree assembled from the classifications that
    happen to be in use is missing every branch nobody has been assigned to yet, which makes the
    filter narrower than the vocabulary and does so silently. §6 asks that the API can return
    this without scanning the catalogue, which is why it lands on the snapshot.

    `direct_count` counts only tools assigned to the node itself. A consumer wanting the total
    beneath a node walks `children`, because the answer depends on which other filters are
    applied and a snapshot cannot know that.
    """
    ontology = central.ontology
    direct: dict[str, int] = {}
    for item in items:
        for found in item.classifications:
            if found.direct:
                direct[found.id] = direct.get(found.id, 0) + 1

    children: dict[str, list[str]] = {}
    for term in ontology.terms.values():
        for parent in term.parents:
            children.setdefault(parent, []).append(term.id)

    return tuple(
        FilterNode(
            id=term.id,
            name=term.name,
            definition=term.definition,
            parents=term.parents,
            children=tuple(sorted(children.get(term.id, ()))),
            path=ontology.path(term.id),
            direct_count=direct.get(term.id, 0),
        )
        for term in sorted(ontology.terms.values(), key=lambda t: t.id)
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
    repo: _Repo,
    refs: tuple[ContainerRef, ...],
    documentation: list[str],
    entry: Entry | None = None,
    classifications: tuple[Classification, ...] = (),
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
    for name, value in entry.facts() if entry else ():
        found.append(
            RawEvidence(
                locator=f"{SOURCE_OWNER}/{SOURCE_REPO}/{CENTRAL['metadata']}:{repo.name}.{name}",
                text=f"{name}: {value}",
                kind="metadata",
            )
        )
    # **Labelled as a classification, and only the direct ones.**
    #
    # §8: a PEGiS category is authoritative catalogue and filter metadata and useful context for
    # a model — and it is *not* a port declaration. A dossier entry reading "PEGiS classifies
    # this as ..." is a claim about where the tool belongs; one reading "Sequences" beside a
    # list of ports invites exactly the inference that rule forbids, so the sentence carries its
    # own frame.
    #
    # Inherited terms are excluded here: they are true, and they are not something the source
    # said about this tool. Sending them as evidence would put a claim nobody made in front of a
    # model, which is the same reason `Classification.direct` exists at all.
    for found_class in (c for c in classifications if c.direct):
        breadcrumb = " > ".join(found_class.path) or found_class.name
        definition = f" — {found_class.definition}" if found_class.definition else ""
        found.append(
            RawEvidence(
                locator=(
                    f"{SOURCE_OWNER}/{SOURCE_REPO}/{CENTRAL['diaf']}:{found_class.id}"
                ),
                text=(
                    f"PEGiS classifies this tool as {found_class.id} ({breadcrumb})"
                    f"{definition}. A catalogue category, not a port or parameter declaration."
                ),
                kind="classification",
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
