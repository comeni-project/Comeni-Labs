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
        return resolve(goal, loaded.registry, loaded.rules)

    return build


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
    next(layer.rglob("hisat2-build.yml")).unlink()
    return _spine(layer)
