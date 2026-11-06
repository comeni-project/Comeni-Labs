"""QUAST built end to end with its reference off, optional and required (#460).

The curated registry plus a small overlay: QUAST's contract (from the comeni-core fixture,
with its reports typed `assembly.qc` so nothing else competes to make them), the assembly
family and the types the registry does not yet declare.
"""

from pathlib import Path

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.goal.asked import Constraints, InputChoice, InputState
from mendel_compiler import orchestrate, pipeline_file
from mendel_resolver.goal import Goal, GoalInput

ROOT = Path(__file__).resolve().parents[3]
QUAST = (ROOT / "packages/comeni-core/tests/fixtures/constraints/quast.yml").read_text()
QUAST_ID = "nf-core/quast@5.3.0"

OVERLAY = {
    "assembly.family.yml": "declares: family\nid: assembly\n"
                           "description: Genomes assembled from reads, and reports on them\n",
    "assembly.fasta.yml": "declares: vocabulary\nid: assembly.fasta\nstates: []\nscope: sample\n",
    "assembly.qc.yml": "declares: vocabulary\nid: assembly.qc\nstates: []\nscope: sample\n",
    "annotation.gff.yml": "declares: vocabulary\nid: annotation.gff\nstates: []\nscope: run\n",
    "quast.contract.yml": "declares: contract\n" + QUAST.replace("type_id: qc.report",
                                                                 "type_id: assembly.qc"),
}

NEEDS_REF = """declares: contract
id: lab/needsref@1.0.0
nf_process: NEEDSREF
nf_include: modules/lab/needsref/main
roles: [qc_per_sample]
consumes: [{name: reference, type_id: genome.fasta}]
produces: [{name: summary, type_id: assembly.summary}]
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-11-06"}
"""


def _overlay(tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    layer = tmp_path / "overlay"
    layer.mkdir()
    for name, body in {**OVERLAY, **(extra or {})}.items():
        (layer / name).write_text(body)
    return layer


def _build(tmp_path: Path, goal: Goal, extra: dict[str, str] | None = None) -> Pipeline:
    roots = [ROOT / "registry", _overlay(tmp_path, extra)]
    return orchestrate.build(goal, registry_roots=roots).pipeline


def _quast_step(pipeline: Pipeline):
    return next(s for s in pipeline.steps if s.module.contract_id == QUAST_ID)


def _goal(have: list[str], want: list[str], *choices: tuple[str, InputState]) -> Goal:
    return Goal(have=[GoalInput(type_id=t) for t in have], want=want,
                constraints=Constraints(inputs=[
                    InputChoice(contract=QUAST_ID, port=p, state=s) for p, s in choices]))


def test_an_off_reference_becomes_an_empty_call_argument(tmp_path):
    pipeline = _build(tmp_path, _goal(["assembly.fasta"], ["assembly.qc"]))
    step = _quast_step(pipeline)
    assert [i.port for i in step.inputs] == ["consensus"]
    fasta = next(a for a in step.call if a.ports == ["fasta"])
    assert fasta.empty_width == 2
    assert not any(c.type_id == "genome.fasta" for c in pipeline.channels)


def test_an_optional_reference_becomes_an_optional_channel_with_its_width(tmp_path):
    pipeline = _build(tmp_path, _goal(["assembly.fasta", "genome.fasta"], ["assembly.qc"],
                                      ("fasta", InputState.OPTIONAL)))
    channel = next(c for c in pipeline.channels if c.type_id == "genome.fasta")
    assert channel.optional is True and channel.absent_width == 2
    assert "fasta" in [i.port for i in _quast_step(pipeline).inputs]
    consensus = next(c for c in pipeline.channels if c.type_id == "assembly.fasta")
    assert consensus.optional is False


def test_a_shared_channel_optional_here_and_required_there_is_required(tmp_path):
    extra = {"needsref.contract.yml": NEEDS_REF,
             "assembly.summary.yml": "declares: vocabulary\nid: assembly.summary\nstates: []\n"}
    goal = _goal(["assembly.fasta", "genome.fasta"], ["assembly.qc", "assembly.summary"],
                 ("fasta", InputState.OPTIONAL))
    channel = next(c for c in _build(tmp_path, goal, extra).channels
                   if c.type_id == "genome.fasta")
    assert channel.optional is False


def test_input_records_round_trip_sorted(tmp_path):
    pipeline = _build(tmp_path, _goal(["assembly.fasta"], ["assembly.qc"]))
    records = _quast_step(pipeline).input_states
    assert [(r.port, r.state) for r in records] == [
        ("fasta", InputState.OFF), ("gff", InputState.OFF)]
    again = Pipeline.model_validate(pipeline.model_dump(mode="json"))
    assert _quast_step(again).input_states == records


def test_a_pipeline_saved_before_this_change_still_loads():
    pipeline = pipeline_file.load(ROOT / "tests/fixtures/pipeline-v8/pipeline.yml")
    assert pipeline.steps, "the fixture has no steps — this test is measuring nothing"
    assert all(not c.optional for c in pipeline.channels)
    assert all(s.input_states == [] for s in pipeline.steps)


# ── emission ────────────────────────────────────────────────────────────────────────────────

from mendel_compiler.emit import emit  # noqa: E402

EMPTY_2 = "Channel.value([[:], []])"


def _quast_call(text: str) -> str:
    return next(line for line in text.splitlines() if line.strip().startswith("QUAST("))


def test_an_off_reference_is_emitted_as_two_empty_tuples(tmp_path):
    text = emit(_build(tmp_path, _goal(["assembly.fasta"], ["assembly.qc"])))
    assert _quast_call(text).count(EMPTY_2) == 2
    assert "params.genome_fasta" not in text


def test_an_optional_reference_is_emitted_as_a_ternary_on_its_param(tmp_path):
    pipeline = _build(tmp_path, _goal(["assembly.fasta", "genome.fasta"], ["assembly.qc"],
                                      ("fasta", InputState.OPTIONAL)))
    channel = next(c for c in pipeline.channels if c.type_id == "genome.fasta")
    line = next(text for text in emit(pipeline).splitlines()
                if text.strip().startswith((f"ch_{channel.name} =", f"{channel.name} =")))
    assert f"params.{channel.param} ? (" in line
    assert line.rstrip().endswith(f": {EMPTY_2}")
    assert _quast_call(emit(pipeline)).count(EMPTY_2) == 1, "gff is still off"


def test_a_required_reference_is_emitted_as_a_plain_channel(tmp_path):
    extra = {"needsref.contract.yml": NEEDS_REF,
             "assembly.summary.yml": "declares: vocabulary\nid: assembly.summary\nstates: []\n"}
    goal = _goal(["assembly.fasta", "genome.fasta"], ["assembly.qc", "assembly.summary"],
                 ("fasta", InputState.OPTIONAL))
    pipeline = _build(tmp_path, goal, extra)
    param = next(c for c in pipeline.channels if c.type_id == "genome.fasta").param
    assert f"params.{param} ?" not in emit(pipeline)


def test_a_rule_only_a_run_can_settle_is_on_the_step(tmp_path):
    goal = _goal(["assembly.fasta", "genome.fasta", "annotation.gff"], ["assembly.qc"],
                 ("fasta", InputState.OPTIONAL), ("gff", InputState.OPTIONAL))
    step = _quast_step(_build(tmp_path, goal))
    assert step.run_rules == [
        "`gff` is used only with `fasta` (QUAST reads --features only against a reference (-r))"]


WIDE_REF = """declares: contract
id: lab/wideref@1.0.0
nf_process: WIDEREF
nf_include: modules/lab/wideref/main
roles: [qc_per_sample]
consumes:
  - {name: assembly, type_id: assembly.fasta}
  - {name: reference, type_id: genome.fasta, required: false}
produces: [{name: summary, type_id: assembly.summary}]
nf_inputs: [{ports: [assembly]}, {ports: [reference], absent: 3}]
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-11-06"}
"""


def test_one_optional_input_with_two_placeholder_widths_is_refused(tmp_path):
    """Final review: two consumers wanting [[:], []] and [[:], [], []] cannot share one."""
    import pytest

    extra = {"wideref.contract.yml": WIDE_REF,
             "assembly.summary.yml": "declares: vocabulary\nid: assembly.summary\nstates: []\n"}
    goal = Goal(have=[GoalInput(type_id="assembly.fasta"), GoalInput(type_id="genome.fasta")],
                want=["assembly.qc", "assembly.summary"], constraints=Constraints(inputs=[
                    InputChoice(contract=QUAST_ID, port="fasta", state=InputState.OPTIONAL),
                    InputChoice(contract="lab/wideref@1.0.0", port="reference",
                                state=InputState.OPTIONAL)]))
    with pytest.raises(ValueError, match="width"):
        _build(tmp_path, goal, extra)
