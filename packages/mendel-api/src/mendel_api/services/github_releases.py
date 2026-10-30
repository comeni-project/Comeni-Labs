"""`comeni-registry`'s public release data, read without a token (forge MVP 6, spec §3)."""

import io
import tarfile
from pathlib import Path, PurePosixPath

import httpx
from mendel_forge.publishing import GITHUB_API, checks_of
from mendel_forge.releases import (
    Fragment,
    Release,
    ReleaseUnavailable,
    Unreleased,
    key,
)

from mendel_api.settings import settings

FRAGMENTS = "changelog.d/"


class GitHubReleases:
    def __init__(self, repo: str, client: httpx.Client | None = None) -> None:
        self.repo = repo
        self._client = client or httpx.Client(timeout=120.0, follow_redirects=True)
        self._client.base_url = GITHUB_API

    def _get(self, path: str, **kw) -> httpx.Response:
        try:
            answer = self._client.get(f"/repos/{self.repo}{path}", **kw)
        except httpx.HTTPError as error:
            raise ReleaseUnavailable(f"GitHub could not be reached: {type(error).__name__}") \
                from None
        if answer.status_code >= 400:
            raise ReleaseUnavailable(f"GitHub refused {path}: {answer.status_code}")
        return answer

    def releases(self) -> list[Release]:
        found = self._get("/releases", params={"per_page": 100}).json()
        return [Release(tag=r["tag_name"], notes=r.get("body") or "",
                        published_at=r.get("published_at"))
                for r in found if not r.get("draft") and not r.get("prerelease")]

    def download(self, tag: str, into: Path) -> str:
        commit = self._get(f"/commits/{tag}").json()["sha"]
        data = self._get(f"/tarball/{tag}").content
        _unpack(data, into, commit)
        return commit

    def unreleased(self) -> Unreleased:
        tags = [t["name"] for t in self._get("/tags", params={"per_page": 100}).json()]
        versioned = [t for t in tags if key(t) is not None]
        last = max(versioned, key=key) if versioned else None
        if last is None:
            head = self._get("/commits/main").json()["sha"]
            ahead, paths = 1, self._all_fragments()
        else:
            compared = self._get(f"/compare/{last}...main").json()
            ahead = compared["ahead_by"]
            head = compared["commits"][-1]["sha"] if compared["commits"] else ""
            paths = [f["filename"] for f in compared["files"]
                     if f["status"] == "added" and _is_fragment(f["filename"])]
        fragments = [Fragment(path=p, text=self._raw(p)) for p in sorted(paths)]
        checks, says = "pending", "nothing to check"
        if head:
            runs = self._get(f"/commits/{head}/check-runs", params={"per_page": 100})
            checks, says = checks_of(runs.json()["check_runs"])
        return Unreleased(last=last, commit=head, ahead=ahead, checks=checks, says=says,
                          fragments=fragments)

    def _all_fragments(self) -> list[str]:
        try:
            found = self._get(f"/contents/{FRAGMENTS.rstrip('/')}").json()
        except ReleaseUnavailable:
            return []
        return [f["path"] for f in found if _is_fragment(f["path"])]

    def _raw(self, path: str) -> str:
        return self._get(f"/contents/{path}", params={"ref": "main"},
                         headers={"Accept": "application/vnd.github.raw+json"}).text


def _is_fragment(path: str) -> bool:
    return path.startswith(FRAGMENTS) and path.endswith(".md") and \
        not path.endswith("README.md")


def _unpack(data: bytes, into: Path, commit: str) -> None:
    """GitHub's tarball has one top folder, `<owner>-<repo>-<short sha>`, which is stripped and
    must name `commit`. Anything that would land outside `into` is refused before writing."""
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            _extract(archive, into, commit)
    except tarfile.TarError as error:
        raise ReleaseUnavailable(f"the release archive could not be read: {error}") from None


def _extract(archive: tarfile.TarFile, into: Path, commit: str) -> None:
    members = archive.getmembers()
    top = PurePosixPath(members[0].name).parts[0] if members else ""
    if not top or not commit.startswith(top.rsplit("-", 1)[-1]):
        raise ReleaseUnavailable(f"the release archive is not commit {commit[:12]}")
    for member in members:
        parts = PurePosixPath(member.name).parts
        if ".." in parts or member.name.startswith("/") or member.issym() or member.islnk():
            raise ReleaseUnavailable(f"the release archive holds {member.name!r}")
        if parts[0] != top:
            raise ReleaseUnavailable("the release archive has more than one top folder")
    into.mkdir(parents=True)
    for member in members:
        target = into.joinpath(*PurePosixPath(member.name).parts[1:])
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())


def source() -> GitHubReleases:
    return GitHubReleases(settings.registry_repo)


