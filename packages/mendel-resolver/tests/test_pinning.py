import pathlib

import pytest
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.plan.ir import Tier
from mendel_resolver.router import UnroutablePinError

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
    # `tools/nf-core/fastqc/contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


def test_a_sole_producer_is_structural(spine):
    """`fastqc` is the only thing producing a bare `qc.report` — multiqc's carries
    `aggregated`, so it has a surplus and is not an alternative to it. No choice exists."""
    ir = spine(want=["qc.report"])
    node = next(n for n in ir.nodes if n.id == "fastqc")
    assert node.selection.tier is Tier.STRUCTURAL


def test_a_rule_pinned_producer_is_data_profiled_and_cites(spine):
    ir = spine(want=["alignment.bam"], profile={"read_length": 150})
    node = next(n for n in ir.nodes if n.id == "star_align")
    assert node.selection.tier is Tier.DATA_PROFILED
    assert "Dobin" in node.selection.reason


def test_a_short_read_profile_pins_the_other_aligner(spine):
    """The row that had never fired in the history of this repository."""
    ir = spine(want=["alignment.bam"], profile={"read_length": 50})
    assert "hisat2_align" in [n.id for n in ir.nodes]
    assert "star_align" not in [n.id for n in ir.nodes]


def test_a_priority_resolved_choice_is_convention(spine):
    """No profile, so no rule fires: star and hisat2 tie on surplus and priority breaks it."""
    ir = spine(want=["alignment.bam"], profile={})
    node = next(n for n in ir.nodes if n.id == "star_align")
    assert node.selection.tier is Tier.CONVENTION
    assert "priority" in node.selection.reason


def test_a_pin_that_cannot_route_raises_naming_the_rule(spine_without_hisat2_index):
    with pytest.raises(UnroutablePinError, match="read_length"):
        spine_without_hisat2_index(want=["alignment.bam"], profile={"read_length": 50})


def test_a_pin_does_not_apply_where_its_contract_cannot_produce_what_was_asked(spine):
    """`samtools/sort` is the only producer of a *coordinate-sorted* BAM.

    The rule pins star for `alignment.bam`, but star cannot emit that state at all, so
    the rule is not about this routing site — it applies one level down, on the sorter's
    own BAM input, where star genuinely is a candidate. Treating the pin as binding
    everywhere would make the spine unbuildable.
    """
    ir = spine(want=["counts.matrix"], profile={"read_length": 150})
    sort = next(n for n in ir.nodes if n.id == "samtools_sort")
    star = next(n for n in ir.nodes if n.id == "star_align")
    # Tier **2** since Plan 1.15 Task 7, not tier 1: the sorter is uncontested because this
    # stack holds one contract that sorts, which is a fact about the registry rather than
    # about the inputs. Its *presence* is what the inputs force, and that is tier 1 — A113.
    assert sort.selection.tier is Tier.CONVENTION
    assert sort.presence.tier is Tier.STRUCTURAL
    assert star.selection.tier is Tier.DATA_PROFILED


def test_the_selection_records_which_contract_was_chosen(spine):
    ir = spine(want=["qc.report"])
    node = next(n for n in ir.nodes if n.id == "fastqc")
    assert node.selection.value == "nf-core/fastqc@0.12.1"


def test_a_genuine_tie_is_ambiguous_and_reaches_the_review_list(tmp_path):
    """Invariant 8 for module choice, now visible as a tier on the node itself."""
    import pathlib

    from comeni_core.declared.registry import Registry
    from comeni_core.declared.vocabulary import Vocabulary
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve
    from mendel_resolver.rules import RuleTable

    layer = pathlib.Path(__file__).parents[3] / "registry"
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    original = (layer / "tools" / "nf-core" / "trimgalore" / "contract.yml").read_text()
    (contracts / "trimgalore.yml").write_text(_declared(contracts / "trimgalore.yml", original))
    # Same priority, same output, different module key: nothing distinguishes them.
    (contracts / "fastp.yml").write_text(
        _declared(
            contracts / "fastp.yml",
            original.replace("nf-core/trimgalore@0.6.10", "nf-core/fastp@0.24.0").replace(
            "TRIMGALORE", "FASTP"
        ))
    )
    vocabulary = Vocabulary.load(layer)
    registry = Registry.load(tmp_path, vocabulary)
    ir = resolve(
        Goal(have=[GoalInput(type_id="fastq.reads")], want=["fastq.reads"],
             constraints={"required_states": {"fastq.reads": ["trimmed"]}}),
        registry,
        RuleTable(),
        MeasurementRegistry(),
        vocabulary=vocabulary,
    )
    chosen = ir.nodes[0]
    assert chosen.selection.tier is Tier.AMBIGUOUS
    assert ir.needs_review() != []
