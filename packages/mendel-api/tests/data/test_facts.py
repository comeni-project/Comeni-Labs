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


def test_mixed_data_keeps_the_facts_of_each_kind():
    """Checkpoint B, I3: a genome among reads does not erase the reads' facts."""
    facts, _ = derive([sample("a", paired=True, read_length=101),
                       sample("b", paired=True, read_length=101),
                       sample("g", type_id="genome.fasta")])
    assert {f.subject for f in facts} == {"paired", "read_length"}


def test_a_retracted_fact_lets_the_data_speak_again():
    """Checkpoint B, I4: retracting an override writes `open`, which must not hide the data."""
    from mendel_api.services.data.facts import merge
    from mendel_authoring.decisions import FactDecision

    facts, _ = merge([FactDecision(subject="read_length", origin=FactOrigin.OPEN)], [],
                     [sample("a", read_length=150)])
    assert [(f.subject, f.value, f.origin) for f in facts] == [
        ("read_length", 150, FactOrigin.MEASURED)]


def test_a_forgotten_input_lets_the_data_say_it_again():
    from mendel_api.services.data.facts import merge
    from mendel_authoring.decisions import InputDecision

    forgotten = InputDecision(key="fastq.reads", type_id="fastq.reads", present=False,
                              origin=FactOrigin.OPEN)
    _, inputs = merge([], [forgotten], [sample("a")])
    assert [(i.type_id, i.present) for i in inputs] == [("fastq.reads", True)]


def test_what_a_person_said_varies_stands_over_uniform_data():
    """Checkpoint B, I5."""
    from mendel_api.services.data.facts import merge
    from mendel_authoring.decisions import FactDecision

    facts, _ = merge([FactDecision(subject="read_length", origin=FactOrigin.VARIES)], [],
                     [sample("a", read_length=150), sample("b", read_length=150)])
    assert [(f.subject, f.origin) for f in facts] == [("read_length", FactOrigin.VARIES)]


def test_a_measured_fact_keeps_what_measured_it():
    """Checkpoint B, I10: pipeline.yml says which measurer answered."""
    s = sample("a")
    s["facts"] = [{"measurement": "read_length", "value": 101,
                   "pieces": ["fastq@1.1.0", "read_length@1.0.0"]}]
    facts, _ = derive([s])
    assert facts[0].pieces == ["fastq@1.1.0", "read_length@1.0.0"]


def test_a_said_fact_the_data_contradicts_keeps_both():
    """#510: `read_length: 150, said` chose STAR while the reads measured about 99. The person's
    word still stands; what the data measured is kept beside it."""
    from mendel_api.services.data.facts import merge
    from mendel_authoring.decisions import FactDecision

    said = [FactDecision(subject="read_length", value=150, origin=FactOrigin.PERSON_SAID)]
    facts, _ = merge(said, [], [sample("a", read_length=99), sample("b", read_length=99)])
    assert [(f.subject, f.value, f.origin, f.measured) for f in facts] == [
        ("read_length", 150, FactOrigin.PERSON_SAID, 99)]


def test_a_said_fact_the_data_agrees_with_carries_nothing_beside_it():
    from mendel_api.services.data.facts import merge
    from mendel_authoring.decisions import FactDecision

    said = [FactDecision(subject="read_length", value=99, origin=FactOrigin.PERSON_SAID)]
    facts, _ = merge(said, [], [sample("a", read_length=99)])
    assert [f.measured for f in facts] == [None]
