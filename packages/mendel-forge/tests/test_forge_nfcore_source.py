"""`NfCoreSource` against a local git repository: no network in tests."""

import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mendel_forge.nfcore.source import NfCoreSource
from mendel_forge.source import SourceUnavailable

FIXTURES = Path(__file__).parent / "fixtures" / "nf-core"


def _git(repo: Path, *args: str, when: str | None = None) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    if when:
        env |= {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, env=env,
                          capture_output=True, text=True).stdout.strip()


def _add(repo: Path, module: str, when: str) -> None:
    shutil.copytree(FIXTURES / module, repo / "modules" / "nf-core" / module)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"add {module}", when=when)


@pytest.fixture
def upstream(tmp_path) -> Path:
    repo = tmp_path / "upstream"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "uploadpack.allowFilter", "true")
    _add(repo, "fastqc", "2026-01-01T00:00:00+00:00")
    _add(repo, "star/align", "2026-02-01T00:00:00+00:00")
    return repo


def test_sync_clones_and_reports_the_commit(upstream, tmp_path):
    snapshot = NfCoreSource(upstream.as_uri()).sync(tmp_path / "cache")
    assert snapshot.source == "nf-core"
    assert snapshot.commit == _git(upstream, "rev-parse", "HEAD")


def test_modules_lists_both_with_their_last_change(upstream, tmp_path):
    source = NfCoreSource(upstream.as_uri())
    modules = {m.path: m for m in source.modules(source.sync(tmp_path / "cache"))}
    assert sorted(modules) == ["fastqc", "star/align"]
    assert modules["star/align"].upstream_changed == datetime(2026, 2, 1, tzinfo=UTC)
    assert modules["fastqc"].upstream_changed == datetime(2026, 1, 1, tzinfo=UTC)
    assert modules["star/align"].tool_version == "2.7.11b"


def test_a_second_sync_sees_a_new_module(upstream, tmp_path):
    source = NfCoreSource(upstream.as_uri())
    source.sync(tmp_path / "cache")
    _add(upstream, "bwa/mem", "2026-03-01T00:00:00+00:00")
    snapshot = source.sync(tmp_path / "cache")
    assert snapshot.commit == _git(upstream, "rev-parse", "HEAD")
    assert "bwa/mem" in {m.path for m in source.modules(snapshot)}


def test_unreachable_url_raises_SourceUnavailable(tmp_path):
    with pytest.raises(SourceUnavailable):
        NfCoreSource((tmp_path / "nonexistent").as_uri()).sync(tmp_path / "cache")
