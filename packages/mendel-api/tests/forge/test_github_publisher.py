"""The publisher against a local bare repository and a fake GitHub: nothing live."""

import json
import subprocess

import httpx
import pytest
from mendel_api.services import github_publisher
from mendel_api.services.github_publisher import GitHubPublisher
from mendel_api.settings import settings
from mendel_forge.publishing import Change, PublishUnavailable

TOKEN = "ghp_guard_publisher_0123"


def _git(where, *args):
    return subprocess.run(["git", *args], cwd=where, check=True, text=True,
                          capture_output=True).stdout.strip()


@pytest.fixture
def remote(tmp_path):
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _git(bare, "init", "--quiet", "--bare", "--initial-branch=main")
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "--quiet", str(bare), str(seed))
    (seed / "registry.yml").write_text("name: x\n")
    _git(seed, "add", ".")
    _git(seed, "-c", "user.name=x", "-c", "user.email=x@x", "commit", "--quiet", "-m", "first")
    _git(seed, "push", "--quiet", "origin", "HEAD:main")
    return bare


def _publisher(tmp_path, remote, handler=None) -> GitHubPublisher:
    handler = handler or (lambda request: httpx.Response(200, json={}))
    return GitHubPublisher("x/y", TOKEN, tmp_path / "cache", remote=str(remote),
                           client=httpx.Client(transport=httpx.MockTransport(handler)))


CHANGE = Change(branch="forge/star-1", title="Add star", body="the record", author="rafael")


def test_checkout_is_a_fresh_main(tmp_path, remote):
    publisher = _publisher(tmp_path, remote)
    root = publisher.checkout()
    (root / "stray.txt").write_text("left behind")
    (root / "registry.yml").write_text("edited")
    root = publisher.checkout()
    assert not (root / "stray.txt").exists()
    assert (root / "registry.yml").read_text() == "name: x\n"


def test_opening_pushes_a_branch_and_opens_a_pull_request(tmp_path, remote):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(201, json={"number": 7, "html_url": "https://github.com/x/y/pull/7"})

    publisher = _publisher(tmp_path, remote, handler)
    (publisher.checkout() / "new.yml").write_text("a: 1\n")
    opened = publisher.open_pull_request(CHANGE)
    assert opened.number == 7 and opened.branch == "forge/star-1"
    assert seen[0]["head"] == "forge/star-1" and seen[0]["base"] == "main"
    assert seen[0]["body"] == "the record"
    assert _git(remote, "show", "forge/star-1:new.yml") == "a: 1"


def test_the_token_is_not_in_the_clone_or_any_command(tmp_path, remote, monkeypatch):
    commands = []
    real = subprocess.run

    def recording(command, **kw):
        commands.append(command)
        return real(command, **kw)

    monkeypatch.setattr(github_publisher.subprocess, "run", recording)
    publisher = _publisher(tmp_path, remote)
    root = publisher.checkout()
    assert commands and not any(TOKEN in " ".join(c) for c in commands)
    assert TOKEN not in (root / ".git/config").read_text()
    assert TOKEN not in (tmp_path / "cache/askpass.sh").read_text()


def _pull(runs):
    def handler(request):
        if request.url.path.endswith("/check-runs"):
            return httpx.Response(200, json={"check_runs": runs})
        return httpx.Response(200, json={"state": "open", "merged": False,
                                         "head": {"sha": "abc"}})
    return handler


@pytest.mark.parametrize("runs,checks", [
    ([], "pending"),
    ([{"name": "ci", "status": "in_progress", "conclusion": None}], "pending"),
    ([{"name": "ci", "status": "completed", "conclusion": "failure"}], "red"),
    ([{"name": "a", "status": "completed", "conclusion": "success"},
      {"name": "b", "status": "in_progress", "conclusion": None}], "pending"),
    ([{"name": "ci", "status": "completed", "conclusion": "success"}], "green"),
])
def test_state_reads_the_checks(tmp_path, remote, runs, checks):
    state = _publisher(tmp_path, remote, _pull(runs)).state(7)
    assert state.checks == checks and state.state == "open" and state.head == "abc"


def test_merging_names_the_head_it_checked(tmp_path, remote):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"merged": True})

    _publisher(tmp_path, remote, handler).merge(7, "abc")
    assert seen[0].method == "PUT" and json.loads(seen[0].content)["sha"] == "abc"
    assert seen[0].headers["authorization"] == f"Bearer {TOKEN}"


def test_a_refusal_never_says_the_token(tmp_path, remote):
    handler = lambda request: httpx.Response(401, text=f"bad credentials {TOKEN}")  # noqa: E731
    with pytest.raises(PublishUnavailable) as caught:
        _publisher(tmp_path, remote, handler).merge(7, "abc")
    assert TOKEN not in str(caught.value) and "401" in str(caught.value)


def test_an_unreachable_github_never_says_the_token(tmp_path, remote):
    def handler(request):
        raise httpx.ConnectError(request.headers["authorization"])

    with pytest.raises(PublishUnavailable) as caught:
        _publisher(tmp_path, remote, handler).state(7)
    assert TOKEN not in str(caught.value)


def test_no_token_means_no_publisher(monkeypatch):
    monkeypatch.delenv("COMENI_FORGE_GITHUB_TOKEN", raising=False)
    assert github_publisher.publisher() is None


def test_a_token_means_a_publisher(monkeypatch, tmp_path):
    monkeypatch.setenv("COMENI_FORGE_GITHUB_TOKEN", TOKEN)
    monkeypatch.setattr(settings, "forge_cache", tmp_path)
    assert isinstance(github_publisher.publisher(), GitHubPublisher)
