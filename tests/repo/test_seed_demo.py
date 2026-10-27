"""The demo seeder projects goals, refreshes drafts and guards its fake-run writes."""

import argparse
import sys
from types import SimpleNamespace

import pytest
from support.paths import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import seed_demo  # noqa: E402


def test_the_demo_graph_uses_the_example_profile():
    built = {
        "steps": [
            {"id": "index", "contract_id": "nf-core/star/genomegenerate@2.7.11b"},
            {"id": "align", "contract_id": "nf-core/star/align@2.7.11b"},
        ],
        "layout": {
            "wires": [
                {
                    "from_node": "index",
                    "from_port": "index",
                    "to_node": "align",
                    "to_port": "index",
                }
            ]
        },
    }
    goal = seed_demo.load_goal(ROOT / "examples" / "rnaseq.yml")

    graph = seed_demo.graph_of(built, goal)

    assert graph["nodes"] == [
        {"id": "index", "contract_id": "nf-core/star/genomegenerate@2.7.11b", "params": []},
        {"id": "align", "contract_id": "nf-core/star/align@2.7.11b", "params": []},
    ]
    assert graph["edges"] == [
        {
            "from_node": "index",
            "from_port": "index",
            "to_node": "align",
            "to_port": "index",
        }
    ]
    assert graph["profile"]["read_length"] == 150
    assert graph["profile"]["strandedness"] == "reverse"


def test_seeding_refreshes_a_named_demo_draft():
    class FakeApi:
        def __init__(self, base, timeout):
            self.calls = []

        def request(self, method, path, body=None):
            self.calls.append((method, path, body))
            if path == "/pipeline/drafts":
                return {"drafts": [{"id": "abc123", "name": "RNA-seq demo"}]}
            if path == "/pipeline":
                return {"steps": [], "layout": {"wires": []}}
            if path == "/pipeline/drafts/abc123":
                return {"id": "abc123"}
            if path == "/pipeline/drafts/abc123/keep":
                return {"path": "/app/drafts/abc123/pipeline.yml"}
            raise AssertionError((method, path, body))

    old = seed_demo.Api
    seed_demo.Api = FakeApi
    try:
        result = seed_demo.seed(
            argparse.Namespace(
                api="http://api/api",
                web="http://web",
                starter=ROOT / "examples" / "rnaseq.yml",
                name="RNA-seq demo",
                fresh=False,
                keep=True,
                timeout=1,
            )
        )
    finally:
        seed_demo.Api = old

    assert result["action"] == "refreshed"
    assert result["draft_id"] == "abc123"
    assert result["builder_url"] == "http://web/build?draft=abc123"
    assert result["artifact"] == "/app/drafts/abc123/pipeline.yml"


def test_fake_run_seeding_is_idempotent_for_a_named_run():
    class ExistingApi:
        def request(self, method, path):
            assert (method, path) == ("GET", "/runs?limit=200")
            return {"runs": [{"name": "RNA-seq demo"}]}

        def upload(self, bundle, name):
            raise AssertionError("an existing demo run must not upload another artifact")

    assert seed_demo.seed_fake_runs(ExistingApi(), "draft-1", "RNA-seq demo", []) == []


def test_fake_run_seeding_reports_a_failed_database_write(monkeypatch):
    class EmptyApi:
        def request(self, method, path):
            assert (method, path) == ("GET", "/runs?limit=200")
            return {"runs": []}

        def upload(self, bundle, name):
            assert bundle == b"bundle"
            assert name == "RNA-seq demo"
            return {"artifact_id": "artifact-1"}

    captured = {}

    def failed_run(command, **kwargs):
        captured["command"] = command
        captured["input"] = kwargs["input"].decode()
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(seed_demo, "bundle_of", lambda draft_id: b"bundle")
    monkeypatch.setattr(seed_demo.subprocess, "run", failed_run)

    with pytest.raises(RuntimeError, match="could not seed fake Wiener runs"):
        seed_demo.seed_fake_runs(
            EmptyApi(),
            "draft-1",
            "RNA-seq demo",
            [{"id": "align", "process": "STAR_ALIGN"}],
        )

    assert captured["command"][:4] == ["docker", "compose", "exec", "-T"]
    assert captured["input"].count("INSERT INTO run (") == 4
    assert "INSERT INTO run_event" in captured["input"]
    assert "INSERT INTO run_task" in captured["input"]
