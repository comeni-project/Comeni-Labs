"""The model-fill op: attempt, persist, report.

Persistence is per fill rather than per batch. A provider dying after eight of fifteen holes
must cost eight holes' worth of nothing — the draft is the thing the forge accumulates.
"""

from pathlib import Path

import pytest
from comeni_core.declared.layered import DeclaredKind
from mendel_forge import ops
from mendel_forge.observe import Observation
from mendel_forge.scaffold import Candidate, FilledValue, Filler, Hole, Scaffold
from mendel_forge.workspace import Draft, Workspace


def _scaffold() -> Scaffold:
    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="fastqc",
        observation=Observation(source="nf-core", ref_id="nf-core:fastqc", facts={}, prose=[]),
        filled={},
        holes=[
            Hole(
                field="produces[0].type_id",
                what="what the port carries",
                why_open="not derivable",
                candidates=[Candidate(value="qc.report")],
            ),
            Hole(field="priority_because", what="why it ranks", why_open="a judgement"),
        ],
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    Workspace(root=tmp_path).save(Draft(name="fastqc", scaffold=_scaffold(), module=None))
    return tmp_path


class Always:
    """Fills anything with candidates."""

    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None:
        if not hole.candidates:
            return None
        return FilledValue(
            value=hole.candidates[0].value, filler=Filler.MODEL, by="test/model", why="because"
        )


class Explodes:
    """Fills one hole successfully, then fails — the flaky-provider case.

    Counts *fills*, not calls, so it does not depend on the order holes come back in: a
    candidate-less hole is declined without consuming the one success.
    """

    def __init__(self) -> None:
        self.filled = 0

    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None:
        if not hole.candidates:
            return None
        if self.filled:
            raise RuntimeError("provider went away")
        self.filled += 1
        return FilledValue(
            value=hole.candidates[0].value, filler=Filler.MODEL, by="test/model", why="because"
        )


def _request(root: Path, field: str | None = None) -> ops.ModelFillRequest:
    return ops.ModelFillRequest(
        name="fastqc", field=field, workspace_root=root, model="test/model"
    )


def test_it_fills_every_candidate_bearing_hole(workspace: Path) -> None:
    result = ops.fill_with_model(_request(workspace), filler=Always())
    filled = {o.field for o in result.outcomes if o.filled}
    assert filled == {"produces[0].type_id"}


def test_a_prose_hole_is_reported_as_declined_rather_than_omitted(workspace: Path) -> None:
    """A hole nobody attempted must not look like a hole that does not exist."""
    result = ops.fill_with_model(_request(workspace), filler=Always())
    declined = {o.field for o in result.outcomes if not o.filled}
    assert declined == {"priority_because"}
    assert all(o.declined_because for o in result.outcomes if not o.filled)


def test_the_fill_is_persisted(workspace: Path) -> None:
    ops.fill_with_model(_request(workspace), filler=Always())
    found = Workspace(root=workspace).load("fastqc")
    assert found.scaffold.filled["produces[0].type_id"].filler is Filler.MODEL
    assert found.scaffold.filled["produces[0].type_id"].by == "test/model"


def test_one_named_field_attempts_only_that_field(workspace: Path) -> None:
    result = ops.fill_with_model(
        _request(workspace, field="produces[0].type_id"), filler=Always()
    )
    assert [o.field for o in result.outcomes] == ["produces[0].type_id"]


def test_a_field_that_is_not_a_hole_is_refused(workspace: Path) -> None:
    with pytest.raises(ValueError) as raised:
        ops.fill_with_model(_request(workspace, field="not_a_field"), filler=Always())
    assert "MF0002" in str(raised.value)


def test_a_provider_dying_mid_batch_keeps_what_was_filled(tmp_path: Path) -> None:
    """The reason persistence is per fill. Eight of fifteen must cost nothing.

    Its own workspace, with **two** fillable holes: with one there is nothing for the
    provider to die after, and the test would pass without exercising anything.
    """
    scaffold = _scaffold()
    two = scaffold.model_copy(
        update={
            "holes": [
                *scaffold.holes,
                Hole(
                    field="consumes[0].type_id",
                    what="what the port takes",
                    why_open="not derivable",
                    candidates=[Candidate(value="fastq.reads")],
                ),
            ]
        }
    )
    Workspace(root=tmp_path).save(Draft(name="fastqc", scaffold=two, module=None))

    with pytest.raises(RuntimeError):
        ops.fill_with_model(_request(tmp_path), filler=Explodes())

    found = Workspace(root=tmp_path).load("fastqc")
    assert len(found.scaffold.filled) == 1, "the successful fill before the failure was lost"


def test_remaining_lists_the_holes_still_open(workspace: Path) -> None:
    result = ops.fill_with_model(_request(workspace), filler=Always())
    assert result.remaining == ["priority_because"]


def test_the_declined_reason_distinguishes_prose_from_a_refusal(workspace: Path) -> None:
    """'no candidates' and 'the model declined' are different problems with different fixes."""
    result = ops.fill_with_model(_request(workspace), filler=Always())
    prose = next(o for o in result.outcomes if o.field == "priority_because")
    assert "free text" in (prose.declined_because or "")


class ProposesFor:
    """Proposes for one field, declines everything else."""

    def __init__(self, field: str) -> None:
        self.field = field

    def fill(self, hole: Hole, observation: Observation):
        from mendel_forge.scaffold import Proposal

        if hole.field != self.field:
            return None
        return Proposal(
            id="star.log", description="a STAR run log", why="nothing fits", by="test/model"
        )


def test_a_proposal_is_persisted_and_the_hole_stays_open(workspace: Path) -> None:
    """A proposal is not a fill. `is_complete()` stays false and the draft cannot land,
    because a contract citing an undeclared type is the load-time refusal invariant 7 makes."""
    field = "produces[0].type_id"
    result = ops.fill_with_model(_request(workspace), filler=ProposesFor(field))
    found = Workspace(root=workspace).load("fastqc")

    assert found.scaffold.proposed[field].id == "star.log"
    assert field not in found.scaffold.filled
    assert found.scaffold.hole(field) is not None
    assert not found.scaffold.is_complete()

    outcome = next(o for o in result.outcomes if o.field == field)
    assert outcome.filled is False
    assert outcome.proposed_id == "star.log"
    assert "new entry is proposed" in (outcome.declined_because or "")


def test_landing_a_draft_with_a_proposal_says_what_it_wants(workspace: Path) -> None:
    from mendel_forge import assemble

    ops.fill_with_model(_request(workspace), filler=ProposesFor("produces[0].type_id"))
    found = Workspace(root=workspace).load("fastqc")
    with pytest.raises(ValueError) as raised:
        assemble.to_yaml(found.scaffold, approved_by="me", approved_at="2026-08-17")
    assert "MF0004" in str(raised.value)
    assert "star.log" in str(raised.value)


def test_a_proposal_for_a_field_that_is_not_a_hole_is_refused(workspace: Path) -> None:
    found = Workspace(root=workspace).load("fastqc")
    from mendel_forge.scaffold import Proposal

    with pytest.raises(ValueError) as raised:
        found.scaffold.propose(
            "not_a_field", Proposal(id="x", description="d", why="w", by="m")
        )
    assert "MF0002" in str(raised.value)


class PicksFromCandidates:
    """Answers with whatever the hole currently offers — so a stale candidate list shows up."""

    def fill(self, hole: Hole, observation: Observation):
        if not hole.candidates:
            return None
        # The *first* candidate, which is the registry-derived one — the channel name is
        # deliberately last now, so picking from the end would test the opposite of the point.
        return FilledValue(
            value=hole.candidates[0].value, filler=Filler.MODEL, by="test/model", why="first"
        )


def test_a_refreshed_candidate_is_accepted_by_the_scaffold_that_offered_it(
    tmp_path: Path,
) -> None:
    """**The whole draft died on this.** A dependent hole's candidates are recomputed once its
    type is filled, and the recomputed hole has to *be* the scaffold's hole — otherwise `fill`
    validates against the stale list and refuses a value the model was correctly offered, with
    MF0003, taking the tool down rather than the hole."""
    scaffold = _scaffold()
    with_dependent = scaffold.model_copy(
        update={
            "holes": [
                *scaffold.holes,
                Hole(
                    field="consumes[0].type_id",
                    what="the type",
                    why_open="not derivable",
                    candidates=[Candidate(value="qc.report")],
                ),
                Hole(
                    field="consumes[0].name",
                    what="the name",
                    why_open="a choice",
                    candidates=[Candidate(value="multiqc_files")],
                    after="consumes[0].type_id",
                    channels=("multiqc_files",),
                ),
            ]
        }
    )
    Workspace(root=tmp_path).save(Draft(name="fastqc", scaffold=with_dependent, module=None))

    result = ops.fill_with_model(
        ops.ModelFillRequest(
            name="fastqc",
            workspace_root=tmp_path,
            model="test/model",
            registry_root=Path("registry"),
        ),
        filler=PicksFromCandidates(),
    )
    name = next(o for o in result.outcomes if o.field == "consumes[0].name")
    assert name.filled, f"a refreshed candidate was refused: {name.declined_because}"
    assert name.value != "multiqc_files", "candidates were never refreshed at all"
    assert name.value in {"qc", "qcs", "report", "reports", "zip"}, name.value
