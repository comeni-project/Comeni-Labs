import pytest
from comeni_core.ir import Tier
from comeni_core.measurement import MeasurementRegistry
from mendel_resolver.router import UnroutablePinError


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
    assert sort.selection.tier is Tier.STRUCTURAL
    assert star.selection.tier is Tier.DATA_PROFILED


def test_the_selection_records_which_contract_was_chosen(spine):
    ir = spine(want=["qc.report"])
    node = next(n for n in ir.nodes if n.id == "fastqc")
    assert node.selection.value == "nf-core/fastqc@0.12.1"


def test_a_genuine_tie_is_ambiguous_and_reaches_the_review_list(tmp_path):
    """Invariant 8 for module choice, now visible as a tier on the node itself."""
    import pathlib

    from comeni_core.registry import Registry
    from comeni_core.vocabulary import Vocabulary
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve
    from mendel_resolver.rules import RuleTable

    layer = pathlib.Path(__file__).parents[3] / "registry"
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    original = (layer / "contracts" / "nf-core" / "trimgalore.yml").read_text()
    (contracts / "trimgalore.yml").write_text(original)
    # Same priority, same output, different module key: nothing distinguishes them.
    (contracts / "fastp.yml").write_text(
        original.replace("nf-core/trimgalore@0.6.10", "nf-core/fastp@0.24.0").replace(
            "TRIMGALORE", "FASTP"
        )
    )
    vocabulary = Vocabulary.load(layer)
    registry = Registry.load(tmp_path, vocabulary)
    ir = resolve(
        Goal(have=[GoalInput(type_id="fastq.reads")], want=["fastq.reads"],
             constraints={"required_states": {"fastq.reads": ["trimmed"]}}),
        registry,
        RuleTable(),
        MeasurementRegistry(),
    )
    chosen = ir.nodes[0]
    assert chosen.selection.tier is Tier.AMBIGUOUS
    assert ir.needs_review() != []
