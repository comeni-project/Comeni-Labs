"""One writer for every change to intent and facts, whoever asks for it (Part I.0 spec §5.1)."""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft
from mendel_api.services import changes, decisions, drafts
from mendel_authoring.payloads import Change
from mendel_postgres import reachable
from test_authoring_building import clean as clean

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


def _draft() -> str:
    return drafts.create(DraftGraph(), "changes", "ana")


def _wanting(draft: str) -> str:
    changes.apply(draft, Change(kind="want", subject="counts.matrix"), who="ana")
    return draft


def _revision(draft: str) -> int:
    with session_scope() as db:
        return db.get(PipelineDraft, draft).decision_revision


@pytest.mark.parametrize("change, check", [
    (Change(kind="want", subject="counts.matrix"),
     lambda d: [w.type_id for w in d.wants if w.present] == ["counts.matrix"]),
    (Change(kind="input", subject="genome.fasta", value=True),
     lambda d: [i.type_id for i in d.inputs if i.present] == ["genome.fasta"]),
    (Change(kind="measurement", subject="paired", value=True),
     lambda d: [(f.subject, f.value) for f in d.facts] == [("paired", True)]),
    (Change(kind="pin", subject="alignment.bam", value="nf-core/hisat2/align@2.2.2"),
     lambda d: d.producers[0].contract == "nf-core/hisat2/align@2.2.2"),
    (Change(kind="parameter", subject="seq_platform", value="ILLUMINA"),
     lambda d: d.parameters[0].value == "ILLUMINA"),
], ids=["want", "input", "measurement", "pin", "parameter"])
def test_each_change_writes_its_family(clean, change, check):
    draft = _draft()
    assert changes.apply(draft, change, who="ana")
    assert check(decisions.read(draft))


def test_a_required_state_on_a_want(clean):
    draft = _wanting(_draft())
    changes.apply(draft, Change(kind="require", subject="counts.matrix", states=["gene_level"]),
                  who="ana")
    assert decisions.read(draft).wants[0].states == ["gene_level"]


def test_asked_is_recorded_apart_from_the_goal(clean):
    draft = _draft()
    changes.apply(draft, Change(kind="asked", subject="differential expression",
                                heard="differential expression", heard_seq=1, actor="model"),
                  who="model")
    assert [a.phrase for a in decisions.read_asked(draft)] == ["differential expression"]


def test_a_heard_change_keeps_its_words(clean):
    draft = _draft()
    changes.apply(draft, Change(kind="measurement", subject="paired", value=True,
                                heard="paired-end", heard_seq=1, actor="model"), who="model")
    assert decisions.heard_of(draft)[("fact", "paired")] == ("paired-end", 1)


def test_an_undeclared_type_is_refused_and_nothing_written(clean):
    draft = _draft()
    with pytest.raises(ValueError, match="MI0204"):
        changes.apply(draft, Change(kind="want", subject="made.up"), who="ana")
    assert decisions.read(draft).wants == []


def test_an_undeclared_tool_and_parameter_are_refused(clean):
    draft = _draft()
    with pytest.raises(ValueError, match="MI0204"):
        changes.apply(draft, Change(kind="pin", subject="alignment.bam",
                                    value="nf-core/nothing@1.0.0"), who="ana")
    with pytest.raises(ValueError, match="MI0204"):
        changes.apply(draft, Change(kind="parameter", subject="no_such_param", value=1), who="ana")


def test_a_value_the_measurement_refuses_is_refused(clean):
    with pytest.raises(ValueError, match="MI0208"):
        changes.apply(_draft(), Change(kind="measurement", subject="read_length", value=-4),
                      who="ana")


def test_retracting_each_kind_removes_it(clean):
    draft = _wanting(_draft())
    changes.apply(draft, Change(kind="input", subject="genome.fasta", value=True), who="ana")
    changes.apply(draft, Change(kind="input", subject="genome.fasta", retract=True), who="ana")
    assert not [i for i in decisions.read(draft).inputs if i.present]

    changes.apply(draft, Change(kind="measurement", subject="paired", value=True), who="ana")
    changes.apply(draft, Change(kind="measurement", subject="paired", retract=True), who="ana")
    assert decisions.read(draft).facts[0].value is None

    pin = Change(kind="pin", subject="alignment.bam", value="nf-core/hisat2/align@2.2.2")
    changes.apply(draft, pin, who="ana")
    changes.apply(draft, pin.model_copy(update={"retract": True}), who="ana")
    assert decisions.read(draft).producers[0].contract is None

    changes.apply(draft, Change(kind="parameter", subject="seq_platform", value="ILLUMINA"),
                  who="ana")
    changes.apply(draft, Change(kind="parameter", subject="seq_platform", retract=True),
                  who="ana")
    assert decisions.read(draft).parameters[0].value is None

    changes.apply(draft, Change(kind="asked", subject="differential expression"), who="ana")
    changes.apply(draft, Change(kind="asked", subject="differential expression", retract=True),
                  who="ana")
    assert decisions.read_asked(draft) == []

    changes.apply(draft, Change(kind="want", subject="counts.matrix", retract=True), who="ana")
    assert not [w for w in decisions.read(draft).wants if w.present]


def test_retracting_what_was_never_there_changes_nothing(clean):
    """Review Focus 5."""
    draft = _draft()
    before = _revision(draft)
    for kind, subject in (("input", "genome.fasta"), ("want", "counts.matrix"),
                          ("pin", "alignment.bam"), ("parameter", "seq_platform"),
                          ("asked", "anything")):
        assert changes.apply(draft, Change(kind=kind, subject=subject, retract=True),
                             who="ana") is False
    assert _revision(draft) == before


def test_describe_says_each_change_in_words():
    assert changes.describe(Change(kind="measurement", subject="read_length", value=150)) == (
        "read length is 150")
    assert changes.describe(Change(kind="input", subject="genome.fasta", retract=True)) == (
        "forgot that you have the reference genome (FASTA)")
