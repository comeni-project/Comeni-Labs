"""A tool chosen from a fact that differs between samples is chosen per sample (#466, stage 4)."""

from comeni_core.plan.at_run import AtRunSource, AtRunTest
from mendel_resolver import at_run, layers
from mendel_resolver.goal import Goal
from mendel_resolver.premises import build_premises
from support.paths import ROOT

STAR = "nf-core/star/align@2.7.11b"
HISAT2 = "nf-core/hisat2/align@2.2.2"


def _stack():
    return layers.load([ROOT / "registry"])


def _goal(stack, *, varies=(), profile=None) -> Goal:
    return Goal.model_validate({
        "have": [{"type_id": t} for t in ("fastq.reads", "genome.fasta", "annotation.gtf")],
        "want": ["counts.matrix"], "constraints": {"varies": list(varies)},
        "profile": stack.measurements.profile(profile or {}).model_dump(mode="json")})


def _points(stack, goal):
    premises = build_premises(goal=goal, derivations=stack.rules.derivations,
                              measurements=stack.measurements)
    return at_run.branch_points(stack.routing, stack.rules, premises, stack.measurements, goal)


def test_a_tool_chosen_from_a_varying_fact_is_a_branch_point():
    stack = _stack()
    (point,) = _points(stack, _goal(stack, varies=["read_length"]))
    assert point.decision.key() == "implementation:alignment"
    assert point.facts == ("read_length",)
    assert point.sources == (AtRunSource.CELL_OR_MEASURED,)
    assert point.outcomes == (STAR, HISAT2)
    star, hisat2 = point.rows
    assert (star.then, star.when[0].test, star.when[0].operand) == (STAR, AtRunTest.GE, [70])
    assert (hisat2.then, hisat2.when[0].test) == (HISAT2, AtRunTest.LT)


def test_a_stated_fact_is_no_branch_point():
    """Every sample stated to one side: today's pipeline exactly (Review Focus 2)."""
    stack = _stack()
    assert _points(stack, _goal(stack, profile={"read_length": 150})) == []


def test_an_unknown_fact_nobody_said_varies_is_no_branch_point():
    """It stays the question it is today: nobody said the samples differ."""
    stack = _stack()
    assert _points(stack, _goal(stack)) == []


def test_rows_that_reach_one_tool_are_no_branch_point(tmp_path):
    layer = tmp_path / "one"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules/alignment.yml").write_text("""declares: rule
version: 1
decisions:
  - decides: {effect: implementation, of: alignment}
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/star/align@2.7.11b, because: a fixture}
      - {when: {read_length: "< 70"}, then: nf-core/star/align@2.7.11b, because: a fixture}
""")
    stack = layers.load([ROOT / "registry", layer])
    assert _points(stack, _goal(stack, varies=["read_length"])) == []


def _resolved(stack, goal):
    from mendel_resolver.resolve import resolve

    return resolve(goal, stack.routing, stack.rules, stack.measurements,
                   vocabulary=stack.vocabulary)


def test_each_tool_is_routed_and_the_routes_merged_with_guards():
    stack = _stack()
    ir = _resolved(stack, _goal(stack, varies=["read_length"]))
    nodes = {n.id: n for n in ir.nodes}
    takes = {i: n.guard.takes for i, n in nodes.items() if n.guard is not None}
    assert takes == {"star_genomegenerate": [STAR], "star_align": [STAR],
                     "hisat2_build": [HISAT2], "hisat2_align": [HISAT2],
                     "samtools_faidx": [STAR], "measure_genome_length_fai": [STAR]}
    assert {"trimgalore", "samtools_sort", "subread_featurecounts"} <= set(nodes)
    assert nodes["star_align"].selection.tier.value == 3
    guard = nodes["star_align"].guard.lookup
    assert guard.rule == "implementation:alignment"
    assert [r.then for r in guard.rows] == [STAR, HISAT2]
    (fact,) = guard.facts
    assert fact.source is AtRunSource.CELL_OR_MEASURED and fact.measured_by
    into_sort = sorted(e.from_node for e in ir.edges
                       if (e.to_node, e.to_port) == ("samtools_sort", "bam"))
    assert into_sort == ["hisat2_align", "star_align"]
    keys = [d.key for d in ir.decisions]
    assert not [k for k in keys if k.startswith("producer:alignment.bam")]
    (fallback,) = [d for d in ir.decisions if "if_no_row" in d.key]
    assert fallback.candidates == [STAR, HISAT2, at_run.AT_RUN_STOP]
    assert guard.fallback == fallback.chosen
    # The measured fact is joined into the reads' `meta` before any guard reads it.
    assert [m.measurement for m in ir.meta_at_run if m.measurement == "read_length"]
    # Every node precedes what it feeds.
    order = [n.id for n in ir.nodes]
    assert all(order.index(e.from_node) < order.index(e.to_node) for e in ir.edges)


def test_the_merge_is_deterministic():
    stack = _stack()
    first = _resolved(stack, _goal(stack, varies=["read_length"]))
    second = _resolved(stack, _goal(stack, varies=["read_length"]))
    assert first.model_dump_json() == second.model_dump_json()


def test_a_stated_fact_builds_todays_pipeline():
    stack = _stack()
    ir = _resolved(stack, _goal(stack, profile={"read_length": 150}))
    assert not [n for n in ir.nodes if n.guard is not None]
    assert "hisat2_align" not in {n.id for n in ir.nodes}


def test_routes_that_differ_before_the_choice_are_refused(tmp_path):
    """HISAT2 taking untrimmed reads would trim only STAR's samples: a step carrying the
    samples upstream of the choice may not differ between routes (Review Focus 1)."""
    import pytest

    contract = (ROOT / "registry/tools/nf-core/hisat2/align/contract.yml").read_text()
    folder = tmp_path / "raw/tools/nf-core/hisat2/align"
    folder.mkdir(parents=True)
    start = contract.index("    state_required_conventional")
    end = contract.index("  - {name: index")
    (folder / "contract.yml").write_text(contract[:start] + contract[end:])
    stack = layers.load([ROOT / "registry", tmp_path / "raw"])
    with pytest.raises(ValueError, match="MD0339"):
        _resolved(stack, _goal(stack, varies=["read_length"]))
