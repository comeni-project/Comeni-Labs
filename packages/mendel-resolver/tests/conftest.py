import pathlib

import pytest
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.resolve import resolve
from mendel_resolver.rules import RuleTable

ROOT = pathlib.Path(__file__).parents[3]
EXAMPLES = ROOT / "examples"


def _spine(contracts: pathlib.Path):
    """A resolver over `examples/`, with the contract tree swapped out if asked."""
    vocabulary = Vocabulary.load(EXAMPLES / "vocabularies")
    registry = Registry.load(contracts, vocabulary)
    measurements = MeasurementRegistry.load(EXAMPLES / "measurements")
    rules = RuleTable.load(
        EXAMPLES / "rules",
        registry=registry,
        vocabulary=vocabulary,
        measurements=measurements,
    )

    def build(*, want, profile=None, have=("fastq.reads", "annotation.gtf")):
        goal = Goal(
            have=[GoalInput(type_id=t) for t in have],
            want=want,
            profile=measurements.profile(profile or {}),
        )
        return resolve(goal, registry, rules)

    return build


@pytest.fixture
def spine():
    return _spine(EXAMPLES / "contracts")


@pytest.fixture
def spine_without_hisat2_index(tmp_path):
    """The same registry with `hisat2/build` removed.

    HISAT2_ALIGN still produces `alignment.bam`, so a rule pinning it still selects it —
    but nothing can build its index any more, so the pin leads somewhere unreachable.
    That is the case the router must refuse loudly rather than quietly re-ranking.
    """
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    for path in sorted((EXAMPLES / "contracts").rglob("*.yml")):
        if path.stem == "hisat2-build":
            continue
        (contracts / path.name).write_text(path.read_text())
    return _spine(contracts)
