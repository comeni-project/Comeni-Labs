"""Settings decided at run time from a fact the pipeline measures (#217)."""

import pytest
from comeni_core.plan.at_run import (
    AtRunCondition,
    AtRunFallback,
    AtRunOp,
    AtRunSource,
    AtRunTest,
)
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
    assert value.at_run is not None
    (fact,) = value.at_run.facts
    assert (fact.measurement, fact.meta_key, fact.source, fact.measured_by) == (
        "genome_length", "genome_length", AtRunSource.MEASURED,
        "comeni/measure/genome_length_fai@1.0.0")
    (row,) = value.at_run.rows
    assert row.when == [] and row.takes == "genome_length" and row.integer
    assert [s.op for s in row.transform] == [AtRunOp.LOG2, AtRunOp.DIVIDE, AtRunOp.SUBTRACT,
                                             AtRunOp.AT_MOST, AtRunOp.ROUND]
    assert value.tier is Tier.DATA_PROFILED and value.value is None
    assert "decided at run time" in value.reason and "genome_length" in value.reason
    (premise,) = [p for p in value.premise if p.id == "genome_length"]
    assert premise.origin is PremiseOrigin.UNMEASURED
    assert {n.contract_id for n in ir.nodes} >= {"nf-core/samtools/faidx@1.24",
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
        "describes: genome.fasta\n", ""))
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
uses: nf-core/samtools/faidx@1.24
output: fai
entry: piece/fai.py
runs: [pipeline]
"""


def test_a_setting_waits_on_two_measured_facts(tmp_path):
    """A lookup may read several facts (#466); part 4 refused this as MD0328."""
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
    ir = resolve(goal, stack.routing, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary)
    lookup = _setting(ir).at_run
    assert [(f.measurement, f.source) for f in lookup.facts] == [
        ("genome_length", AtRunSource.MEASURED), ("genome_sequences", AtRunSource.MEASURED)]
    assert [c.fact for c in lookup.rows[0].when] == ["genome_sequences"]
    assert lookup.rows[0].takes == "genome_length"
    assert {m.measurement for m in ir.meta_at_run} == {"genome_length", "genome_sequences"}



def test_a_unique_decision_without_overlaps_is_decided_at_run_time(tmp_path):
    """One row cannot tie, so nobody needs asking in the run (operator, 11-11)."""
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
    assert _setting(ir).at_run is not None


def test_a_unique_decision_that_can_tie_stays_a_question(tmp_path):
    """Over the study's genome length, a tie is a question the build asks, never the run."""
    layer = overlay(tmp_path)
    rule = layer / "rules/star_index.yml"
    rule.write_text(rule.read_text().replace(
        "              when_implementation: [nf-core/star/genomegenerate@2.7.11b]}\n",
        "              when_implementation: [nf-core/star/genomegenerate@2.7.11b]}\n"
        "    hit: unique\n").replace(
        "      - when: {}\n        then: {fact: star_sa_index_nbases}\n",
        "      - when: {genome_length: \">= 100\"}\n        then: 8\n        because: a fixture\n"
        "      - when: {genome_length: \">= 10\"}\n        then: {fact: star_sa_index_nbases}\n"
        "        because: a fixture\n"
        "      - when: {genome_length: \"< 10\"}\n        then: 4\n"))
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
    return rows_of(_decision(rows), {"strandedness"}, premises, stack.rules, stack.measurements)


def test_rows_spell_every_test_on_the_measured_fact():
    rows = _rows(
        "  - {when: {strandedness: reverse}, then: 2}\n"
        "  - {when: {strandedness: {in: [forward, unstranded]}}, then: 1}\n"
        "  - {when: {strandedness: {not: reverse}}, then: 0}\n"
        "  - {when: {strandedness: present}, then: 3}\n"
        "  - {when: {strandedness: absent}, then: 4}\n")
    def one(row):
        (condition,) = row.when
        assert condition.fact == "strandedness"
        return condition.test, condition.operand, row.then

    assert [one(r) for r in rows] == [
        (AtRunTest.EQ, ["reverse"], 2), (AtRunTest.IN, ["forward", "unstranded"], 1),
        (AtRunTest.NE, ["reverse"], 0), (AtRunTest.PRESENT, [], 3), (AtRunTest.ABSENT, [], 4),
    ]


def test_a_known_fact_is_substituted_and_a_false_row_dropped():
    rows = _rows(
        "  - {when: {paired: false, strandedness: reverse}, then: 9}\n"
        "  - {when: {paired: true, strandedness: reverse}, then: 2}\n"
        "  - {when: {read_length: \">= 70\"}, then: {fact: read_length}}\n",
        known={"paired": True, "read_length": 150})
    assert [(r.when, r.then) for r in rows] == [
        ([AtRunCondition(fact="strandedness", test=AtRunTest.EQ, operand=["reverse"])], 2),
        ([], 150)]


def test_a_row_reading_an_unknown_other_fact_cannot_be_a_lookup():
    assert _rows("  - {when: {paired: true, strandedness: reverse}, then: 2}\n") is None


# ── final review: the resolver is asked once, and the route its answers make is measured ─


class _Last:
    """A resolver that answers every question with its last candidate, as a model might."""

    def __init__(self):
        self.asked: list[str] = []

    def resolve(self, ambiguity):
        from comeni_core.plan.decision import Resolution

        self.asked.append(ambiguity.key())
        return Resolution(value=ambiguity.candidates[-1], why="a model", confidence=0.5,
                          by="model")


def test_a_resolver_that_breaks_a_tie_differently_still_gets_its_pipeline_measured():
    """Final review, Critical: discovery must follow the real resolver's route."""
    stack = layers.load(ROOT / "registry")
    goal = Goal(have=[GoalInput(type_id=t) for t in ("fastq.reads", "genome.fasta",
                                                      "annotation.gtf")],
                want=["counts.matrix"], profile=stack.measurements.profile({}))
    resolver = _Last()
    ir = resolve(goal, stack.routing, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary, resolver=resolver)
    assert len(resolver.asked) == len(set(resolver.asked)), "a question was asked twice"
    if any(n.contract_id == STAR_ID for n in ir.nodes):
        assert _setting(ir).at_run is not None


def test_each_question_is_asked_once_on_every_path():
    stack = layers.load(ROOT / "registry")
    goal = Goal(have=[GoalInput(type_id=t) for t in ("fastq.reads", "genome.fasta",
                                                      "annotation.gtf")],
                want=["counts.matrix"],
                profile=stack.measurements.profile({"read_length": 150}))
    resolver = _Last()
    resolve(goal, stack.routing, stack.rules, stack.measurements,
            vocabulary=stack.vocabulary, resolver=resolver)
    assert resolver.asked and len(resolver.asked) == len(set(resolver.asked))
    assert not [k for k in resolver.asked if k.endswith(".sa_index_nbases")]


# ── #466: facts from the samplesheet, and the fallback ─────────────────────────────────


QUANT_RULE = """declares: rule
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: min_mqs}
    rows:
      - {when: {strandedness: reverse, read_length: ">= 70"}, then: 10, because: a fixture}
      - {when: {strandedness: reverse, read_length: "< 70"}, then: 7, because: a fixture}
      - {when: {strandedness: forward}, then: 5, because: a fixture}
      - {when: {strandedness: unstranded}, then: 0, because: a fixture}
"""


def _counted(tmp_path, *, varies: list[str], rule: str = QUANT_RULE, default: bool = True):
    layer = tmp_path / "quant"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules/quant.yml").write_text(rule)
    if not default:
        contract = (ROOT / "registry/tools/nf-core/subread/featurecounts/contract.yml").read_text()
        folder = layer / "tools/nf-core/subread/featurecounts"
        folder.mkdir(parents=True)
        (folder / "contract.yml").write_text(contract)
    stack = layers.load([ROOT / "registry", layer])
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in ("fastq.reads", "genome.fasta", "annotation.gtf")],
        "want": ["counts.matrix"], "constraints": {"varies": varies},
        "profile": stack.measurements.profile({}).model_dump(mode="json")})
    ir = resolve(goal, stack.routing, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary)
    node = next(n for n in ir.nodes if n.contract_id.startswith("nf-core/subread/"))
    return next(b.value for b in node.params if b.name == "min_mqs"), ir


def test_a_fact_that_varies_without_a_measurer_comes_from_its_cell(tmp_path):
    value, _ = _counted(tmp_path, varies=["read_length", "strandedness"])
    sources = {f.measurement: f.source for f in value.at_run.facts}
    assert sources == {"read_length": AtRunSource.CELL_OR_MEASURED,
                       "strandedness": AtRunSource.CELL}
    by = {f.measurement: f.measured_by for f in value.at_run.facts}
    assert by["strandedness"] is None and by["read_length"]


def test_a_measured_fact_nobody_said_varies_is_measured(tmp_path):
    value, ir = _counted(tmp_path, varies=["strandedness"])
    sources = {f.measurement: f.source for f in value.at_run.facts}
    assert sources == {"read_length": AtRunSource.MEASURED, "strandedness": AtRunSource.CELL}
    assert [m.measurement for m in ir.meta_at_run] == ["genome_length", "read_length"]


def test_a_fact_neither_stated_nor_varying_leaves_the_setting_to_lower_tiers(tmp_path):
    """Strandedness has no measurer: without its cell nothing in the run can decide it."""
    value, _ = _counted(tmp_path, varies=[])
    assert value.at_run is None


def test_the_fallback_is_the_default_first(tmp_path):
    value, _ = _counted(tmp_path, varies=["read_length", "strandedness"])
    assert value.at_run.fallback_is is AtRunFallback.VALUE and value.at_run.fallback == 0


def _param(**kw):
    from comeni_core.declared.contract import Param

    return Param.model_validate({"name": "x", "via": "positional", **kw})


def test_the_fallback_order():
    """A default; else the tool's own for a setting it can do without; else the person's
    answer, which may be to stop the run and name the sample (#466)."""
    from mendel_resolver.at_run import AT_RUN_STOP, fallback_of

    never = lambda: pytest.fail("asked when it needed not be")  # noqa: E731
    assert fallback_of(_param(default=3), never)[2] is AtRunFallback.VALUE
    omittable = _param(via="ext", key="args", template="--x {value}")
    assert fallback_of(omittable, never)[:3] == (None, "left to the tool: without a value it "
                                                 "uses its own", AtRunFallback.TOOL)
    assert fallback_of(_param(), lambda: (7, "a person"))[:3] == (7, "a person",
                                                                  AtRunFallback.VALUE)
    stopped = fallback_of(_param(), lambda: (AT_RUN_STOP, "a person"))
    assert stopped[0] is None and stopped[2] is AtRunFallback.STOP
    assert fallback_of(_param(), lambda: (None, "nobody"))[2] is AtRunFallback.QUESTION


ALIGN_RULE = """declares: rule
version: 1
decisions:
  - decides: {effect: param, of: alignment, name: star_ignore_sjdbgtf,
              when_implementation: [nf-core/star/align@2.7.11b]}
    rows:
      - {when: {strandedness: reverse}, then: true, because: a fixture}
      - {when: {strandedness: {in: [forward, unstranded]}}, then: false, because: a fixture}
"""


def _aligned(tmp_path, prior=()):
    """STAR align's positional setting, without its default, ruled from strandedness that
    varies: only a person can say what a sample with a blank cell gets."""
    from mendel_resolver.replay import ReplayResolver

    layer = tmp_path / "align"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules/align.yml").write_text(ALIGN_RULE)
    folder = layer / "tools/nf-core/star/align"
    folder.mkdir(parents=True)
    contract = (ROOT / "registry/tools/nf-core/star/align/contract.yml").read_text()
    (folder / "contract.yml").write_text(contract.replace(
        "  - name: star_ignore_sjdbgtf\n    default: false\n", "  - name: star_ignore_sjdbgtf\n"))
    stack = layers.load([ROOT / "registry", layer])
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in ("fastq.reads", "genome.fasta", "annotation.gtf")],
        "want": ["counts.matrix"], "constraints": {"varies": ["strandedness"]},
        "profile": stack.measurements.profile({"read_length": 150}).model_dump(mode="json")})
    ir = resolve(goal, stack.routing, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary, prior=list(prior),
                 resolver=ReplayResolver(list(prior)))
    node = next(n for n in ir.nodes if n.contract_id == "nf-core/star/align@2.7.11b")
    return node, next(b.value for b in node.params if b.name == "star_ignore_sjdbgtf"), ir


def test_a_persons_stop_answer_stops_the_run_and_keeps_the_lookup(tmp_path):
    """The fallback question is its own (`if_no_row.<setting>`): answering it never replaces
    the lookup with one value for every sample (Task 5 review, Critical)."""
    from comeni_core.plan.decision import ParamDecision
    from mendel_resolver.at_run import AT_RUN_STOP

    node, value, ir = _aligned(tmp_path / "a")
    asked = [d for d in ir.decisions if d.key == f"{node.id}.if_no_row.star_ignore_sjdbgtf"]
    assert asked and value.at_run.fallback_is is AtRunFallback.QUESTION
    stop = ParamDecision(key=asked[0].key, subject=asked[0].subject, reason="a person",
                         resolved_by="human", chosen=AT_RUN_STOP, human_override=AT_RUN_STOP,
                         candidates=[None])
    _, value, _ = _aligned(tmp_path / "b", prior=[stop])
    assert value.at_run is not None
    assert value.at_run.fallback_is is AtRunFallback.STOP and value.value is None


def test_a_fact_on_another_input_than_the_steps_own_is_not_a_lookup(tmp_path):
    """Genome length reaches STAR align only through its index, not on the reads' `meta` the
    step reads, so the setting falls to the lower tiers instead of an emit refusal (Task 5
    review)."""
    rule = ALIGN_RULE.replace("strandedness: reverse", "genome_length: \">= 1000\"").replace(
        "strandedness: {in: [forward, unstranded]}", "genome_length: \"< 1000\"")
    layer = tmp_path / "align"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules/align.yml").write_text(rule)
    stack = layers.load([ROOT / "registry", layer])
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in ("fastq.reads", "genome.fasta", "annotation.gtf")],
        "want": ["counts.matrix"],
        "profile": stack.measurements.profile({"read_length": 150}).model_dump(mode="json")})
    ir = resolve(goal, stack.routing, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary)
    node = next(n for n in ir.nodes if n.contract_id == "nf-core/star/align@2.7.11b")
    value = next(b.value for b in node.params if b.name == "star_ignore_sjdbgtf")
    assert value.at_run is None
