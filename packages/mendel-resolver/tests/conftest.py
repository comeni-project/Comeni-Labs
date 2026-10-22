import pathlib
import shutil

import pytest
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve

ROOT = pathlib.Path(__file__).parents[3]
EXAMPLES = ROOT / "registry"


def _spine(layer: pathlib.Path):
    """A resolver over a registry layer — `registry/`, or a doctored copy of it."""
    loaded = layers.load(layer)

    def build(*, want, profile=None, have=("fastq.reads", "annotation.gtf", "genome.fasta")):
        goal = Goal(
            have=[GoalInput(type_id=t) for t in have],
            want=want,
            profile=loaded.measurements.profile(profile or {}),
        )
        return resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )

    return build


@pytest.fixture(scope="session")
def stack():
    """The shipped registry, loaded once.

    `session` rather than `module` because `layers.load` is the 244ms function the performance
    audit found (A132) and three validate test files share this.
    """
    return layers.load(EXAMPLES)


@pytest.fixture
def spine():
    return _spine(EXAMPLES)


@pytest.fixture
def spine_without_hisat2_index(tmp_path):
    """The same registry with `hisat2/build` removed.

    HISAT2_ALIGN still produces `alignment.bam`, so a rule pinning it still selects it —
    but nothing can build its index any more, so the pin leads somewhere unreachable.
    That is the case the router must refuse loudly rather than quietly re-ranking.
    """
    layer = tmp_path / "layer"
    shutil.copytree(EXAMPLES, layer)
    (layer / "tools/nf-core/hisat2/build/contract.yml").unlink()
    return _spine(layer)


@pytest.fixture
def resolve_rnaseq(stack):
    """The rnaseq example resolved over the shipped registry, with a person's pins and
    structural intent (A1) written into its constraints."""
    from support.example import example_mapping

    def run(*, read_length=True, pins=(), absent_roles=(), exclusions=(), sources=(),
            resolver=None, profile=None):
        data = example_mapping()
        if not read_length:
            data["profile"].pop("read_length")
        if profile:
            data["profile"].update(profile)
        constraints = data.setdefault("constraints", {})
        for field, values in (("producers", pins), ("absent_roles", absent_roles),
                              ("exclusions", exclusions), ("sources", sources)):
            constraints[field] = [v.model_dump(mode="json") for v in values]
        return resolve(
            Goal.model_validate(data),
            stack.registry,
            stack.rules,
            stack.measurements,
            vocabulary=stack.vocabulary,
            resolver=resolver,
        )

    return run


MARKDUP = "lab/markdup@1.0.0"


@pytest.fixture
def resolve_with_markdup(tmp_path):
    """The rnaseq example over the shipped registry plus `lab/markdup`, a hand-written tool
    that makes a coordinate-sorted, deduplicated BAM from a sorted one (cloned from the sorter's
    folder). Nothing asks for deduplication, so it is in a plan only when a person puts it there:
    a source pin on featureCounts' `bam` port is an insertion (A1)."""
    from support.example import example_mapping

    layer = tmp_path / "layer"
    shutil.copytree(EXAMPLES, layer)
    markdup = layer / "tools" / "lab" / "markdup"
    shutil.copytree(EXAMPLES / "tools" / "nf-core" / "samtools" / "sort", markdup)
    contract = (markdup / "contract.yml").read_text()
    for old, new in (
        ("nf-core/samtools/sort@1.21.0", MARKDUP),
        ("roles: [bam_sorting]", "roles: []"),
        ("nf_process: SAMTOOLS_SORT", "nf_process: LAB_MARKDUP"),
        ("consumes: [{name: bam, type_id: alignment.bam, state_required: []}]",
         "consumes: [{name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}]"),
        ("produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]",
         "produces: [{name: bam, type_id: alignment.bam, "
         "state: [coordinate_sorted, deduplicated]}]"),
    ):
        assert old in contract, old
        contract = contract.replace(old, new)
    (markdup / "contract.yml").write_text(contract)
    module = (markdup / "module.yml").read_text()
    module = module.replace("id: nf-core/samtools/sort", "id: lab/markdup")
    (markdup / "module.yml").write_text(module)
    loaded = layers.load(layer)

    def run(*, sources=(), exclusions=(), absent_roles=()):
        data = example_mapping()
        constraints = data.setdefault("constraints", {})
        for field, values in (("sources", sources), ("exclusions", exclusions),
                              ("absent_roles", absent_roles)):
            constraints[field] = [v.model_dump(mode="json") for v in values]
        return resolve(Goal.model_validate(data), loaded.registry, loaded.rules,
                       loaded.measurements, vocabulary=loaded.vocabulary)

    run.registry = loaded.registry
    return run
