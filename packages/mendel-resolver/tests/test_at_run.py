"""Settings decided at run time from a fact the pipeline measures (#217)."""

import pytest
from comeni_core.plan.at_run import AtRunOp, AtRunTest
from comeni_core.plan.tiers import PremiseOrigin, Tier
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from support.at_run import ROOT, STAR_ID, overlay


def _resolved(tmp_path, *, stated: int | None = None, **kw):
    stack = layers.load([ROOT / "registry", overlay(tmp_path, **kw)])
    profile = stack.measurements.profile({"genome_length": stated} if stated else {})
    goal = Goal(have=[GoalInput(type_id="genome.fasta"), GoalInput(type_id="annotation.gtf")],
                want=["genome.index.star"], profile=profile)
    return resolve(goal, stack.routing, stack.rules, stack.measurements,
                   vocabulary=stack.vocabulary), stack


def _setting(ir):
    node = next(n for n in ir.nodes if n.contract_id == STAR_ID)
    return next(b.value for b in node.params if b.name == "sa_index_nbases")


def test_an_unknown_genome_length_is_decided_at_run_time(tmp_path):
    ir, _ = _resolved(tmp_path)
    value = _setting(ir)
    assert value.at_run is not None and value.at_run.fact == "genome_length"
    assert value.at_run.meta_key == "genome_length"
    assert value.at_run.measured_by == "comeni/measure/genome_length_fai@1.0.0"
    (row,) = value.at_run.rows
    assert row.test is AtRunTest.ANY and row.takes_fact and row.integer
    assert [s.op for s in row.transform] == [AtRunOp.LOG2, AtRunOp.DIVIDE, AtRunOp.SUBTRACT,
                                             AtRunOp.AT_MOST, AtRunOp.ROUND]
    assert value.tier is Tier.DATA_PROFILED and value.value is None
    assert "decided at run time" in value.reason and "genome_length" in value.reason
    (premise,) = [p for p in value.premise if p.id == "genome_length"]
    assert premise.origin is PremiseOrigin.UNMEASURED
    assert {n.contract_id for n in ir.nodes} >= {"nf-core/samtools/faidx@1.21",
                                                 "comeni/measure/genome_length_fai@1.0.0"}
    (meta,) = ir.meta_at_run
    assert (meta.measurement, meta.type_id, meta.meta_key) == (
        "genome_length", "genome.fasta", "genome_length")


def test_a_stated_genome_length_is_decided_at_build(tmp_path):
    ir, _ = _resolved(tmp_path, stated=29903)
    value = _setting(ir)
    assert value.at_run is None and value.value == 6
    assert not [n for n in ir.nodes if n.contract_id.startswith("comeni/measure/")]
    assert ir.meta_at_run == []


def test_without_a_pipeline_measurer_the_setting_falls_back(tmp_path):
    ir, _ = _resolved(tmp_path, with_measurer=False)
    value = _setting(ir)
    assert value.at_run is None and value.tier is Tier.AMBIGUOUS


def test_a_fact_that_describes_no_input_falls_back(tmp_path):
    """Its value would have no `meta` to travel on."""
    from support.at_run import GENOME_LENGTH

    ir, _ = _resolved(tmp_path, genome_length=GENOME_LENGTH.replace(
        "describes: genome.fasta\nmeta_key: genome_length\n", ""))
    assert _setting(ir).at_run is None


def test_rerouting_keeps_the_graph(tmp_path):
    """The build with the measuring steps holds every node, edge and decision of the one
    without, unchanged (Review Focus 2)."""
    with_steps, _ = _resolved(tmp_path / "a")
    without, _ = _resolved(tmp_path / "b", with_measurer=False)
    kept = {n.id: n.contract_id for n in with_steps.nodes}
    for node in without.nodes:
        assert kept.get(node.id) == node.contract_id
    edges = {e.model_dump_json() for e in with_steps.edges}
    assert {e.model_dump_json() for e in without.edges} <= edges


def test_the_same_goal_resolves_to_the_same_ir(tmp_path):
    first, _ = _resolved(tmp_path / "a")
    second, _ = _resolved(tmp_path / "b")
    assert first.model_dump_json() == second.model_dump_json()


SEQUENCES = """declares: measurement
id: genome_sequences
kind: integer
minimum: 0
description: "How many sequences the reference genome holds"
cite: "a test fixture"
describes: genome.fasta
"""

SEQUENCES_MEASURER = """declares: measurer
id: genome_sequences_fai
version: 1.0.0
measures: genome_sequences
by: tool
uses: nf-core/samtools/faidx@1.21
output: fai
entry: piece/fai.py
runs: [pipeline]
"""


def test_two_run_time_facts_in_one_decision_are_refused(tmp_path):
    """One lookup reads one measured fact (MD0328)."""
    layer = overlay(tmp_path)
    (layer / "vocabulary/measurements/genome_sequences.yml").write_text(SEQUENCES)
    folder = layer / "measurers/measures/genome_sequences_fai"
    (folder / "piece").mkdir(parents=True)
    (folder / "measurer.yml").write_text(SEQUENCES_MEASURER)
    (folder / "piece/fai.py").write_text("def parse(stream, decided):\n    return None\n")
    rule = layer / "rules/star_index.yml"
    rule.write_text(rule.read_text().replace(
        "      - when: {}\n        then: {fact: star_sa_index_nbases}\n",
        "      - when: {genome_sequences: \">= 1\"}\n        then: {fact: star_sa_index_nbases}\n"
        "        because: a fixture\n"
        "      - when: {genome_sequences: \"< 1\"}\n        then: 4\n"))
    stack = layers.load([ROOT / "registry", layer])
    goal = Goal(have=[GoalInput(type_id="genome.fasta"), GoalInput(type_id="annotation.gtf")],
                want=["genome.index.star"], profile=stack.measurements.profile({}))
    with pytest.raises(ValueError, match="MD0328"):
        resolve(goal, stack.routing, stack.rules, stack.measurements,
                vocabulary=stack.vocabulary)



def test_a_unique_decision_is_not_decided_at_run_time(tmp_path):
    """An overlap at run time would have nobody to ask, so it stays a question."""
    layer = overlay(tmp_path)
    rule = layer / "rules/star_index.yml"
    rule.write_text(rule.read_text().replace(
        "              when_implementation: [nf-core/star/genomegenerate@2.7.11b]}\n",
        "              when_implementation: [nf-core/star/genomegenerate@2.7.11b]}\n"
        "    hit: unique\n"))
    stack = layers.load([ROOT / "registry", layer])
    goal = Goal(have=[GoalInput(type_id="genome.fasta"), GoalInput(type_id="annotation.gtf")],
                want=["genome.index.star"], profile=stack.measurements.profile({}))
    ir = resolve(goal, stack.routing, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary)
    assert _setting(ir).at_run is None
    assert not [n for n in ir.nodes if n.contract_id.startswith("comeni/measure/")]


# ── Task 6 review ───────────────────────────────────────────────────────────────────────


def test_a_persons_answer_is_not_displaced_by_a_rule_decided_later(tmp_path):
    """Re-resolving a pipeline whose setting a person answered keeps their answer."""
    from comeni_core.plan.decision import ParamDecision

    first, _ = _resolved(tmp_path / "a", with_measurer=False)
    node = next(n for n in first.nodes if n.contract_id == STAR_ID)
    answered = ParamDecision(key=f"{node.id}.sa_index_nbases", subject="sa_index_nbases",
                             reason="a person said so", resolved_by="human", chosen=8,
                             human_override=8, candidates=[None])
    stack = layers.load([ROOT / "registry", overlay(tmp_path / "b")])
    goal = Goal(have=[GoalInput(type_id="genome.fasta"), GoalInput(type_id="annotation.gtf")],
                want=["genome.index.star"], profile=stack.measurements.profile({}))
    ir = resolve(goal, stack.routing, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary, prior=[answered])
    assert _setting(ir).at_run is None
    assert not [n for n in ir.nodes if n.contract_id.startswith("comeni/measure/")]


def _decision(rows: str):
    import yaml
    from mendel_resolver.rules.format import Decision

    return Decision.model_validate(yaml.safe_load(
        "decides: {effect: param, of: quantification, name: strandedness}\nrows:\n" + rows))


def _rows(rows: str, known: dict | None = None):
    from mendel_resolver.at_run import rows_of
    from mendel_resolver.premises import Premise

    stack = layers.load(ROOT / "registry")
    premises = {k: Premise(id=k, value=v, origin=PremiseOrigin.ASSERTED)
                for k, v in (known or {}).items()}
    return rows_of(_decision(rows), "strandedness", premises, stack.rules, stack.measurements)


def test_rows_spell_every_test_on_the_measured_fact():
    rows = _rows(
        "  - {when: {strandedness: reverse}, then: 2}\n"
        "  - {when: {strandedness: {in: [forward, unstranded]}}, then: 1}\n"
        "  - {when: {strandedness: {not: reverse}}, then: 0}\n"
        "  - {when: {strandedness: present}, then: 3}\n"
        "  - {when: {strandedness: absent}, then: 4}\n")
    assert [(r.test, r.operand, r.then) for r in rows] == [
        (AtRunTest.EQ, ["reverse"], 2), (AtRunTest.IN, ["forward", "unstranded"], 1),
        (AtRunTest.NE, ["reverse"], 0), (AtRunTest.ANY, [], 3),
    ]


def test_a_known_fact_is_substituted_and_a_false_row_dropped():
    rows = _rows(
        "  - {when: {paired: false, strandedness: reverse}, then: 9}\n"
        "  - {when: {paired: true, strandedness: reverse}, then: 2}\n"
        "  - {when: {read_length: \">= 70\"}, then: {fact: read_length}}\n",
        known={"paired": True, "read_length": 150})
    assert [(r.test, r.then) for r in rows] == [(AtRunTest.EQ, 2), (AtRunTest.ANY, 150)]


def test_a_row_reading_an_unknown_other_fact_cannot_be_a_lookup():
    assert _rows("  - {when: {paired: true, strandedness: reverse}, then: 2}\n") is None
