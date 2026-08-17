import pytest
from mendel_forge.observe import Excerpt, Fact, Observation
from pydantic import ValidationError


def test_a_fact_carries_where_it_came_from():
    fact = Fact(value="FASTQC", evidence=Excerpt(locator="main.nf:12", text="process FASTQC {"))
    assert fact.value == "FASTQC"
    assert fact.evidence.locator == "main.nf:12"


def test_an_observation_looks_a_fact_up_and_returns_none_for_an_absent_one():
    obs = Observation(
        source="nf-core",
        ref_id="nf-core/fastqc",
        facts={"process": Fact(value="FASTQC", evidence=Excerpt(locator="main.nf:12", text="x"))},
    )
    assert obs.fact("process") == "FASTQC"
    assert obs.fact("container") is None


def test_evidence_is_mandatory_on_every_fact():
    """A fact with no locator is an assertion, which is what the forge exists not to make."""
    with pytest.raises(ValidationError):
        Fact(value="FASTQC")


def test_an_observation_serialises_with_its_facts_in_sorted_order():
    obs = Observation(
        source="s",
        ref_id="r",
        facts={
            "zebra": Fact(value=1, evidence=Excerpt(locator="a:1", text="t")),
            "alpha": Fact(value=2, evidence=Excerpt(locator="a:2", text="t")),
        },
    )
    assert list(obs.model_dump()["facts"]) == ["alpha", "zebra"]
