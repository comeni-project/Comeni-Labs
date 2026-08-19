from pathlib import Path

import pytest
from mendel_forge import ops

ROOT = Path(__file__).resolve().parents[3]


def _ctx(tmp_path):
    return {
        "registry_root": ROOT / "registry",
        "source_root": ROOT / "vendor",
        "workspace_root": tmp_path,
    }


def test_sources_lists_the_registered_ones():
    assert "nf-core" in ops.sources_().names


def test_draft_ingests_and_saves(tmp_path):
    result = ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    assert result.name == "fastqc"
    assert result.holes, "a fresh nf-core draft has semantic holes"
    assert (tmp_path / "fastqc" / "draft.json").exists()


def test_show_returns_holes_with_their_candidates(tmp_path):
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    shown = ops.show(ops.ShowRequest(name="fastqc", **_ctx(tmp_path)))
    hole = next(h for h in shown.holes if h.subject.endswith("type_id"))
    assert hole.candidates


def test_fill_persists(tmp_path):
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    ops.fill(
        ops.FillRequest(
            name="fastqc",
            field="roles",
            value=["qc_per_sample"],
            by="rafael",
            why="it QCs a sample",
            workspace_root=tmp_path,
        )
    )
    shown = ops.show(ops.ShowRequest(name="fastqc", **_ctx(tmp_path)))
    assert "roles" not in {h.subject for h in shown.holes}
    assert shown.filled["roles"].value == ["qc_per_sample"]


def test_every_result_is_json_serialisable(tmp_path):
    """The whole point of the layer: the CLI's --json and the HTTP body are one payload."""
    result = ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    assert result.model_dump_json()


def test_a_refusal_is_raised_not_returned(tmp_path):
    """Both transports need one place to turn a refusal into an exit code or a 4xx, and a
    result object carrying a maybe-error means both would have to remember to check."""
    with pytest.raises(ValueError, match="MF0001"):
        ops.draft(ops.DraftRequest(ref="nonesuch:x", name="x", **_ctx(tmp_path)))


def test_the_default_filler_declines_every_hole():
    from mendel_forge.observe import Observation
    from mendel_forge.ports import NoFiller
    from mendel_forge.scaffold import Hole

    hole = Hole(subject="roles", what="w", why_open="o")
    assert NoFiller().fill(hole, Observation(source="s", ref_id="r")) is None


def test_drafting_over_an_existing_draft_is_refused(tmp_path):
    """A draft is a person's judgement, one field at a time, each with a reason.

    `Workspace.save` does `mkdir(exist_ok=True)` then `write_text`, so before MF0010 this
    replaced every answer, proposal and decision on the draft and said nothing. Survivable in
    a CLI a person types deliberately; one careless click in a form.
    """
    request = ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path))
    ops.draft(request)  # the half that must pass: the first one works

    with pytest.raises(ValueError, match="MF0010"):
        ops.draft(request)


def test_a_second_draft_under_another_name_is_fine(tmp_path):
    """The refusal is about the NAME, not the tool: two drafts of one tool at two versions is
    exactly what a version bump looks like."""
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    second = ops.draft(
        ops.DraftRequest(
            ref="nf-core:fastqc", name="fastqc-next", version="0.13.0", **_ctx(tmp_path)
        )
    )
    assert second.name == "fastqc-next"


def test_the_refusal_names_the_drafts_that_exist(tmp_path):
    """The same list `MF0008` prints when a draft is missing — one answer to *what is here*."""
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    with pytest.raises(ValueError, match="fastqc"):
        ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
