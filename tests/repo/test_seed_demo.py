import argparse
import sys

from support.paths import ROOT

sys.path.insert(0, str(ROOT / "tools"))
import seed_demo  # noqa: E402


def test_the_demo_graph_uses_the_example_profile():
    built = {
        "steps": [
            {"id": "index", "contract_id": "nf-core/star/genomegenerate@1.11.0"},
            {"id": "align", "contract_id": "nf-core/star/align@1.11.0"},
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
    goal = seed_demo.load_goal(ROOT / "examples" / "rnaseq-goal.yml")

    graph = seed_demo.graph_of(built, goal)

    assert graph["nodes"] == [
        {"id": "index", "contract_id": "nf-core/star/genomegenerate@1.11.0", "params": []},
        {"id": "align", "contract_id": "nf-core/star/align@1.11.0", "params": []},
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
                goal=ROOT / "examples" / "rnaseq-goal.yml",
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
