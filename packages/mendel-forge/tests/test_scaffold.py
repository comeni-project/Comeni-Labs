import pytest
from comeni_core.declared.layered import DeclaredKind
from comeni_core.review import ValueSource
from mendel_forge.observe import Excerpt, Observation
from mendel_forge.scaffold import Candidate, Hole, Scaffold


def _scaffold() -> Scaffold:
    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="tools/nf-core/fastqc/fastqc.contract.yml",
        observation=Observation(source="nf-core", ref_id="nf-core/fastqc"),
        filled={},
        holes=[
            Hole(
                subject="produces[0].type_id",
                what="the semantic type this port emits",
                why_open="a module declares a filename pattern, never a type",
                candidates=[Candidate(value="qc.report", note="declared in registry/types")],
                evidence=[Excerpt(locator="meta.yml:31", text="FastQC report")],
            )
        ],
    )


def test_a_scaffold_with_holes_is_not_complete():
    assert _scaffold().is_complete() is False


def test_filling_the_last_hole_completes_it():
    filled = _scaffold().fill(
        "produces[0].type_id", "qc.report", ValueSource.HUMAN, by="rafael", why="it is a report"
    )
    assert filled.is_complete() is True
    assert filled.holes == []
    assert filled.filled["produces[0].type_id"].value == "qc.report"
    assert filled.filled["produces[0].type_id"].how is ValueSource.HUMAN


def test_filling_is_not_in_place():
    """A scaffold is a value. Mutating one would make the workspace's saved copy lie."""
    original = _scaffold()
    original.fill("produces[0].type_id", "qc.report", ValueSource.HUMAN, by="r", why="w")
    assert original.is_complete() is False


def test_filling_a_field_that_is_not_a_hole_is_refused():
    with pytest.raises(ValueError, match="MF0002"):
        _scaffold().fill("roles", "qc_per_sample", ValueSource.HUMAN, by="r", why="w")


def test_a_value_outside_the_candidates_is_refused():
    """Invariant 7 at draft time. A closed candidate list that anything may ignore is not one."""
    with pytest.raises(ValueError, match="MF0003"):
        _scaffold().fill("produces[0].type_id", "invented.type", ValueSource.HUMAN, by="r", why="w")


def test_a_hole_with_no_candidates_accepts_free_text():
    """`priority_because` has no enumerable legal values, and demanding some would make
    every prose field unfillable."""
    scaffold = Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="t",
        observation=Observation(source="s", ref_id="r"),
        holes=[
            Hole(
                subject="priority_because",
                what="why this ranks here",
                why_open="a judgement",
            )
        ],
    )
    assert scaffold.fill(
        "priority_because", "it is the only aligner", ValueSource.HUMAN, by="r", why="w"
    ).is_complete()


def test_holes_serialise_in_field_order():
    scaffold = Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="t",
        observation=Observation(source="s", ref_id="r"),
        holes=[
            Hole(subject="zebra", what="w", why_open="o"),
            Hole(subject="alpha", what="w", why_open="o"),
        ],
    )
    assert [h["subject"] for h in scaffold.model_dump()["holes"]] == ["alpha", "zebra"]


def test_a_list_field_is_checked_member_by_member():
    """`roles` holds several values from one closed set, so the candidates are the legal
    members. Comparing the whole list against them rejected every legal answer — found by
    ops.fill on the first real call, not by reading the code."""
    scaffold = Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target="t",
        observation=Observation(source="s", ref_id="r"),
        holes=[
            Hole(
                subject="roles",
                what="the jobs this contract can do",
                why_open="a module declares no role",
                candidates=[Candidate(value="qc_per_sample"), Candidate(value="alignment")],
            )
        ],
    )
    assert scaffold.fill(
        "roles", ["qc_per_sample"], ValueSource.HUMAN, by="r", why="w"
    ).is_complete()
    assert scaffold.fill(
        "roles", ["qc_per_sample", "alignment"], ValueSource.HUMAN, by="r", why="w"
    ).is_complete()
    with pytest.raises(ValueError, match="MF0003"):
        scaffold.fill("roles", ["qc_per_sample", "invented"], ValueSource.HUMAN, by="r", why="w")
