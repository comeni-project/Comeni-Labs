"""Every kind of change has a reader (Part I.0 spec §5.2): a command nothing reads is a log.

For each kind, the change is applied and each reader the spec names is asked whether it sees it:
the gap engine (a question closes), the resolver's goal, the memory every prompt is given, and the
goal card the person confirms."""

from mendel_api.services import changes, decisions, gaps, known, registry
from mendel_api.services import session as facade
from mendel_api.stages import gathering
from mendel_api_tests.gathering import _gathering
from mendel_api_tests.gathering import clean as clean
from mendel_authoring.payloads import DecisionChange

KINDS = ("want", "input", "measurement", "require", "pin", "parameter", "asked")


def _draft(sid: str) -> str:
    return facade.read(sid)["draft_id"]


def _open(sid: str) -> set[str]:
    stack = registry.stack()
    goal = decisions.goal(_draft(sid))
    found = gaps.gaps(goal.want, gathering.authoring_decisions.facts(_draft(sid)), stack)
    return set() if isinstance(found, gaps.Unreachable) else {g.subject for g in found}


def test_every_kind_is_listed():
    """A loop is not an assertion: the kinds below are every kind a change can be."""
    from typing import get_args

    declared = set(get_args(DecisionChange.model_fields["kind"].annotation))
    assert set(KINDS) <= declared and KINDS
    # The remaining kinds belong to the correction section, read through its own tests, and to a
    # person's structural intent (A1), read by the resolver's goal in `test_intent_changes.py`.
    assert declared - set(KINDS) == {"producer", "retain", "observation",
                                     "role", "exclude", "source"}


def test_a_want_is_read_by_the_goal_the_memory_and_the_card(clean):
    sid = _gathering(want=["counts.matrix"])
    changes.apply(_draft(sid), DecisionChange(kind="want", subject="qc.report"), who="ana")
    assert "qc.report" in decisions.goal(_draft(sid)).want
    assert "quality-control report" in known.text(sid)
    assert "qc.report" in gathering.compose_goal(sid).want


def test_an_input_closes_its_question_and_is_remembered(clean):
    sid = _gathering(want=["counts.matrix"])
    assert "genome.fasta" in _open(sid)
    changes.apply(
        _draft(sid), DecisionChange(kind="input", subject="genome.fasta", value=True), who="ana"
    )
    assert "genome.fasta" not in _open(sid)
    assert any(h.type_id == "genome.fasta" for h in decisions.goal(_draft(sid)).have)
    assert "reference genome (FASTA)" in known.text(sid)


def test_a_measurement_closes_its_question_reaches_the_profile_and_is_remembered(clean):
    sid = _gathering(want=["counts.matrix"])
    assert "read_length" in _open(sid)
    changes.apply(
        _draft(sid), DecisionChange(kind="measurement", subject="read_length", value=150), who="ana"
    )
    assert "read_length" not in _open(sid)
    assert decisions.goal(_draft(sid)).profile.get("read_length") == 150
    assert "read length: 150" in known.text(sid)


def test_a_required_state_reaches_the_goal_and_the_memory(clean):
    sid = _gathering(want=["counts.matrix"])
    changes.apply(
        _draft(sid),
        DecisionChange(kind="require", subject="counts.matrix", states=["gene_level"]),
        who="ana",
    )
    required = decisions.goal(_draft(sid)).constraints.required_states
    assert [(r.type_id, list(r.states)) for r in required] == [("counts.matrix", ["gene_level"])]
    assert "gene_level" in known.text(sid)


def test_a_pin_reaches_the_resolvers_goal_and_the_memory(clean):
    sid = _gathering(want=["counts.matrix"])
    changes.apply(
        _draft(sid),
        DecisionChange(kind="pin", subject="alignment.bam", value="nf-core/hisat2/align@2.2.2"),
        who="ana",
    )
    pins = decisions.goal(_draft(sid)).constraints.producers
    assert [p.contract for p in pins] == ["nf-core/hisat2/align@2.2.2"]
    assert "nf-core/hisat2/align@2.2.2" in known.text(sid)


def test_a_parameter_reaches_the_resolvers_goal_and_the_memory(clean):
    sid = _gathering(want=["counts.matrix"])
    changes.apply(
        _draft(sid),
        DecisionChange(kind="parameter", subject="seq_platform", value="ILLUMINA"),
        who="ana",
    )
    assert [p.value for p in decisions.goal(_draft(sid)).constraints.params] == ["ILLUMINA"]
    assert "seq_platform: ILLUMINA" in known.text(sid)


def test_what_was_asked_is_remembered_and_never_reaches_the_goal(clean):
    sid = _gathering(want=["counts.matrix"])
    changes.apply(
        _draft(sid), DecisionChange(kind="asked", subject="differential expression"), who="ana"
    )
    assert "differential expression" in known.text(sid).split("not offered here:")[1]
    assert [a.phrase for a in decisions.read_asked(_draft(sid))] == ["differential expression"]
    assert "differential" not in decisions.goal(_draft(sid)).model_dump_json()
