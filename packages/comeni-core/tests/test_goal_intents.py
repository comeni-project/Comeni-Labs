"""A person's structural intent in the goal (A1, the one-builder design): a role switched off, a
tool excluded at a site, and a port's source pinned."""

import pytest
from comeni_core.artifact.pipeline import SCHEMA_VERSION, Pipeline
from comeni_core.goal.asked import (
    Constraints,
    ProducerExclusion,
    RoleAbsence,
    Site,
    SourcePin,
)
from pydantic import ValidationError

STAR = "nf-core/star/align@1.11.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"
SORT = "nf-core/samtools/sort@1.21.0"
DEDUP = "lab/markdup@1.0.0"


def test_a_goal_without_intents_dumps_the_bytes_it_did():
    """Invariant 10: no `absent_roles: []`, `exclusions: []` or `sources: []` appears."""
    dumped = Constraints().model_dump(mode="json")
    assert not {"absent_roles", "exclusions", "sources"} & set(dumped)


def test_intents_round_trip_with_sorted_states():
    constraints = Constraints(
        absent_roles=[RoleAbsence(role="trimming")],
        exclusions=[ProducerExclusion(
            site=Site(type_id="alignment.bam", states=frozenset({"b", "a"})), contract=STAR)],
        sources=[SourcePin(consumer=COUNTS, port="bam", producer=SORT)],
    )
    dumped = constraints.model_dump(mode="json")
    assert dumped["exclusions"][0]["site"]["states"] == ["a", "b"]
    assert Constraints.model_validate(dumped) == constraints


def test_an_unknown_field_is_refused():
    with pytest.raises(ValidationError):
        RoleAbsence.model_validate({"role": "trimming", "why": "x"})


def test_what_is_excluded_at_a_site_is_read_there_only():
    site = Site(type_id="alignment.bam")
    other = Site(type_id="alignment.bam", states=frozenset({"coordinate_sorted"}))
    constraints = Constraints(exclusions=[ProducerExclusion(site=site, contract=STAR)])
    assert constraints.excluded_at(site) == frozenset({STAR})
    assert constraints.excluded_at(other) == frozenset()


def test_the_later_source_pin_at_a_port_wins():
    first = SourcePin(consumer=COUNTS, port="bam", producer=SORT)
    last = SourcePin(consumer=COUNTS, port="bam", producer=DEDUP)
    assert Constraints(sources=[first, last]).source_at(COUNTS, "bam") == last
    assert Constraints(sources=[first, last]).source_at(COUNTS, "gtf") is None


def test_the_roles_switched_off_are_a_set():
    constraints = Constraints(absent_roles=[RoleAbsence(role="trimming"),
                                            RoleAbsence(role="trimming")])
    assert constraints.roles_absent() == frozenset({"trimming"})


def test_the_pipeline_file_is_version_8_and_7_is_refused():
    assert SCHEMA_VERSION == 8
    with pytest.raises(ValidationError, match="8"):
        Pipeline.model_validate({"version": 7})
