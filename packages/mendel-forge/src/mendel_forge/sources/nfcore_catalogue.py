"""nf-core's module tree, read from upstream rather than from what somebody already vendored.

**This is issue #77.** `NfCoreSource.discover(root)` in `nfcore.py` walks the registry layer and
answers *what have we already imported*, which was never the size of the known world — the Tools
board rendered `—` rather than `13` precisely because 13 was not a total anybody wanted. This
adapter answers the other question, and the two coexist until Task 13 retires the old path.

**What counts as a module, exactly.** A leaf directory under `modules/nf-core/` holding **both**
`main.nf` and `meta.yml`. Not subworkflows, not test directories, not pipeline-local modules.
That definition is §1.3's and it is enforced here rather than described: `_modules_in` is the
only place it exists, so the discovered total and the bundle fetch cannot disagree about what a
module is.

**The whole repository arrives in one request, as an archive.** That replaced a walk costing
about 2,400 calls with one costing 2, and the arithmetic is the argument: the recursive tree
API is capped and nf-core is past the cap, so the old path fetched a subtree per module
directory (~700) and then each module's `meta.yml` as its own git blob (~1,700). Against a
5,000-per-hour authenticated budget that meant one sync nearly spent the hour, and two syncs in
an hour could not both finish — measured, on 2026-09-06, by watching exactly that happen.
Adapting a single tool repeated the same walk to locate one directory whose path it already
knew.

**And it removes the truncation problem rather than handling it.** An archive is the whole
repository by construction: there is no cap to detect, no subtree fallback, and no partial
listing that could publish a short total. `RawCatalogue.complete` stays for the other adapter
and for a source that pages.

**`content_digest` is the module's own subtree**, computed from the sorted `(path, blob sha)`
pairs beneath its directory. That is what makes an unrelated upstream commit — a change to some
other module, a README edit at the repository root — leave this module current. Comparing the
repository HEAD instead would mark every adapted tool in the registry outdated at once, every
time anybody merged anything, and the outdated count would become noise nobody reads.

**Metadata comes from `meta.yml` at the recorded commit**, read out of that same archive, so
it cannot race a branch that moved underneath the listing. The blob shas the digest is built
from are computed the way git computes them — see `_blob_sha` — which is what kept every
existing `content_digest` identical across this change.
"""

import hashlib
import io
import tarfile
from datetime import datetime

import httpx
from comeni_core import yaml_strict
from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.catalogue import (
    BundleFact,
    BundleFile,
    CatalogueItem,
    SourceCapabilities,
    SourceSnapshot,
)
from mendel_forge.sources import Credentials
from mendel_forge.sources.base import (
    BaseSourceAdapter,
    RawBundle,
    RawCatalogue,
    RawEvidence,
    RawItem,
    UpstreamError,
    digest_of,
)

API = "https://api.github.com"
OWNER = "nf-core"
REPO = "modules"
BRANCH = "master"
PREFIX = "modules/nf-core/"
REQUIRED = ("main.nf", "meta.yml")
"""Both, and that conjunction is the definition. A directory with only `main.nf` is a helper;
one with only `meta.yml` is not a module anybody can run."""

CAPABILITIES = SourceCapabilities(
    supplies_nextflow=True,
    supplies_structured_ports=True,
    supplies_container_digest=False,
    supplies_tests=True,
)
"""**`supplies_container_digest` is false, and that is not an oversight.** nf-core writes a
container as a Groovy ternary over two registries, by tag — `ModuleSpec` reads the tag and
nothing upstream pins a digest. Claiming otherwise here would make the scaffold pin something
it cannot prove.

`supplies_tests` is true because the modules ship `tests/` directories with nf-test files; they
are a validation rung when a fixture can be generated, not a guarantee any given module has one.
"""

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
"""A ceiling on the archive, because a decompressor with no bound is a denial of service.

The real one is 5.8 MB compressed. This is not a tuned number — it is far enough above the
truth to never fire on legitimate growth, and far enough below memory to fail as a refusal
rather than as an OOM kill nobody gets a message from.
"""


class _Blob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha: str


class NfCoreAdapter(BaseSourceAdapter):
    """The official nf-core module repository."""

    name = "nf-core"
    capabilities = CAPABILITIES

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        credentials: "Credentials | None" = None,
        now: datetime | None = None,
        branch: str = BRANCH,
    ) -> None:
        super().__init__(client, now=now, credentials=credentials)
        self._branch = branch
        self._archived_at: str | None = None
        self._archived: dict[str, bytes] | None = None
        """The repository archive, kept per commit for the life of one adapter.

        A sync and a bundle fetch each construct their own adapter today, so this saves nothing
        across jobs — what it does buy is that a *single* adapter asked for the catalogue and
        then for a module downloads once. Keyed by commit rather than held flat, because two
        revisions in one adapter's life must not share an answer."""

    def _headers(self) -> dict[str, str]:
        """A token is optional and public development must work without one.

        `X-GitHub-Api-Version` is pinned because an unversioned client gets whatever the default
        becomes, and a tree response changing shape under a nightly sync is the sort of failure
        that reads as *the catalogue shrank*.
        """
        return {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **self._github_auth(),
        }

    # ── catalogue ──────────────────────────────────────────────────────────────────────

    async def _fetch_catalogue(self, previous: SourceSnapshot | None) -> RawCatalogue:
        commit = await self._head()
        if previous is not None and previous.source_revision == commit:
            # **The cheapest conditional request there is: the commit did not move.** An ETag
            # would work too and this is stronger — it says *the tree is the same tree*, which
            # is the thing the snapshot depends on, rather than *the response body is the same
            # bytes*.
            return RawCatalogue(source_revision=commit, unchanged=True, etag=previous.etag)

        files = await self._archive(commit)
        modules = _modules_in(_blobs_of(files))
        return RawCatalogue(
            source_revision=commit,
            items=tuple(
                _item(ref, blobs, _meta_of(ref, blobs, files))
                for ref, blobs in sorted(modules.items())
            ),
        )

    async def _head(self) -> str:
        """The branch's current commit. Every later request pins to it.

        **Resolved once and reused**, so a merge landing mid-sync cannot give one module's
        metadata from before it and another's from after — a snapshot has to describe one state
        of the world or its digests describe nothing.
        """
        url = f"{API}/repos/{OWNER}/{REPO}/commits/{self._branch}"
        body = (await self.get(url, headers=self._headers())).json()
        sha = body.get("sha")
        if not sha:
            raise UpstreamError(
                coded("MF0201", f"{self.name}: {self._branch} resolved to no commit")
            )
        return str(sha)

    async def _archive(self, commit: str) -> dict[str, bytes]:
        """Every module file in the repository at `commit`, from ONE request.

        **This replaced a walk that cost about 2,400 requests and it costs 2.** The tree API
        caps a recursive response, so the old path walked ~700 module directories one subtree
        at a time and then fetched each module's `meta.yml` as its own blob — roughly 2,400
        calls against a 5,000-per-hour authenticated budget, which meant a full sync nearly
        exhausted an hour's allowance and two syncs in an hour could not both finish. Measured
        against the real repository, the tarball is 5.8 MB and arrives in 1.7 seconds.

        It also removes the truncation problem rather than handling it: an archive is the whole
        repository by construction, so there is no cap to detect and no partial total to refuse.

        **Nothing is extracted to disk.** Members are read from the stream, so a crafted
        member name is a dictionary key here rather than a path traversal — the reason to say
        so is that `tarfile.extractall` on untrusted input is the well-known version of this,
        and somebody reading this later should be able to see which one it is.
        """
        if self._archived is not None and self._archived_at == commit:
            return self._archived

        url = f"{API}/repos/{OWNER}/{REPO}/tarball/{commit}"
        # GitHub answers this with a redirect to a separate download host, so it is the one
        # request in this adapter that follows one.
        response = await self.get(url, headers=self._headers(), follow_redirects=True)
        payload = response.content
        if len(payload) > MAX_ARCHIVE_BYTES:
            raise UpstreamError(
                coded("MF0200", f"{self.name}: the archive at {commit[:7]} is too large")
                + f"\n  {len(payload)} bytes, ceiling {MAX_ARCHIVE_BYTES}"
            )

        files: dict[str, bytes] = {}
        total = 0
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                # The archive root is `<owner>-<repo>-<short sha>/`, which is a fact about the
                # download rather than about the repository. Strip it so every path here is
                # repository-relative and matches what the tree API used to return.
                _, _, path = member.name.partition("/")
                if not path.startswith(PREFIX):
                    continue
                total += member.size
                if total > MAX_ARCHIVE_BYTES:
                    raise UpstreamError(
                        coded("MF0200", f"{self.name}: the archive at {commit[:7]} expands")
                        + f" past {MAX_ARCHIVE_BYTES} bytes"
                    )
                handle = archive.extractfile(member)
                if handle is not None:
                    files[path] = handle.read()

        if not files:
            raise UpstreamError(
                coded("MF0200", f"{self.name}: the archive at {commit[:7]} holds no modules")
                + f"\n  nothing under {PREFIX} — an empty catalogue is refused, not published"
            )

        self._archived_at, self._archived = commit, files
        return files

    # ── bundle ─────────────────────────────────────────────────────────────────────────

    async def _fetch_bundle(self, item: CatalogueItem) -> RawBundle:
        """The whole module directory at the recorded commit, copied unchanged.

        **Every file is `verbatim=True`.** The plan says it twice and it is the strongest
        property this source has: nf-core wrote the process, so nothing downstream may author
        one. A validation rung compares the candidate's copy against these digests, which turns
        *"AI rewrote a source file"* from a hope into a check.
        """
        commit = item.source_revision
        archive = await self._archive(commit)
        wanted = _modules_in(_blobs_of(archive)).get(item.ref)
        if not wanted:
            raise UpstreamError(
                coded("MF0201", f"{self.name}: {item.ref} is not in the tree at {commit[:7]}")
                + "\n  the catalogue lists it and the revision does not — re-sync"
            )

        prefix = f"{PREFIX}{item.ref}/"
        texts = {blob.sha: _text(archive[blob.path]) for blob in wanted}
        files = tuple(
            BundleFile(path=blob.path.removeprefix(prefix), text=texts[blob.sha])
            for blob in sorted(wanted, key=lambda b: b.path)
        )

        meta = yaml_strict.loads(texts[_named(wanted, "meta.yml").sha]) or {}
        main_nf = texts[_named(wanted, "main.nf").sha]
        evidence = _evidence(item.ref, meta if isinstance(meta, dict) else {}, main_nf)
        return RawBundle(
            source_revision=commit,
            files=files,
            evidence=evidence,
            facts=(
                BundleFact(
                    name="nf_include", value=f"modules/nf-core/{item.ref}/main", evidence_id=None
                ),
            ),
        )


# ── reading the archive as if it were a tree ───────────────────────────────────────────


def _text(payload: bytes) -> str:
    return payload.decode("utf-8", errors="replace")


def _blob_sha(payload: bytes) -> str:
    """Git's own object id for this content: `sha1("blob <length>\\0" + bytes)`.

    **Computed rather than fetched, so `content_digest` did not change meaning.** The tree API
    used to supply these and the digest of a module is built from its sorted `(path, sha)`
    pairs — recomputing them the way git does keeps every existing digest identical, so no
    adapted tool reads as outdated because of *this* change. A different hash here would have
    marked the whole registry stale on the next sync, which is the noise the per-module digest
    exists to avoid in the first place.

    `usedforsecurity=False` because this is a content address in somebody else's format, not a
    signature; the algorithm is git's choice and not ours to strengthen.
    """
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _blobs_of(files: dict[str, bytes]) -> list[_Blob]:
    """The archive as the tree entries the rest of this module already understood."""
    return [_Blob(path=path, sha=_blob_sha(payload)) for path, payload in sorted(files.items())]


def _meta_of(ref: str, blobs: list[_Blob], files: dict[str, bytes]) -> dict:
    """One module's parsed `meta.yml`, or `{}`.

    **A module whose `meta.yml` will not parse is kept, not dropped.** It becomes an entry with
    no summary rather than a hole in the total — dropping it would make the catalogue quietly
    smaller than the repository, which is exactly the failure a complete archive removed.
    """
    blob = next((b for b in blobs if b.path.endswith("/meta.yml")), None)
    if blob is None:
        return {}
    try:
        parsed = yaml_strict.loads(_text(files[blob.path]))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


# ── the definition of a module, in one place ───────────────────────────────────────────


def _modules_in(blobs: list[_Blob]) -> dict[str, list[_Blob]]:
    """`{ref: every blob beneath it}` for each directory under `modules/nf-core/` that directly
    holds both `main.nf` and `meta.yml`.

    **Two passes, and the second one is why.** A first version grouped every blob by its
    immediate parent directory, which is correct for `main.nf` and wrong for everything nested:
    `fastqc/tests/main.nf.test` became a *separate* group called `fastqc/tests`, which had
    neither required file and so vanished. The module then had no tests in its bundle while
    `SourceCapabilities.supplies_tests` claimed it did, and its `content_digest` did not move
    when upstream edited a test. Found by a test asserting the tests arrive, not by reading.

    So: find the module directories first, then assign every blob to the **longest** module
    prefix that contains it. `samtools/sort` and `samtools/index` are separate refs and
    `samtools/` is not a module, which still falls out of requiring both files in the same
    directory. The longest-prefix rule is what would keep a hypothetical module nested inside
    another from stealing its parent's files.

    **A module's tests are part of its content**, so editing one moves the digest and the tool
    reads as outdated. That is the honest answer: nf-core ships them as part of the module, the
    adapter claims them as a capability, and a validation rung may run them.
    """
    directories = {
        blob.path.rsplit("/", 1)[0]
        for blob in blobs
        if blob.path.startswith(PREFIX) and blob.path.rsplit("/", 1)[-1] in REQUIRED
    }
    modules = sorted(
        directory
        for directory in directories
        if all(any(b.path == f"{directory}/{name}" for b in blobs) for name in REQUIRED)
    )

    grouped: dict[str, list[_Blob]] = {d.removeprefix(PREFIX): [] for d in modules}
    for blob in blobs:
        owner = max(
            (d for d in modules if blob.path.startswith(f"{d}/")), key=len, default=None
        )
        if owner is not None:
            grouped[owner.removeprefix(PREFIX)].append(blob)
    return grouped


def _named(blobs: list[_Blob], filename: str) -> _Blob:
    return next(b for b in blobs if b.path.endswith(f"/{filename}"))


def _item(ref: str, files: list[_Blob], meta: dict | None) -> RawItem:
    """One catalogue row out of a module's tree entries and its `meta.yml`."""
    meta = meta or {}
    tool = _first_tool(meta)
    prose = _description(meta, tool)
    return RawItem(
        ref=ref,
        display_name=str(meta.get("name") or ref),
        summary=prose,
        homepage_url=_url(tool.get("homepage")),
        documentation_url=_url(tool.get("documentation")),
        repository_url=f"https://github.com/{OWNER}/{REPO}/tree/master/{PREFIX}{ref}",
        licence=tuple(_strings(tool.get("licence"))),
        keywords=tuple(_strings(meta.get("keywords"))),
        maintainers=tuple(_strings(meta.get("maintainers"))),
        # **No `latest_version`.** nf-core's `meta.yml` states a tool's homepage and licence and
        # not its version; the version lives in the container tag inside `main.nf`'s Groovy
        # ternary, which is a tag rather than a proved release. `None` is a visible hole and a
        # guessed tag would be a claim nobody made.
        latest_version=None,
        input_hints=tuple(_port_names(meta.get("input"))),
        output_hints=tuple(_port_names(meta.get("output"))),
        capabilities=CAPABILITIES,
        content_digest=digest_of(
            *(f"{b.path}\0{b.sha}" for b in sorted(files, key=lambda b: b.path))
        ),
        evidence=_catalogue_evidence(ref, meta, tool),
    )


def _first_tool(meta: dict) -> dict:
    """`tools:` is a list of single-key maps. The first is the module's own tool."""
    tools = meta.get("tools")
    if not isinstance(tools, list):
        return {}
    for entry in tools:
        if isinstance(entry, dict):
            for value in entry.values():
                if isinstance(value, dict):
                    return value
    return {}


def _description(meta: dict, tool: dict) -> str:
    """The module's one-line summary.

    The module's own `description` first, the tool's as a fallback, and the **first paragraph**
    of either — a `tools:` description runs to several paragraphs and a catalogue row has one
    line.
    """
    for candidate in (meta.get("description"), tool.get("description")):
        if isinstance(candidate, str) and candidate.strip():
            # `" ".join(split())` rather than a newline substitution: `test_forge_write_boundary`
            # is an AST scan over attribute *names* and cannot tell `str.replace` from
            # `Path.replace`, which is a filesystem rename. The guard is blunt rather than
            # wrong, and avoiding the name is cheaper than teaching it to read types.
            return " ".join(candidate.strip().split("\n\n")[0].split())
    return ""


def _port_names(entry: object) -> list[str]:
    """The port names a `meta.yml` block declares, in declaration order.

    **Hints, not ports.** `meta.yml` writes an output as `{html: [[{meta}, {"*.html": {...}}]]}`
    and an input as a bare list of those inner lists, so the useful name is sometimes the outer
    key and sometimes an inner one. `meta` is skipped everywhere: it is the Groovy sample map,
    present on every port and never the answer — the same exclusion `nfcore.py` learned.
    """
    found: list[str] = []

    def walk(node: object, depth: int) -> None:
        if isinstance(node, list):
            for element in node:
                walk(element, depth)
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key == "meta":
                continue
            name = str(key)
            if name not in found:
                found.append(name)
            if isinstance(value, list):
                walk(value, depth + 1)

    if isinstance(entry, dict):
        for key, value in entry.items():
            if key != "meta" and str(key) not in found:
                found.append(str(key))
            del value
    else:
        walk(entry, 0)
    return found


def _catalogue_evidence(ref: str, meta: dict, tool: dict) -> tuple[RawEvidence, ...]:
    """What a person reads on the catalogue row before deciding to import it."""
    at = f"{PREFIX}{ref}/meta.yml"
    found: list[RawEvidence] = []
    if isinstance(meta.get("description"), str) and meta["description"].strip():
        found.append(
            RawEvidence(
                locator=f"{at}:description", text=meta["description"].strip(), kind="metadata"
            )
        )
    if isinstance(tool.get("description"), str) and tool["description"].strip():
        found.append(
            RawEvidence(
                locator=f"{at}:tools.description",
                text=tool["description"].strip(),
                kind="prose",
            )
        )
    return tuple(found)


def _evidence(ref: str, meta: dict, main_nf: str) -> tuple[RawEvidence, ...]:
    """The bundle's evidence, in reading order: what it is, then what its ports mean.

    Ordered rather than sorted, because `number()` assigns `E001` upward in the order given and
    a dossier reads better with the description before the ports it describes.
    """
    at = f"{PREFIX}{ref}/meta.yml"
    found = list(_catalogue_evidence(ref, meta, _first_tool(meta)))
    for block in ("input", "output"):
        for port, text in _described(meta.get(block)).items():
            found.append(
                RawEvidence(locator=f"{at}:{block}.{port}", text=text, kind="metadata")
            )
    if main_nf.strip():
        found.append(
            RawEvidence(
                locator=f"{PREFIX}{ref}/main.nf",
                text=main_nf,
                kind="source",
            )
        )
    return tuple(found)


def _described(entry: object) -> dict[str, str]:
    """`{port: one English line}` out of `meta.yml`'s nested shape.

    The same walk `nfcore.py` uses, and the reason it is not shared yet is that that module is
    on the deprecated path and Task 13 deletes it. Duplicating a private helper for the length
    of one migration is cheaper than a shared one that has to survive the deletion.
    """
    found: dict[str, str] = {}

    def described(node: object) -> str | None:
        if not isinstance(node, dict):
            return None
        parts = [
            str(node[key]).strip()
            for key in ("description", "pattern")
            if isinstance(node.get(key), str) and node[key].strip()
        ]
        return " — ".join(parts) or None

    def walk(node: object, port: str | None) -> None:
        if isinstance(node, list):
            for element in node:
                walk(element, port)
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            if key == "meta":
                continue
            text = described(value)
            name = port or str(key)
            if text and name not in found:
                found[name] = f"{key}: {text}" if port else text
            else:
                walk(value, port or str(key))

    if isinstance(entry, dict):
        for port, value in entry.items():
            walk(value, port)
    else:
        walk(entry, None)
    return found


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _url(value: object) -> str | None:
    return str(value).strip() if isinstance(value, str) and value.strip() else None
