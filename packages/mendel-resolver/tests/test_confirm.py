"""An estimate a build decision used is measured again over all the data in the run (#465)."""

from comeni_core.declared.measurement import MeasuredEntry
from comeni_core.goal.profile import Evidence
from comeni_core.plan.tiers import ValueSource
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from mendel_resolver.resolve import resolve
from support.at_run import ROOT

STACK = layers.load(ROOT / "registry")
PIECES = ("fastq@1.1.0", "read_length@1.0.0")


def _goal(*entries) -> Goal:
    said = [MeasuredEntry(m, v, ValueSource.SAID)
            for m, v in (("paired", True), ("strandedness", "reverse"), ("n_samples", 2))
            if m not in {e.measurement for e in entries}]
    return Goal.model_validate({
        "have": [{"type_id": "fastq.reads"}, {"type_id": "annotation.gtf"},
                 {"type_id": "genome.fasta"}],
        "want": ["counts.matrix"],
        "constraints": {"required_states": [{"type_id": "counts.matrix",
                                             "states": ["gene_level"]}]},
        "profile": STACK.measurements.profile_of([*said, *entries]).model_dump(mode="json"),
    })


def _measured(name, value, coverage, pieces=PIECES):
    return MeasuredEntry(name, value, ValueSource.MEASURED, None, pieces,
                         Evidence(records=2000, coverage=coverage))


def _ir(goal):
    return resolve(goal, STACK.routing, STACK.rules, STACK.measurements,
                   vocabulary=STACK.vocabulary)


def test_a_head_read_length_that_chose_the_aligner_is_confirmed():
    ir = _ir(_goal(_measured("read_length", 150, "head")))
    (confirm,) = ir.confirms
    assert confirm.measurement == "read_length" and confirm.estimate == 150
    assert any(u.startswith("selection:") for u in confirm.used_by)
    measuring = [n for n in ir.nodes if n.contract_id == "comeni/measure/fastq@1.1.0"]
    assert [n.id for n in measuring] == [confirm.measured_at]


def test_a_stated_fact_is_never_measured_again():
    ir = _ir(_goal(MeasuredEntry("read_length", 150, ValueSource.SAID)))
    assert ir.confirms == []
    assert not [n for n in ir.nodes if n.contract_id.startswith("comeni/measure/")]


def test_a_fact_read_in_full_is_not_measured_again():
    ir = _ir(_goal(_measured("read_length", 150, "all")))
    assert ir.confirms == []


def test_two_estimates_on_the_reads_share_one_step():
    ir = _ir(_goal(_measured("read_length", 150, "head"),
                   _measured("paired", True, "head", ("fastq@1.1.0", "paired@1.1.0"))))
    measuring = [n for n in ir.nodes if n.contract_id == "comeni/measure/fastq@1.1.0"]
    assert len(measuring) == 1
    assert {c.measurement for c in ir.confirms} <= {"read_length", "paired"}
    assert {c.measured_at for c in ir.confirms} == {measuring[0].id}


def test_confirming_keeps_the_graph_and_the_saved_pipeline_carries_it():
    without = _ir(_goal(MeasuredEntry("read_length", 150, ValueSource.SAID)))
    with_confirm = _ir(_goal(_measured("read_length", 150, "head")))
    kept = {n.id: n.contract_id for n in with_confirm.nodes}
    assert all(kept.get(n.id) == n.contract_id for n in without.nodes)
