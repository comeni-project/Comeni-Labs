"""Deciding a proposal, as a verb both transports share."""

from pathlib import Path

import pytest
from mendel_forge import ops
from mendel_forge.scaffold import Decision

ROOT = Path(__file__).resolve().parents[3]


def _ctx(tmp_path):
    return {
        "registry_root": ROOT / "registry",
        "source_root": ROOT / "registry",
        "workspace_root": tmp_path,
    }


def _proposed(tmp_path):
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    ops.propose(ops.ProposeRequest(
        name="fastqc", field="produces[0].type_id", id="qc.report.html",
        description="an HTML report", why="nothing fits", by="rafael",
        workspace_root=tmp_path,
    ))


def test_approving_reports_the_value_and_a_shorter_remaining(tmp_path):
    _proposed(tmp_path)
    before = ops.show(ops.ShowRequest(name="fastqc", **_ctx(tmp_path))).holes

    got = ops.decide(ops.DecideRequest(
        name="fastqc", field="produces[0].type_id", decision=Decision.APPROVED,
        why="a real distinct output", by="reviewer", workspace_root=tmp_path,
    ))

    assert got.value == "qc.report.html"
    assert "produces[0].type_id" not in got.remaining
    assert len(got.remaining) == len(before) - 1


def test_rejecting_reports_no_value_and_leaves_remaining_alone(tmp_path):
    _proposed(tmp_path)
    before = ops.show(ops.ShowRequest(name="fastqc", **_ctx(tmp_path))).holes

    got = ops.decide(ops.DecideRequest(
        name="fastqc", field="produces[0].type_id", decision=Decision.REJECTED,
        why="it is a measurement, not a type", by="reviewer", workspace_root=tmp_path,
    ))

    assert got.value is None
    assert len(got.remaining) == len(before), "a rejected proposal leaves the hole open"


def test_a_rename_is_recorded_on_the_draft(tmp_path):
    _proposed(tmp_path)
    ops.decide(ops.DecideRequest(
        name="fastqc", field="produces[0].type_id", decision=Decision.APPROVED,
        id="qc.html_report", why="clearer", by="reviewer", workspace_root=tmp_path,
    ))

    shown = ops.show(ops.ShowRequest(name="fastqc", **_ctx(tmp_path)))
    assert shown.proposed["produces[0].type_id"].decided_id == "qc.html_report"
    assert shown.proposed["produces[0].type_id"].id == "qc.report.html"


def test_deciding_something_never_proposed_is_refused(tmp_path):
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    with pytest.raises(ValueError, match="MF0002"):
        ops.decide(ops.DecideRequest(
            name="fastqc", field="roles", decision=Decision.APPROVED,
            why="w", by="r", workspace_root=tmp_path,
        ))
