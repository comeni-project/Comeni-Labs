"""Shared mendel_resolver_tests declarations and helpers; collected tests remain separate."""

import pathlib

import pytest
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.plan.decision import Ambiguity, Resolution
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.rules import RuleTable

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/fastqc.contract.yml` sits two levels down from the directory that
    # names it.
    kind = next((_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None)
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


ALIGNER = """
id: audit/aligner-{tag}@1.0.0
nf_process: ALIGNER_{upper}
nf_include: modules/audit/aligner-{tag}/main
consumes: [{{name: reads, type_id: fastq.reads, state_required: []}}]
produces: [{{name: bam, type_id: alignment.bam, state: []}}]
priority: 0
provenance: {{source: audit, drafted_by: audit, approved_by: audit, approved_at: "2026-08-06"}}
"""


class _PicksLast:
    """Chooses the *last* candidate — disagrees with `router._choose`, which took `ordered[0]`.

    `FlagOnlyResolver` picks the first, which is what the router picked anyway. The two
    agreeing is precisely what hid A8, so every test here needs a resolver that does not.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        return Resolution(
            value=ambiguity.candidates[-1],
            why="audit fixture: deliberately not the first candidate",
            confidence=1.0,
            by="audit",
        )


class _PicksFirst:
    """Chooses the *first* candidate — disagrees with `_source_for`, which took the last.

    The two sites defaulted in opposite directions: `_choose` kept `ordered[0]` and
    `_source_for` kept `equally_good[-1]`. So one fixture cannot disagree with both, and
    using `_PicksLast` on a source ambiguity silently agrees with the bug — which is how
    the first version of these tests passed against unfixed code.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        return Resolution(
            value=ambiguity.candidates[0],
            why="audit fixture: deliberately not the last candidate",
            confidence=1.0,
            by="audit",
        )


@pytest.fixture
def tied(tmp_path):
    """Two aligners nothing distinguishes: a genuine tie, so tier 4 and a record."""
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "fastq.reads.yml").write_text(
        _declared(vocab_dir / "fastq.reads.yml", "states: []\n")
    )
    (vocab_dir / "alignment.bam.yml").write_text(
        _declared(vocab_dir / "alignment.bam.yml", "states: []\n")
    )
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "a.yml").write_text(
        _declared(contracts / "a.yml", ALIGNER.format(tag="a", upper="A"))
    )
    (contracts / "b.yml").write_text(
        _declared(contracts / "b.yml", ALIGNER.format(tag="b", upper="B"))
    )
    vocabulary = Vocabulary.load(tmp_path)
    return Registry.load(tmp_path, vocabulary), RuleTable(), MeasurementRegistry(), vocabulary


def _goal():
    return Goal(have=[GoalInput(type_id="fastq.reads")], want=["alignment.bam"])


DUAL = """
id: audit/dual@1.0.0
nf_process: DUAL
nf_include: modules/audit/dual/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces:
  - {name: bam, type_id: alignment.bam, state: []}
  - {name: bam_transcriptome, type_id: alignment.bam, state: []}
priority: 0
provenance: {source: audit, drafted_by: audit, approved_by: audit, approved_at: "2026-08-06"}
"""


COUNTER = """
id: audit/counter@1.0.0
nf_process: COUNTER
nf_include: modules/audit/counter/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: counts, type_id: counts.matrix, state: []}]
priority: 0
provenance: {source: audit, drafted_by: audit, approved_by: audit, approved_at: "2026-08-06"}
"""


@pytest.fixture
def two_equally_good_sources(tmp_path):
    """One producer, two ports of the same type — the shape that makes `_source_for` choose.

    Two *contracts* would not do it: only one of them gets routed, so `produced` holds one
    candidate and the ambiguity never arises. That is why the first version of this test
    passed against the bug — it asserted over an empty loop. Real: STAR emits a genomic
    and a transcriptomic BAM, and which one a counter should read is a genuine question.
    """
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    for type_id in ("fastq.reads", "alignment.bam", "counts.matrix"):
        (vocab_dir / f"{type_id}.yml").write_text(
            _declared(vocab_dir / f"{type_id}.yml", "states: []\n")
        )
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "dual.yml").write_text(_declared(contracts / "dual.yml", DUAL))
    (contracts / "counter.yml").write_text(_declared(contracts / "counter.yml", COUNTER))
    vocabulary = Vocabulary.load(tmp_path)
    return Registry.load(tmp_path, vocabulary), vocabulary
