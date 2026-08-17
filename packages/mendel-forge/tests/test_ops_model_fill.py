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
