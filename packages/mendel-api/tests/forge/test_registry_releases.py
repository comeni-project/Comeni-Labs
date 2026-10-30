"""Following releases: only what loads is used, and nothing else moves. A fake GitHub."""

import io
import shutil
import tarfile

import httpx
import pytest
import yaml
from mendel_api.services import registry, registry_releases
from mendel_api.services.github_releases import GitHubReleases
from mendel_api.settings import active_registry, settings
from mendel_compiler.locate import locate
from mendel_forge.releases import Fragment as F
from mendel_forge.releases import Release, ReleaseUnavailable, next_version, notes_from
from support.paths import REGISTRY


class FakeSource:
    def __init__(self, *tags, broken=()):
        self.tags, self.broken, self.down = list(tags), set(broken), False
        self.fetched = []

    def releases(self):
        if self.down:
            raise ReleaseUnavailable("GitHub could not be reached: ConnectError")
        return [Release(tag=t) for t in self.tags]

    def download(self, tag, into):
        self.fetched.append(tag)
        shutil.copytree(REGISTRY, into, ignore=shutil.ignore_patterns(".git"))
        if tag in self.broken:
            (into / "registry.yml").write_text("requires_format: 999\n")
        return "a" * 40


@pytest.fixture
def follow(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "registries_root", tmp_path / "registries")
    monkeypatch.setattr(registry_releases, "_wanted", lambda: "latest")

    def run(source, wanted="latest"):
        monkeypatch.setattr(registry_releases, "source", lambda: source)
        monkeypatch.setattr(registry_releases, "_wanted", lambda: wanted)
        return registry_releases.follow()

    yield run
    for path in (tmp_path / "registries").rglob("*"):
        if path.is_dir():
            path.chmod(0o755)


def test_latest_chooses_the_newest(follow):
    assert follow(FakeSource("v0.2.0", "v0.10.0", "v0.9.0")) == "v0.10.0"
    assert active_registry().parent.name == "v0.10.0"


def test_a_release_that_does_not_load_is_skipped(follow):
    source = FakeSource("v0.2.0", "v0.3.0", broken={"v0.3.0"})
    assert follow(source) == "v0.2.0"
    found = registry_releases.status()
    assert "v0.3.0" in found.refused and found.problem


def test_offline_keeps_the_newest_it_has(follow):
    assert follow(FakeSource("v0.2.0")) == "v0.2.0"
    source = FakeSource("v0.2.0")
    source.down = True
    assert follow(source) == "v0.2.0"
    assert "could not be reached" in registry_releases.status().problem


def test_a_pin_never_moves(follow):
    source = FakeSource("v0.2.0", "v0.3.0")
    assert follow(source, wanted="v0.2.0") == "v0.2.0"
    assert follow(source) == "v0.3.0", "latest moves"
    assert follow(source, wanted="v0.2.0") == "v0.2.0"
    assert source.fetched.count("v0.2.0") == 1, "fetched once"


def test_a_pin_that_does_not_exist_changes_nothing_and_says_so(follow):
    assert follow(FakeSource("v0.2.0")) == "v0.2.0"
    assert follow(FakeSource("v0.2.0"), wanted="v9.9.9") == "v0.2.0"
    assert "v9.9.9" in registry_releases.status().problem


def test_no_release_runs_the_configured_root(follow):
    assert follow(FakeSource()) is None
    assert active_registry() == settings.registry_root


def test_no_registries_root_changes_nothing(monkeypatch):
    monkeypatch.setattr(settings, "registries_root", None)
    assert active_registry() == settings.registry_root and registry_releases.follow() is None


def test_a_release_is_read_only(follow):
    follow(FakeSource("v0.2.0"))
    contract = active_registry() / "tools/nf-core/fastqc/contract.yml"
    assert not contract.stat().st_mode & 0o222


def test_the_stack_follows_the_switch(follow):
    follow(FakeSource("v0.2.0"))
    assert registry.stack().paths == [active_registry()]
    assert registry.registry_label() == "v0.2.0"


def test_the_lockfile_names_the_release(follow):
    follow(FakeSource("v0.2.0"))
    found = locate(active_registry())
    assert found.release == "v0.2.0" and found.commit == "a" * 40
    assert found.source.startswith("https://github.com/") and found.dirty is False


def test_a_layer_with_no_release_says_nothing_of_one():
    assert locate(REGISTRY).release is None


def _tarball(top: str, members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(f"{top}/{name}" if not name.startswith("/") else name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _github(tar: bytes, sha: str = "abcdef1234567890") -> GitHubReleases:
    def handler(request):
        if request.url.path.endswith("/commits/v1"):
            return httpx.Response(200, json={"sha": sha})
        return httpx.Response(200, content=tar)
    return GitHubReleases("x/y", httpx.Client(transport=httpx.MockTransport(handler)))


def test_a_tarball_unpacks_without_its_top_folder(tmp_path):
    tar = _tarball("x-y-abcdef1", {"registry.yml": b"name: x\n", "tools/a.yml": b"a: 1\n"})
    assert _github(tar).download("v1", tmp_path / "out") == "abcdef1234567890"
    assert (tmp_path / "out/registry.yml").is_file() and (tmp_path / "out/tools/a.yml").is_file()


def test_a_tarball_of_another_commit_is_refused(tmp_path):
    with pytest.raises(ReleaseUnavailable, match="not commit"):
        _github(_tarball("x-y-0000000", {"a": b"1"})).download("v1", tmp_path / "out")


@pytest.mark.parametrize("name", ["../escape.txt", "a/../../escape.txt"])
def test_a_tarball_that_climbs_out_is_refused(tmp_path, name):
    with pytest.raises(ReleaseUnavailable, match="holds"):
        _github(_tarball("x-y-abcdef1", {name: b"1"})).download("v1", tmp_path / "deep" / "out")
    assert not list(tmp_path.rglob("escape.txt"))


def test_the_next_version_and_notes():
    assert next_version("v0.4.0") == "v0.5.0" and next_version(None) == "v0.1.0"
    assert notes_from([F(path="b", text="- b\n"), F(path="a", text="- a\n")]) == "- a\n- b"


def test_a_failed_fetch_leaves_no_folder_behind(follow):
    class Failing(FakeSource):
        def download(self, tag, into):
            into.mkdir(parents=True)
            raise ReleaseUnavailable("GitHub refused /tarball/v0.2.0: 502")

    assert follow(Failing("v0.2.0")) is None
    assert "502" in registry_releases.status().refused["v0.2.0"]
    assert not (settings.registries_root / "v0.2.0").exists()


def test_settings_says_what_is_in_use(follow):
    follow(FakeSource("v0.2.0"))
    assert "v0.2.0" in registry_releases.describe()
    yaml.safe_load((active_registry().parent / "release.yml").read_text())
