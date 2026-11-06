"""Routing a tool's optional inputs: off unless switched on, and why either way (#460).

QUAST is the case. Its reference (`fasta`) and `gff` are optional; three of its reports exist
only with a reference. A goal that only has assemblies must route QUAST without them.
"""

import pathlib

import pytest
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.goal.asked import InputState
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.router import route
from support.paths import ROOT

QUAST = (ROOT / "packages/comeni-core/tests/fixtures/constraints/quast.yml").read_text()

TYPES = {
    "assembly.fasta": "scope: sample\n",
    "genome.fasta": "scope: run\n",
    "annotation.gff": "scope: run\n",
    "qc.report": "",
}


def _world(tmp_path: pathlib.Path, contracts: dict[str, str]) -> tuple[Registry, Vocabulary]:
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    for type_id, extra in TYPES.items():
        (vocab_dir / f"{type_id}.yml").write_text(
            f"declares: vocabulary\nid: {type_id}\n"
            + ("" if "states:" in extra else "states: []\n") + extra)
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()
    for name, body in contracts.items():
        (contract_dir / name).write_text("declares: contract\n" + body)
    vocabulary = Vocabulary.load(tmp_path)
    return Registry.load(tmp_path, vocabulary), vocabulary


def _assemblies_only() -> Goal:
    return Goal(have=[GoalInput(type_id="assembly.fasta")], want=["qc.report"])


def test_quast_with_only_assemblies_leaves_its_optional_inputs_off(tmp_path):
    registry, _ = _world(tmp_path, {"quast.yml": QUAST})
    plan = route(_assemblies_only(), registry)
    step = next(s for s in plan.steps if s.contract_id == "nf-core/quast@5.3.0")
    assert [(r.port, r.state, r.by) for r in step.inputs] == [
        ("fasta", InputState.OFF, "router"), ("gff", InputState.OFF, "router")]
    assert all(r.reason == "off: not switched on" for r in step.inputs)


# ── switching on, needs, and constraint checks after resolution ─────────────────────────────

from comeni_core.declared.constraints import sentence  # noqa: E402
from comeni_core.declared.measurement import MeasurementRegistry  # noqa: E402
from comeni_core.goal.asked import Constraints, InputChoice  # noqa: E402
from mendel_resolver.resolve import resolve  # noqa: E402
from mendel_resolver.router import ConstraintViolation  # noqa: E402
from mendel_resolver.rules import RuleTable  # noqa: E402

QUAST_ID = "nf-core/quast@5.3.0"

# The misassembly report as its own state, so a later step can need exactly it.
QUAST_STATED = QUAST.replace(
    "{name: misassemblies, type_id: qc.report,",
    "{name: misassemblies, type_id: qc.report::misassemblies,")
REPORT = """
id: lab/report@1.0.0
nf_process: REPORT
nf_include: modules/lab/report/main
consumes: [{name: misassemblies, type_id: qc.report::misassemblies}]
produces: [{name: html, type_id: report.html}]
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-11-06"}
"""


def _stated_world(tmp_path):
    TYPES["qc.report"] = "states: [misassemblies]\n"
    TYPES["report.html"] = ""
    try:
        registry, vocabulary = _world(tmp_path, {"quast.yml": QUAST_STATED, "report.yml": REPORT})
    finally:
        TYPES["qc.report"] = ""
        TYPES.pop("report.html")
    return registry, vocabulary


def _choose(*choices: tuple[str, InputState]) -> Constraints:
    return Constraints(inputs=[InputChoice(contract=QUAST_ID, port=p, state=s)
                               for p, s in choices])


def _records(plan) -> dict[str, tuple[InputState, str, str]]:
    step = next(s for s in plan.steps if s.contract_id == QUAST_ID)
    return {r.port: (r.state, r.by, r.reason) for r in step.inputs}


def test_a_person_switches_the_reference_on_as_optional(tmp_path):
    registry, vocabulary = _world(tmp_path, {"quast.yml": QUAST})
    goal = Goal(have=[GoalInput(type_id="assembly.fasta"), GoalInput(type_id="genome.fasta")],
                want=["qc.report"], constraints=_choose(("fasta", InputState.OPTIONAL)))
    records = _records(route(goal, registry))
    assert records["fasta"][:2] == (InputState.OPTIONAL, "person")
    ir = resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)
    node = next(n for n in ir.nodes if n.contract_id == QUAST_ID)
    assert [(r.port, r.state) for r in node.inputs] == [
        ("fasta", InputState.OPTIONAL), ("gff", InputState.OFF)]


def test_switching_gff_on_brings_fasta_with_the_reason(tmp_path):
    registry, _ = _world(tmp_path, {"quast.yml": QUAST})
    goal = Goal(have=[GoalInput(type_id="assembly.fasta"), GoalInput(type_id="genome.fasta"),
                      GoalInput(type_id="annotation.gff")],
                want=["qc.report"], constraints=_choose(("gff", InputState.OPTIONAL)))
    contract = registry.get(QUAST_ID)
    assert _records(route(goal, registry))["fasta"] == (
        InputState.OPTIONAL, "router", sentence(contract.constraints[0]))


def test_a_step_needing_misassemblies_makes_fasta_required(tmp_path):
    registry, vocabulary = _stated_world(tmp_path)
    goal = Goal(have=[GoalInput(type_id="assembly.fasta"), GoalInput(type_id="genome.fasta")],
                want=["report.html"])
    state, by, reason = _records(route(goal, registry))["fasta"]
    assert (state, by) == (InputState.REQUIRED, "router")
    assert "misassemblies" in reason
    ir = resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)
    assert any(e.from_port == "misassemblies" for e in ir.edges)


def test_switching_off_an_input_a_later_step_needs_is_refused(tmp_path):
    registry, _ = _stated_world(tmp_path)
    goal = Goal(have=[GoalInput(type_id="assembly.fasta"), GoalInput(type_id="genome.fasta")],
                want=["report.html"], constraints=_choose(("fasta", InputState.OFF)))
    with pytest.raises(ConstraintViolation, match=r"MD0609.*fasta.*misassemblies"):
        route(goal, registry)


FLAGGED = """
id: lab/flagged@1.0.0
nf_process: FLAGGED
nf_include: modules/lab/flagged/main
consumes:
  - {name: reads, type_id: assembly.fasta}
  - {name: extra, type_id: genome.fasta, required: false}
produces: [{name: out, type_id: qc.report}]
params:
  - {name: strict, via: positional, default: true, domain: {kind: boolean},
     because: "strict mode is the tool's default"}
nf_inputs: [{ports: [reads]}, {ports: [extra], absent: 2}, {param: strict}]
constraints:
  - {when: {param.strict: true}, forbids: [extra], because: "strict mode reads no extra input"}
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-11-06"}
"""


def test_a_forbidden_connection_is_refused_after_parameters_resolve(tmp_path):
    registry, vocabulary = _world(tmp_path, {"flagged.yml": FLAGGED})
    goal = Goal(have=[GoalInput(type_id="assembly.fasta"), GoalInput(type_id="genome.fasta")],
                want=["qc.report"], constraints=Constraints(inputs=[
                    InputChoice(contract="lab/flagged@1.0.0", port="extra",
                                state=InputState.REQUIRED)]))
    with pytest.raises(ConstraintViolation, match=r"MD0610.*extra"):
        resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)


# ── final review fixes ──────────────────────────────────────────────────────────────────────

KRAKEN2 = (ROOT / "packages/comeni-core/tests/fixtures/constraints/kraken2.yml").read_text()
QC = """
id: lab/qc@1.0.0
nf_process: QC
nf_include: modules/lab/qc/main
consumes: [{name: reads, type_id: fastq.reads}]
produces: [{name: html, type_id: report.html}]
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-11-06"}
"""


def test_a_withheld_output_does_not_refuse_a_consumer_fed_by_the_persons_files(tmp_path):
    """Final review I1: QC of the raw reads was refused because kraken2 withholds its FASTQs."""
    TYPES.update({"fastq.reads": "", "kraken2.db": "", "report.html": ""})
    try:
        registry, vocabulary = _world(tmp_path, {"kraken2.yml": KRAKEN2, "qc.yml": QC})
    finally:
        for t in ("fastq.reads", "kraken2.db", "report.html"):
            TYPES.pop(t)
    goal = Goal(have=[GoalInput(type_id="fastq.reads"), GoalInput(type_id="kraken2.db")],
                want=["qc.report", "report.html"])
    ir = resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)
    assert {n.contract_id for n in ir.nodes} >= {"lab/qc@1.0.0"}


def test_a_later_need_raises_an_earlier_visits_input(tmp_path):
    """Final review I2: the wants' order decided whether fasta was switched on."""
    registry, vocabulary = _stated_world(tmp_path)
    have = [GoalInput(type_id="assembly.fasta"), GoalInput(type_id="genome.fasta")]
    for want in (["qc.report", "report.html"], ["report.html", "qc.report"]):
        goal = Goal(have=have, want=want)
        assert _records(route(goal, registry))["fasta"][0] is InputState.REQUIRED, want
        resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)


NEEDS_REF = """
id: lab/needsref@1.0.0
nf_process: NEEDSREF
nf_include: modules/lab/needsref/main
consumes: [{name: reference, type_id: genome.fasta}]
produces: [{name: summary, type_id: report.html}]
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-11-06"}
"""


def test_an_input_another_step_requires_from_the_same_file_is_required_here(tmp_path):
    """Final review I4: the channel became required but quast's own checks still treated
    fasta as optional per run."""
    TYPES["report.html"] = ""
    try:
        registry, _ = _world(tmp_path, {"quast.yml": QUAST, "needsref.yml": NEEDS_REF})
    finally:
        TYPES.pop("report.html")
    goal = Goal(have=[GoalInput(type_id="assembly.fasta"), GoalInput(type_id="genome.fasta")],
                want=["qc.report", "report.html"],
                constraints=_choose(("fasta", InputState.OPTIONAL)))
    state, by, reason = _records(route(goal, registry))["fasta"]
    assert (state, by) == (InputState.REQUIRED, "router")
    assert "lab/needsref@1.0.0" in reason
