"""Verifying a draft that carries an approved proposal.

Between approving and landing, the draft cites a type the registry does not declare — that is
the cost spec §3.1 accepted. The rung is not weakened; it is pointed at the vocabulary the
draft would CREATE, which is the question a reviewer actually has: if I land this, does it
load?
"""

from pathlib import Path

from mendel_forge import ops
from mendel_forge.scaffold import Decision, Proposal
from mendel_forge.verify import Rung
from mendel_forge.workspace import Workspace

ROOT = Path(__file__).resolve().parents[3]


def _ctx(tmp_path):
    return {
        "registry_root": ROOT / "registry",
        "source_root": ROOT / "vendor",
        "workspace_root": tmp_path,
    }


def _settle_the_rest(scaffold):
    """Answer every remaining hole so the ladder actually reaches LOADS.

    **Without this the test is vacuous** — `verify` stops on `complete` while any hole is
    open, so `loads` is `[]` and every assertion over it passes by being empty. Measured:
    the first version of this test reached `['complete']` and nothing else.
    """
    from comeni_core.review import ValueSource

    while scaffold.holes:
        hole = scaffold.holes[0]
        value = hole.candidates[0].value if hole.candidates else "because the module says so"
        if hole.subject == "roles":
            value = [value]
        scaffold = scaffold.fill(hole.subject, value, ValueSource.HUMAN, by="t", why="t")
    return scaffold


def test_an_approved_type_does_not_fail_the_load_rung(tmp_path):
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    workspace = Workspace(root=tmp_path)
    draft = workspace.load("fastqc")

    field = "produces[0].type_id"
    scaffold = draft.scaffold.propose(
        field,
        Proposal(id="qc.report.html", description="an HTML report", why="nothing fits",
                 by="rafael"),
    ).decide(field, Decision.APPROVED, by="reviewer", why="a real distinct output")
    scaffold = _settle_the_rest(scaffold)
    workspace.save(draft.model_copy(update={"scaffold": scaffold}))

    result = ops.verify_(ops.VerifyRequest(name="fastqc", **_ctx(tmp_path)))
    rungs = [v.rung for v in result.verdicts]

    assert Rung.LOADS in rungs, f"the ladder must reach LOADS to test it; reached {rungs}"
    loads = [v for v in result.verdicts if v.rung is Rung.LOADS]
    # `detail` holds what the loader actually said; `summary` is a fixed sentence for the
    # whole rung and never names the type — asserting on it passes whatever happens, which
    # is how the first version of this test was green while proving nothing.
    assert not any(
        "qc.report.html" in d.detail for v in loads for d in v.diagnostics
    ), "an approved type must not fail the rung it is being added to satisfy"


def test_the_same_draft_fails_that_rung_without_the_approval(tmp_path):
    """The other half, and the one that proves the first is not passing by accident: fill the
    field with the SAME id and no proposal behind it, and LOADS refuses it."""
    ops.draft(ops.DraftRequest(ref="nf-core:fastqc", name="fastqc", **_ctx(tmp_path)))
    workspace = Workspace(root=tmp_path)
    draft = workspace.load("fastqc")

    from comeni_core.review import ValueSource

    field = "produces[0].type_id"
    hole = draft.scaffold.hole(field)
    scaffold = draft.scaffold.model_copy(
        update={
            "holes": [h for h in draft.scaffold.holes if h.subject != field],
            "filled": {
                **draft.scaffold.filled,
                field: __import__(
                    "mendel_forge.scaffold", fromlist=["FilledValue"]
                ).FilledValue(
                    value="qc.report.html", by="t", how=ValueSource.HUMAN, why="t"
                ),
            },
        }
    )
    assert hole is not None
    scaffold = _settle_the_rest(scaffold)
    workspace.save(draft.model_copy(update={"scaffold": scaffold}))

    result = ops.verify_(ops.VerifyRequest(name="fastqc", **_ctx(tmp_path)))
    loads = [v for v in result.verdicts if v.rung is Rung.LOADS]

    assert any(
        "qc.report.html" in d.detail for v in loads for d in v.diagnostics
    ), "an unapproved undeclared type must still fail the rung"
