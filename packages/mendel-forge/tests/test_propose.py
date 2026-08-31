"""Declining a hole: nothing declared fits, and here is what would.

`Scaffold.propose` already existed for the model path (`fill_with_model` sets `proposed_id`).
This is the human's door to the same act — invariant 7's escape hatch, and
`notes/specs/2026-08-17-vocabulary-proposals.md` is why it exists at all.
"""

from pathlib import Path

import pytest
from mendel_forge import ops

ROOT = Path(__file__).resolve().parents[3]


def _ctx(tmp_path):
    """The workspace triple every forge test uses — copied from `test_ops.py:9`, which is
    the file's own idiom. `DraftRequest.version` defaults to `"0.0.0"` and nothing here
    depends on it."""
    return {
        "registry_root": ROOT / "registry",
        "source_root": ROOT / "registry",
        "workspace_root": tmp_path,
    }


def _drafted(tmp_path):
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))


def test_a_proposal_leaves_the_hole_open(tmp_path):
    """**The assertion this file exists for.** A proposal is not a fill: `is_complete()`
    stays false and `land` still refuses, because a contract citing an undeclared type is
    the load-time refusal invariant 7 already makes."""
    _drafted(tmp_path)

    got = ops.propose(ops.ProposeRequest(
        name="fastqc", field="produces[0].type_id",
        id="qc.report.html", description="an HTML QC report for one sample",
        why="nothing declared distinguishes the HTML report from the zip",
        by="rafael", workspace_root=tmp_path,
    ))

    assert "produces[0].type_id" in got.remaining, "a proposed field is still open"


def test_it_is_recorded_on_the_draft_with_its_author_and_reason(tmp_path):
    _drafted(tmp_path)
    ops.propose(ops.ProposeRequest(
        name="fastqc", field="produces[0].type_id", id="qc.report.html",
        description="an HTML QC report", why="nothing declared fits", by="rafael",
        workspace_root=tmp_path,
    ))

    from mendel_forge.workspace import Workspace

    draft = Workspace(root=tmp_path).load("fastqc")
    proposal = draft.scaffold.proposed["produces[0].type_id"]
    assert proposal.id == "qc.report.html"
    assert proposal.by == "rafael"
    assert proposal.why == "nothing declared fits"


def test_a_field_that_is_not_a_hole_is_refused(tmp_path):
    """`Scaffold.propose` raises MF0002 for that, and the verb must not swallow it —
    proposing against a field that does not exist is a typo, not a new type."""
    _drafted(tmp_path)
    with pytest.raises(ValueError, match="MF0002"):
        ops.propose(ops.ProposeRequest(
            name="fastqc", field="not_a_field", id="x", description="y", why="z",
            by="rafael", workspace_root=tmp_path,
        ))


def test_show_reports_what_was_proposed(tmp_path):
    """The API reads proposals back through `show`. Without this the queue cannot tell a
    declined question from one nobody has reached, which is the whole point of declining."""
    _drafted(tmp_path)
    ops.propose(ops.ProposeRequest(
        name="fastqc", field="produces[0].type_id", id="qc.report.html",
        description="an HTML QC report", why="nothing declared fits", by="rafael",
        workspace_root=tmp_path,
    ))

    shown = ops.show(ops.ShowRequest(name="fastqc", **_ctx(tmp_path)))

    assert shown.proposed["produces[0].type_id"].id == "qc.report.html"
    assert any(h.subject == "produces[0].type_id" for h in shown.holes), "still a hole"
