"""The Groovy lookup and the resolver agree, case by case, under Nextflow (#217, Review Focus 1).

A run-time setting is computed twice in two languages: by the resolver when a fact is known
before the build, and by the emitted closure when the pipeline measures it. They must give the
same value for every case the table check tries, and for the edges arithmetic gets wrong:
`round` at .5 (half to even), `log2` of a power of two, a value on a comparison's boundary.
"""

import shutil
import subprocess

import pytest
import yaml
from comeni_core.logic.when import matches
from comeni_core.plan.at_run import AtRun
from mendel_compiler.groovy_lookup import closure
from mendel_resolver import layers
from mendel_resolver.at_run import rows_of
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.premises import Premise, PremiseOrigin, build_premises
from mendel_resolver.rules.format import Decision
from mendel_resolver.rules.validate import _points
from support.at_run import ROOT, STAR_ID, overlay

pytestmark = pytest.mark.slow


def _groovy(lookup: AtRun, cases: list) -> str:
    """Each case's value, as the emitted closure computes it, printed by Nextflow."""
    rendered = ", ".join("null" if c is None else repr(c) if not isinstance(c, str) else f"'{c}'"
                         for c in cases)
    expr = closure(lookup)
    script = (
        "workflow {\n"
        f"    [{rendered}].each {{ value ->\n"
        f"        def meta = [{lookup.meta_key}: value]\n"
        f"        println('CASE ' + String.valueOf({expr}))\n"
        "    }\n"
        "}\n"
    )
    return script


def _run(tmp_path, script: str) -> list[str]:
    if shutil.which("nextflow") is None:
        pytest.skip("needs Nextflow")
    (tmp_path / "main.nf").write_text(script)
    done = subprocess.run(["nextflow", "-q", "run", "main.nf"], cwd=tmp_path,
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr + done.stdout
    return [line.removeprefix("CASE ") for line in done.stdout.splitlines()
            if line.startswith("CASE ")]


def _python(value) -> str:
    return "null" if value is None else str(value).lower() if isinstance(value, bool) \
        else str(value)


def test_the_star_index_size_agrees_over_every_power_of_two(tmp_path):
    stack = layers.load([ROOT / "registry", overlay(tmp_path / "layer")])
    goal = Goal(have=[GoalInput(type_id="genome.fasta"), GoalInput(type_id="annotation.gtf")],
                want=["genome.index.star"], profile=stack.measurements.profile({}))
    from mendel_compiler import orchestrate

    pipeline = orchestrate.build(goal, registry_roots=[ROOT / "registry",
                                                       tmp_path / "layer/overlay"]).pipeline
    star = next(s for s in pipeline.steps if s.module.contract_id == STAR_ID)
    lookup = next(s for s in star.settings if s.name == "sa_index_nbases").at_run
    cases = [None, *(2 ** n for n in range(0, 41)), 3, 5, 29903, 3_100_000_000, 2 ** 40 + 1]
    expected = []
    for value in cases:
        if value is None:
            expected.append(_python(lookup.fallback))
            continue
        known = Goal(have=goal.have, want=goal.want,
                     profile=stack.measurements.profile({"genome_length": value}))
        premises = build_premises(goal=known, derivations=stack.rules.derivations,
                                  measurements=stack.measurements)
        pin = stack.rules.value_for(["index_building"], "sa_index_nbases", premises,
                                    implementation=STAR_ID)
        expected.append(_python(pin.value if pin else lookup.fallback))
    assert _run(tmp_path, _groovy(lookup, cases)) == expected


def _table_case(tmp_path, rows: str, fact: str, fallback):
    stack = layers.load(ROOT / "registry")
    decision = Decision.model_validate(yaml.safe_load(
        "decides: {effect: param, of: quantification, name: strandedness}\nrows:\n" + rows))
    built = rows_of(decision, fact, {}, stack.rules, stack.measurements)
    lookup = AtRun(fact=fact, meta_key=fact, measured_by="comeni/measure/x@1.0.0",
                   rule=decision.key(), rows=built, fallback=fallback, fallback_reason="test")
    cases = [None, *_points(fact, decision.rows, stack.measurements, {})]
    expected = []
    for value in cases:
        premises = {} if value is None else {
            fact: Premise(id=fact, value=value, origin=PremiseOrigin.MEASURED)}
        row = next((r for r in decision.rows if matches(r.when, premises)), None)
        expected.append(_python(fallback if value is None or row is None else row.then))
    assert _run(tmp_path, _groovy(lookup, cases)) == expected


def test_an_enum_table_agrees(tmp_path):
    _table_case(tmp_path, "  - {when: {strandedness: reverse}, then: 2}\n"
                          "  - {when: {strandedness: {in: [forward]}}, then: 1}\n"
                          "  - {when: {strandedness: {not: forward}}, then: 0}\n",
                "strandedness", 0)


def test_a_comparison_agrees_on_both_sides_of_its_boundary(tmp_path):
    _table_case(tmp_path, "  - {when: {read_length: \">= 70\"}, then: star}\n"
                          "  - {when: {read_length: \"< 70\"}, then: hisat2}\n",
                "read_length", "hisat2")
