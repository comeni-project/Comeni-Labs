"""Routing with the type connected to a port (#464).

salmon quant is the case: FASTQ reads are mapped against an index; BAM reads are quantified in
alignment mode against the transcripts, and the index is forbidden. The rows say so on
`type.reads`, so which inputs a step needs depends on what routing connected.
"""

import pathlib

from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.goal.asked import InputState
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from mendel_resolver.router import route
from mendel_resolver.rules import RuleTable
from support.paths import ROOT

SALMON = (ROOT / "packages/comeni-core/tests/fixtures/constraints/salmon_quant.yml").read_text()
SALMON_ID = "nf-core/salmon/quant@1.10.3"

TYPES = {
    "fastq.reads": "scope: sample\n",
    "alignment.bam": "scope: sample\n",
    "salmon.index": "scope: run\n",
    "annotation.gtf": "scope: run\n",
    "transcripts.fasta": "scope: run\n",
    "salmon.quant": "scope: sample\n",
}


def _world(tmp_path: pathlib.Path) -> tuple[Registry, Vocabulary]:
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    for type_id, extra in TYPES.items():
        (vocab_dir / f"{type_id}.yml").write_text(
            f"declares: vocabulary\nid: {type_id}\nstates: []\n" + extra)
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()
    (contract_dir / "salmon.yml").write_text("declares: contract\n" + SALMON)
    vocabulary = Vocabulary.load(tmp_path)
    return Registry.load(tmp_path, vocabulary), vocabulary


def _states(plan) -> dict[str, InputState]:
    step = next(s for s in plan.steps if s.contract_id == SALMON_ID)
    return {r.port: r.state for r in step.inputs}


def _goal(*have: str) -> Goal:
    return Goal(have=[GoalInput(type_id=t) for t in have], want=["salmon.quant"])


def test_bam_reads_switch_on_salmons_transcript_fasta(tmp_path):
    registry, vocabulary = _world(tmp_path)
    goal = _goal("alignment.bam", "transcripts.fasta")
    states = _states(route(goal, registry))
    assert states["transcript_fasta"] is InputState.REQUIRED
    assert states["index"] is InputState.OFF
    ir = resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)
    node = next(n for n in ir.nodes if n.contract_id == SALMON_ID)
    assert {r.port: r.state for r in node.inputs}["transcript_fasta"] is InputState.REQUIRED


def test_fastq_reads_need_salmons_index(tmp_path):
    registry, vocabulary = _world(tmp_path)
    goal = _goal("fastq.reads", "salmon.index")
    states = _states(route(goal, registry))
    assert states["index"] is InputState.REQUIRED
    assert states["transcript_fasta"] is InputState.OFF
    resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)


def test_an_index_with_bam_reads_is_refused_with_the_reason(tmp_path):
    """Alignment mode forbids the index: a person switching it on is told why at build."""
    import pytest
    from comeni_core.goal.asked import Constraints, InputChoice
    from mendel_resolver.router import ConstraintViolation

    registry, vocabulary = _world(tmp_path)
    goal = Goal(have=[GoalInput(type_id=t) for t in ("alignment.bam", "transcripts.fasta",
                                                     "salmon.index")],
                want=["salmon.quant"],
                constraints=Constraints(inputs=[InputChoice(contract=SALMON_ID, port="index",
                                                            state=InputState.REQUIRED)]))
    with pytest.raises(ConstraintViolation, match="MD0610.*index.*alignment.bam"):
        resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)


# ── the router and resolution agree on the connected type (Task 5 review) ─────────────────

ALIGNER = """id: lab/aligner@1.0.0
nf_process: ALIGNER
nf_include: modules/lab/aligner/main
roles: [alignment]
consumes: [{name: reads, type_id: fastq.reads}]
produces: [{name: bam, type_id: alignment.bam}]
provenance: {source: t, drafted_by: t, approved_by: t, approved_at: "2026-11-10"}
"""
BAMQC = """id: lab/bamqc@1.0.0
nf_process: BAMQC
nf_include: modules/lab/bamqc/main
roles: [qc_per_sample]
consumes: [{name: bam, type_id: alignment.bam}]
produces: [{name: report, type_id: qc.report}]
provenance: {source: t, drafted_by: t, approved_by: t, approved_at: "2026-11-10"}
"""


def _roles(tmp_path: pathlib.Path, *ids: str) -> None:
    body = "declares: role\nroles:\n" + "".join(f"  - {{id: {i}, explain: x}}\n" for i in ids)
    (tmp_path / "roles.yml").write_text(body)


def test_a_held_earlier_alternative_wins_over_a_produced_later_one(tmp_path):
    """The goal has FASTQ; another branch makes a BAM. The router connects salmon's reads to
    the FASTQ (its first alternative) and switches the index on; resolution must wire the same
    FASTQ, not the BAM, or alignment mode refuses the index it was just given."""
    registry, vocabulary = _world(tmp_path)
    (tmp_path / "contracts" / "aligner.yml").write_text("declares: contract\n" + ALIGNER)
    (tmp_path / "contracts" / "bamqc.yml").write_text("declares: contract\n" + BAMQC)
    (tmp_path / "vocabularies" / "qc.report.yml").write_text(
        "declares: vocabulary\nid: qc.report\nstates: []\nscope: sample\n")
    _roles(tmp_path, "quantification", "alignment", "qc_per_sample")
    vocabulary = Vocabulary.load(tmp_path)
    registry = Registry.load(tmp_path, vocabulary)
    goal = Goal(have=[GoalInput(type_id="fastq.reads"), GoalInput(type_id="salmon.index")],
                want=["qc.report", "salmon.quant"])
    ir = resolve(goal, registry, RuleTable(), MeasurementRegistry(), vocabulary=vocabulary)
    salmon = next(n for n in ir.nodes if n.contract_id == SALMON_ID)
    assert not any(e.to_node == salmon.id and e.to_port == "reads" for e in ir.edges)
    assert {r.port: r.state for r in salmon.inputs}["index"] is InputState.REQUIRED


ORPHAN_TYPES = {"h.one": "sample", "m.mid": "sample", "q.opt": "run", "t.one": "sample",
                "t.two": "sample", "w.want": "sample"}
MAKER = """id: lab/maker@1.0.0
nf_process: MAKER
nf_include: modules/lab/maker/main
roles: [trimming]
consumes: [{name: h, type_id: h.one}]
produces: [{name: m, type_id: m.mid}]
provenance: {source: t, drafted_by: t, approved_by: t, approved_at: "2026-11-10"}
"""
ONE = """id: lab/one@1.0.0
nf_process: ONE
nf_include: modules/lab/one/main
roles: [alignment]
consumes:
  - {name: m, type_id: m.mid}
  - {name: q, type_id: q.opt, required: false}
produces: [{name: t, type_id: t.one, produced_when: {given.q: present}}]
nf_inputs: [{ports: [m]}, {ports: [q], absent: 2}]
provenance: {source: t, drafted_by: t, approved_by: t, approved_at: "2026-11-10"}
"""
WANTS = """id: lab/wants@1.0.0
nf_process: WANTS
nf_include: modules/lab/wants/main
roles: [quantification]
consumes: [{name: p, accepts: [{type_id: t.one}, {type_id: t.two}]}]
produces: [{name: w, type_id: w.want}]
provenance: {source: t, drafted_by: t, approved_by: t, approved_at: "2026-11-10"}
"""


def test_a_failed_alternative_leaves_no_steps_behind(tmp_path):
    """Task 5 review: required inputs are routed before optional ones are decided, so an
    alternative refused at that point (MD0609) had already emitted its upstream steps."""
    from comeni_core.goal.asked import Constraints, InputChoice

    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    for type_id, scope in ORPHAN_TYPES.items():
        family = type_id.split(".")[0]
        (vocab_dir / f"{type_id}.yml").write_text(
            f"declares: vocabulary\nid: {type_id}\nstates: []\nscope: {scope}\n")
        (vocab_dir / f"{family}.family.yml").write_text(
            f"declares: family\nid: {family}\ndescription: {family}\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    for name, body in {"maker.yml": MAKER, "one.yml": ONE, "wants.yml": WANTS}.items():
        (contracts / name).write_text("declares: contract\n" + body)
    _roles(tmp_path, "trimming", "alignment", "quantification")
    vocabulary = Vocabulary.load(tmp_path)
    registry = Registry.load(tmp_path, vocabulary)
    goal = Goal(have=[GoalInput(type_id="h.one"), GoalInput(type_id="t.two")], want=["w.want"],
                constraints=Constraints(inputs=[InputChoice(contract="lab/one@1.0.0", port="q",
                                                            state=InputState.OFF)]))
    plan = route(goal, registry)
    assert [s.contract_id for s in plan.steps] == ["lab/wants@1.0.0"]


REVISIT_TYPES = {"h.one": "sample", "c.out": "sample", "c.extra": "sample", "o.opt": "run",
                 "g.raw": "run", "e.two": "sample", "t.one": "sample", "t.two": "sample",
                 "w.want": "sample"}


def _contract(cid: str, consumes: str, produces: str, extra: str = "") -> str:
    name = cid.split("/")[1].split("@")[0]
    return (f"id: {cid}\nnf_process: {name.upper()}\nnf_include: modules/lab/{name}/main\n"
            f"roles: [trimming]\nconsumes: {consumes}\nproduces: {produces}\n{extra}"
            "provenance: {source: t, drafted_by: t, approved_by: t, approved_at: '2026-11-10'}\n")


def test_a_failed_alternative_undoes_a_revisit_that_switched_an_input_on(tmp_path):
    """Final review: a refused alternative revisited an earlier step, switched its optional
    input on and routed it; the rollback removed the routed step but left the input on."""
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    for type_id, scope in REVISIT_TYPES.items():
        family = type_id.split(".")[0]
        (vocab_dir / f"{type_id}.yml").write_text(
            f"declares: vocabulary\nid: {type_id}\nstates: []\nscope: {scope}\n")
        (vocab_dir / f"{family}.family.yml").write_text(
            f"declares: family\nid: {family}\ndescription: {family}\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    bodies = {
        "c.yml": _contract("lab/c@1.0.0",
                           "[{name: h, type_id: h.one}, "
                           "{name: o, type_id: o.opt, required: false}]",
                           "[{name: out, type_id: c.out}, "
                           "{name: extra, type_id: c.extra, produced_when: {given.o: present}}]",
                           "nf_inputs: [{ports: [h]}, {ports: [o], absent: 2}]\n"),
        "f.yml": _contract("lab/f@1.0.0", "[{name: g, type_id: g.raw}]",
                           "[{name: o, type_id: o.opt}]"),
        "e.yml": _contract("lab/e@1.0.0",
                           "[{name: extra, type_id: c.extra}, {name: two, type_id: e.two}]",
                           "[{name: t, type_id: t.one}]"),
        "x.yml": _contract("lab/x@1.0.0",
                           "[{name: c, type_id: c.out}, "
                           "{name: p, accepts: [{type_id: t.one}, {type_id: t.two}]}]",
                           "[{name: w, type_id: w.want}]"),
    }
    for name, body in bodies.items():
        (contracts / name).write_text("declares: contract\n" + body)
    _roles(tmp_path, "trimming")
    vocabulary = Vocabulary.load(tmp_path)
    registry = Registry.load(tmp_path, vocabulary)
    goal = Goal(have=[GoalInput(type_id=t) for t in ("h.one", "g.raw", "t.two")],
                want=["w.want"])
    plan = route(goal, registry)
    assert [s.contract_id for s in plan.steps] == ["lab/c@1.0.0", "lab/x@1.0.0"]
    c = next(s for s in plan.steps if s.contract_id == "lab/c@1.0.0")
    assert {r.port: r.state for r in c.inputs}["o"] is InputState.OFF
