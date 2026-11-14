"""Rule proposals from people's answers (#462): the cases, the engine's judge and the replay.

Pure: a saved pipeline and the shipped registry in, records out. No model is called here; the
model's part is `mendel_api.services.rules_ai`, and its rows are judged by these functions."""

import pathlib

import pytest
import yaml
from comeni_core.artifact.pipeline import Pipeline
from mendel_resolver import layers
from mendel_resolver.proposals import MIN_CASES, Case, cases_of, evidence, evidence_digest
from mendel_resolver.rules import DecisionTarget

ROOT = pathlib.Path(__file__).parents[3]
FIXTURE = ROOT / "tests/fixtures/pipeline-v9/pipeline.yml"
STAR, HISAT2 = "nf-core/star/align@2.7.11b", "nf-core/hisat2/align@2.2.2"
SORT = "nf-core/samtools/sort@1.24"


@pytest.fixture(scope="module")
def registry():
    return layers.load(ROOT / "registry").registry


def _producer(chosen=STAR, *, person=True, candidates=(STAR, HISAT2), tier=4, key="alignment.bam"):
    record = {"key": key, "subject": key, "kind": "producer", "reason": "asked",
              "resolved_by": "flag-only", "tier": tier, "candidates": list(candidates),
              "chosen": chosen}
    if person:
        record["human_override"] = chosen
    else:
        record |= {"model_override": chosen, "model_override_by": "fake/model"}
    return record


def _setting(chosen, *, because="", key="samtools_sort.index_format"):
    return {"key": key, "subject": key.split(".")[1], "kind": "param", "reason": "asked",
            "resolved_by": "flag-only", "tier": 4, "candidates": ["bai", "csi"],
            "chosen": chosen, "human_override": chosen, "override_reason": because}


def pipeline(decisions, facts=None) -> Pipeline:
    data = yaml.safe_load(FIXTURE.read_text())
    data["decisions"] = decisions
    if facts is not None:
        data["facts"]["measurements"] = [
            {"measurement": name, "value": value, "source": "said"}
            for name, value in facts.items()]
    return Pipeline.model_validate(data)


def test_a_persons_tool_choice_is_evidence(registry):
    (case,) = cases_of(pipeline([_producer()], {"read_length": 150}), registry, "p1")
    assert case.target == DecisionTarget(effect="implementation", of="alignment")
    assert case.target_key == "implementation:alignment"
    assert case.facts == {"read_length": 150}
    assert case.answer == STAR and case.by_person and case.tier == 4
    assert case.pipeline == "p1" and case.decision == "alignment.bam"
    assert case.evidence


def test_a_models_answer_is_a_case_but_not_evidence(registry):
    (case,) = cases_of(pipeline([_producer(person=False)]), registry, "p1")
    assert not case.by_person and not case.evidence
    assert cases_of(pipeline([_producer(candidates=(STAR,))]), registry, "p1") == [], \
        "a tool drawn with no alternative is not a choice"


def test_candidates_sharing_no_single_role_are_skipped(registry):
    assert cases_of(pipeline([_producer(candidates=(STAR, SORT))]), registry, "p1") == []


def test_a_setting_answer_names_its_tool(registry):
    (case,) = cases_of(pipeline([_setting("bai", because="our tools read bai")]), registry, "p1")
    assert case.target == DecisionTarget(effect="param", of="bam_sorting", name="index_format",
                                         when_implementation=[SORT])
    assert case.answer == "bai" and case.reason == "our tools read bai"


def test_per_sample_facts_are_left_out(registry):
    (case,) = cases_of(pipeline([_producer()], {"read_length": [100, 150], "paired": True}),
                       registry, "p1")
    assert case.facts == {"paired": True}


def test_evidence_needs_three_answers_and_its_digest_is_stable_under_order(registry):
    cases = [case for n in range(MIN_CASES) for case in
             cases_of(pipeline([_producer()], {"read_length": 150}), registry, f"p{n}")]
    assert MIN_CASES == 3
    assert evidence(cases[:-1]) == {}
    grouped = evidence(cases)
    assert list(grouped) == ["implementation:alignment"]
    assert len(grouped["implementation:alignment"]) == MIN_CASES
    assert evidence_digest(cases) == evidence_digest(list(reversed(cases)))
    assert evidence_digest(cases) != evidence_digest(cases[:-1])
    assert evidence_digest(cases).startswith("sha256:")
    assert all(isinstance(case, Case) for case in cases)
