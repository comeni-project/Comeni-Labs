"""Facts about the data are derived, not decided (#511, Checkpoint A): what the kept samples
measured is read from the analysis's data every time, so changing the data changes the facts,
and what a person or the AI said still stands over them."""

from mendel_api.services.data.facts import derive
from mendel_authoring.decisions import FactOrigin


def sample(name, type_id="fastq.reads", left_out=False, **facts):
    return {"name": name, "files": [], "outcome": "measured", "type_id": type_id,
            "left_out": left_out,
            "facts": [{"measurement": k, "value": v} for k, v in facts.items()]}


def test_a_fact_every_kept_sample_agrees_on_is_measured():
    facts, _ = derive([sample("a", paired=True, read_length=101),
                       sample("b", paired=True, read_length=101)])
    assert {(f.subject, f.value, f.origin) for f in facts} == {
        ("paired", True, FactOrigin.MEASURED), ("read_length", 101, FactOrigin.MEASURED)}


def test_a_fact_the_samples_disagree_on_varies():
    facts, _ = derive([sample("a", read_length=101), sample("b", read_length=50)])
    assert [(f.subject, f.origin, f.value) for f in facts] == [
        ("read_length", FactOrigin.VARIES, None)]


def test_a_fact_one_sample_did_not_measure_is_left_open():
    facts, _ = derive([sample("a", read_length=101), sample("b")])
    assert facts == []


def test_a_left_out_sample_does_not_count():
    facts, _ = derive([sample("a", read_length=101), sample("b", left_out=True, read_length=50)])
    assert [(f.subject, f.value) for f in facts] == [("read_length", 101)]


def test_each_kind_of_data_is_an_input():
    _, inputs = derive([sample("a"), sample("b", type_id="fasta.assembly"),
                        sample("c", type_id=None)])
    assert [(i.type_id, i.present, i.origin) for i in inputs] == [
        ("fasta.assembly", True, FactOrigin.MEASURED), ("fastq.reads", True, FactOrigin.MEASURED)]


def test_no_data_derives_nothing():
    assert derive([]) == ([], [])
