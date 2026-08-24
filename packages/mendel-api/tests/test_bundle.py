"""The courier's Mendel half: a kept pipeline, as a zip somebody else can run — A179.

**No database, on purpose.** `test_drafts_service.py` records the reason: a rule only a
developer machine can check is a rule CI cannot defend. These monkeypatch the same two seams,
keep a real pipeline into a `tmp_path`, and read the archive back.
"""

import io
import zipfile

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.services import bundle, drafts

STAR = "nf-core/star/align@1.11.0"
SORT = "nf-core/samtools/sort@1.21.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
GENOME = "nf-core/star/genomegenerate@1.11.0"

SPINE = (
    [("index", GENOME), ("align", STAR), ("sort", SORT), ("counts", COUNTS)],
    [
        ("index", "index", "align", "index"),
        ("align", "bam", "sort", "bam"),
        ("sort", "bam", "counts", "bam"),
    ],
)


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


@pytest.fixture
def kept(monkeypatch, tmp_path):
    """A real kept pipeline under `tmp_path/a-draft`, with both services pointed at it."""
    monkeypatch.setattr(drafts, "_load", lambda draft_id: _graph(*SPINE))
    monkeypatch.setattr(drafts, "_output_root", lambda: tmp_path)
    monkeypatch.setattr(bundle, "_directory", lambda draft_id: tmp_path / draft_id)
    drafts.keep("a-draft")
    return "a-draft"


def _names(archive: bytes) -> set[str]:
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        return set(zf.namelist())


def test_the_bundle_is_a_runnable_pipeline_directory(kept):
    """§12's diagram names four things — `pipeline.yml`, `main.nf`, the config and the modules —
    and all four have to be there or what arrives at Wiener is not a pipeline."""
    names = _names(bundle.of(kept))
    assert {"pipeline.yml", "main.nf", "nextflow.config"} <= names
    assert any(name.startswith("modules/") for name in names)


def test_the_nextflow_is_emitted_rather_than_copied(kept, tmp_path):
    """**A gate is what writes `main.nf` into the draft directory**, so copying would make the
    bundle depend on whether somebody had gated — and an un-gated draft would ship a directory
    with no workflow in it. Nothing has gated here, and the workflow is present."""
    assert not (tmp_path / kept / "main.nf").exists()
    with zipfile.ZipFile(io.BytesIO(bundle.of(kept))) as zf:
        assert "workflow" in zf.read("main.nf").decode()


def test_only_the_pipeline_travels(kept, tmp_path):
    """**An allowlist, not a sweep** — the same argument `declared_entries()` makes about a
    layer. A draft directory accumulates what a run leaves behind, and none of it is the
    pipeline."""
    (tmp_path / kept / ".nextflow.log").write_text("noise")
    (tmp_path / kept / "work").mkdir()
    (tmp_path / kept / "work" / "scratch.txt").write_text("more noise")

    names = _names(bundle.of(kept))
    assert not any(name.startswith("work/") for name in names)
    assert ".nextflow.log" not in names


def test_the_same_pipeline_is_the_same_archive(kept):
    """Wiener content-addresses what it is handed, so two submissions of one pipeline must
    agree.

    **Asserted on the timestamps, not on equal bytes.** Two archives written in the same second
    are equal whether or not anybody thought about it, so `of(x) == of(x)` passes on the code
    that has this bug — it only fails if the test happens to straddle a second boundary. The
    fixed epoch is the actual claim.
    """
    assert bundle.of(kept) == bundle.of(kept)
    with zipfile.ZipFile(io.BytesIO(bundle.of(kept))) as zf:
        stamps = {info.date_time for info in zf.infolist()}
    assert stamps == {(1980, 1, 1, 0, 0, 0)}


def test_nothing_kept_is_not_an_empty_bundle(monkeypatch, tmp_path):
    """`KeyError`, which the route turns into a 404. An empty archive would reach Wiener, store
    cleanly, and fail at launch with no explanation."""
    monkeypatch.setattr(bundle, "_directory", lambda draft_id: tmp_path / draft_id)
    with pytest.raises(KeyError):
        bundle.of("never-kept")
