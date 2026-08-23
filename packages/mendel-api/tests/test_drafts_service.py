"""The rule, without the storage. **Runs in CI, where the route tests cannot.**

`test_drafts.py` needs Postgres and skips without it, following `test_visits.py`. The rule most
worth defending is that `keep` refuses an illegal graph, so it is tested here with `_load` and
`_output_root` monkeypatched — a rule only a developer machine can check is a rule CI cannot
defend.
"""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.services import drafts

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
GENOME = "nf-core/star/genomegenerate@1.11.0"


def _graph(nodes, edges=()):
    return DraftGraph.model_validate(
        {
            "nodes": [{"id": i, "contract_id": c} for i, c in nodes],
            "edges": [
                {"from_node": a, "from_port": b, "to_node": c, "to_port": d}
                for a, b, c, d in edges
            ],
        }
    )


def test_keep_refuses_an_illegal_graph(monkeypatch):
    """An unsorted BAM into featureCounts. The message carries the code, so
    `mendel explain MD0504` expands it exactly as it would from the CLI."""
    graph = _graph(
        [("align", STAR), ("counts", COUNTS)],
        [("align", "bam", "counts", "bam")],
    )
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    with pytest.raises(ValueError, match="MD0504"):
        drafts.keep("whatever")


def test_the_refusal_says_how_many_problems_there_are(monkeypatch):
    """One answer, but not a lie about the size of the problem. `validate` is where you go to
    see them all, and the refusal should tell you there are more."""
    graph = _graph(
        [("align", STAR), ("counts", COUNTS)],
        [("align", "bam", "counts", "bam"), ("align", "nope", "counts", "annotation")],
    )
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    with pytest.raises(ValueError, match="2 illegal finding"):
        drafts.keep("whatever")


def test_keep_allows_a_graph_with_only_unmet_ports(monkeypatch, tmp_path):
    """`unmet` is not `illegal`. A half-drawn graph is a legal thing to hold; the emitted
    Nextflow simply has an input nothing fills, which the gates catch where it costs something.
    """
    graph = _graph([("counts", COUNTS)])
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)
    written = drafts.keep("whatever")
    assert written.exists()
    assert written.name == "pipeline.yml"


def test_a_kept_draft_records_who_chose_each_step(monkeypatch, tmp_path):
    """Task 5's split, reaching the artifact. A model-assembled pipeline must not read as a
    hand-drawn one."""
    import yaml

    graph = _graph(
        [("index", GENOME), ("align", STAR), ("sort", SORT), ("counts", COUNTS)],
        [
            ("index", "index", "align", "index"),
            ("align", "bam", "sort", "bam"),
            ("sort", "bam", "counts", "bam"),
        ],
    )
    monkeypatch.setattr(drafts, "_load", lambda draft_id: graph)
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)

    written = drafts.keep("by-a-person")
    text = yaml.safe_load(written.read_text())
    producers = [d for d in text["decisions"] if d["kind"] == "producer"]
    assert producers
    assert all(d["human_override"] for d in producers)
    assert all(not d["model_override"] for d in producers)

    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path / "by-model")
    written = drafts.keep("by-a-model", by="claude-opus-5")
    text = yaml.safe_load(written.read_text())
    producers = [d for d in text["decisions"] if d["kind"] == "producer"]
    assert all(d["model_override"] for d in producers)
    assert all(d["model_override_by"] == "claude-opus-5" for d in producers)
    assert all(not d["human_override"] for d in producers)
