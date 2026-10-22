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
