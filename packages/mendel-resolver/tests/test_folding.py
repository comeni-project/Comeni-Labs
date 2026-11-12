"""A fact folds over the study: at build time from known values, in the run otherwise (#466)."""

import pytest
from comeni_core.plan.at_run import AtRunSource
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from mendel_resolver.premises import build_premises
from mendel_resolver.resolve import resolve
from support.paths import ROOT


def _rule(using: str, kind: str = "integer") -> str:
    return f"""declares: rule
version: 1
derives:
  - fact: study_read_length
    kind: {kind}
    aggregate: {{measurement: read_length, over: study, using: {using}}}
    because: a fixture
decisions:
  - decides: {{effect: param, of: quantification, name: min_mqs}}
    rows:
      - {{when: {{study_read_length: ">= 100"}}, then: 10, because: a fixture}}
      - {{when: {{study_read_length: "< 100"}}, then: 7, because: a fixture}}
"""


def _stack(tmp_path, using="agree", kind="integer"):
    layer = tmp_path / "fold"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules/fold.yml").write_text(_rule(using, kind))
    return layers.load([ROOT / "registry", layer])


def _premise(stack, values, using):
    goal = Goal.model_validate({
        "have": [{"type_id": "fastq.reads"}], "want": ["qc.report"],
        "profile": stack.measurements.profile({"read_length": values}).model_dump(mode="json")})
    premises = build_premises(goal=goal, derivations=stack.rules.derivations,
                              measurements=stack.measurements)
    found = premises.get("study_read_length")
    return None if found is None else found.value


@pytest.mark.parametrize(("using", "values", "folded"), [
    ("agree", [150, 150], 150),
    ("agree", [150, 75], None),
    ("count", [150, 75, 75], 3),
    ("distinct", [150, 75, 75], 2),
    ("max", [150, 75], 150),
])
def test_known_values_fold_at_build_time(tmp_path, using, values, folded):
    assert _premise(_stack(tmp_path, using), values, using) == folded


def test_all_and_any_fold_booleans(tmp_path):
    layer = tmp_path / "flags"
    (layer / "rules").mkdir(parents=True)
    (layer / "rules/flags.yml").write_text("""declares: rule
version: 1
derives:
  - fact: every_paired
    kind: boolean
    aggregate: {measurement: paired, over: study, using: all}
    because: a fixture
  - fact: some_paired
    kind: boolean
    aggregate: {measurement: paired, over: study, using: any}
    because: a fixture
""")
    stack = layers.load([ROOT / "registry", layer])
    goal = Goal.model_validate({
        "have": [{"type_id": "fastq.reads"}], "want": ["qc.report"],
        "profile": stack.measurements.profile({"paired": [True, False]}).model_dump(mode="json")})
    premises = build_premises(goal=goal, derivations=stack.rules.derivations,
                              measurements=stack.measurements)
    assert premises["every_paired"].value is False and premises["some_paired"].value is True


def test_a_fold_over_a_varying_fact_is_decided_in_the_run(tmp_path):
    stack = _stack(tmp_path)
    goal = Goal.model_validate({
        "have": [{"type_id": t} for t in ("fastq.reads", "genome.fasta", "annotation.gtf")],
        "want": ["counts.matrix"], "constraints": {"varies": ["read_length"]},
        "profile": stack.measurements.profile({}).model_dump(mode="json")})
    ir = resolve(goal, stack.routing, stack.rules, stack.measurements,
                 vocabulary=stack.vocabulary)
    node = next(n for n in ir.nodes if n.contract_id.startswith("nf-core/subread/"))
    value = node.param("min_mqs")
    assert value.at_run is not None
    (fact,) = value.at_run.facts
    assert (fact.measurement, fact.source, fact.folds, fact.using) == (
        "study_read_length", AtRunSource.FOLDED, "read_length", "agree")
    assert [r.when[0].fact for r in value.at_run.rows] == ["study_read_length"] * 2
    # Its members' read lengths are measured where a cell is blank, so the fold sees them all.
    assert "read_length" in {m.measurement for m in ir.meta_at_run}
