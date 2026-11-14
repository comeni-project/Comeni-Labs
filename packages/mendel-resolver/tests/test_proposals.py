"""Rule proposals from people's answers (#462): the cases, the engine's judge and the replay.

Pure: a saved pipeline and the shipped registry in, records out. No model is called here; the
model's part is `mendel_api.services.rules_ai`, and its rows are judged by these functions."""

import pathlib

import pytest
import yaml
from comeni_core.artifact.pipeline import Pipeline
from mendel_resolver import layers
from mendel_resolver.proposals import (
    MIN_CASES,
    Case,
    Replayed,
    cases_of,
    cite_for,
    evidence,
    evidence_digest,
    judge,
    replay,
    table_with,
)
from mendel_resolver.rules import DecisionRow, DecisionTarget

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


# ---------------- the engine's judge ----------------

ALIGNMENT = DecisionTarget(effect="implementation", of="alignment")


def _cases(answers, *, person=True, tier=4):
    """One case per (pipeline, facts, answer)."""
    return [Case(target=ALIGNMENT, facts=facts, answer=answer, pipeline=pid,
                 decision="alignment.bam", by_person=person, tier=tier)
            for pid, facts, answer in answers]


def _rows(*rows):
    return [DecisionRow(when=when, then=then, because="people chose it") for when, then in rows]


def existing_alignment():
    stack = layers.load(ROOT / "registry")
    return next(d for d in stack.rules.decisions if d.key() == "implementation:alignment")


def test_a_row_agreeing_with_every_answer_is_sound():
    cases = _cases([(f"p{n}", {"organism": "human"}, STAR) for n in range(3)])
    new = _rows(({"organism": "human"}, STAR))
    table = table_with(ALIGNMENT, None, new, cite_for(cases))
    assert judge(table, new, cases) == []
    assert table.because == "learned from people's answers"
    assert [row.cite for row in table.rows] == ["kept pipelines p0, p1, p2, decision alignment.bam"]


def test_a_row_overturning_a_person_is_refused_and_names_the_case():
    cases = _cases([("p0", {}, STAR), ("p1", {}, STAR), ("p2", {}, HISAT2)])
    new = _rows(({}, STAR))
    problems = judge(table_with(ALIGNMENT, None, new, cite_for(cases)), new, cases)
    assert problems == [f"p2 alignment.bam: a person chose {HISAT2}; the table would choose {STAR}"]


def test_an_invented_row_is_refused():
    cases = _cases([(f"p{n}", {"organism": "human"}, STAR) for n in range(3)])
    new = _rows(({"organism": "human"}, STAR), ({"organism": "mouse"}, HISAT2))
    problems = judge(table_with(ALIGNMENT, None, new, cite_for(cases)), new, cases)
    assert problems == ["row 2 matches none of the answers it was drafted from"]


def test_existing_rows_stay_first():
    existing = existing_alignment()
    cases = _cases([(f"p{n}", {"read_length": 150}, STAR) for n in range(3)])
    new = _rows(({"read_length": ">= 100"}, STAR))
    table = table_with(ALIGNMENT, existing, new, cite_for(cases))
    assert table.rows[:2] == existing.rows and table.rows[2].when == {"read_length": ">= 100"}
    assert table.because == existing.because
    assert judge(table, new, cases) == [
        "row 1 never fires: an earlier row settles every case it matches"]


def test_a_threshold_row_is_judged_by_its_comparison():
    cases = _cases([("p0", {"organism": "human", "insert": 300}, STAR),
                    ("p1", {"organism": "human", "insert": 250}, STAR),
                    ("p2", {"organism": "human", "insert": 90}, HISAT2)])
    sound = _rows(({"insert": ">= 100"}, STAR), ({"insert": "< 100"}, HISAT2))
    assert judge(table_with(ALIGNMENT, None, sound, cite_for(cases)), sound, cases) == []
    loose = _rows(({"insert": ">= 50"}, STAR))
    assert judge(table_with(ALIGNMENT, None, loose, cite_for(cases)), loose, cases) == [
        f"p2 alignment.bam: a person chose {HISAT2}; the table would choose {STAR}"]


# ---------------- the replay ----------------


def test_replay_lists_what_the_rows_would_settle():
    cases = _cases([(f"p{n}", {"organism": "human"}, STAR) for n in range(3)])
    cases += _cases([("p9", {"organism": "mouse"}, HISAT2)])
    new = _rows(({"organism": "human"}, STAR))
    replayed = replay(table_with(ALIGNMENT, None, new, "c"), new, cases)
    assert [(r.pipeline, r.recorded, r.would, r.agrees, r.by_person) for r in replayed] == [
        (f"p{n}", STAR, STAR, True, True) for n in range(3)]
    assert all(isinstance(r, Replayed) for r in replayed)


def test_replay_shows_a_models_answer_it_would_change_first():
    cases = _cases([(f"p{n}", {"organism": "human"}, STAR) for n in range(3)])
    cases += _cases([("p8", {"organism": "human"}, HISAT2)], person=False)
    new = _rows(({"organism": "human"}, STAR))
    replayed = replay(table_with(ALIGNMENT, None, new, "c"), new, cases)
    assert replayed, "the replay found the cases"
    first = replayed[0]
    assert (first.pipeline, first.recorded, first.would, first.agrees, first.by_person) == (
        "p8", HISAT2, STAR, False, False)
    assert [r.pipeline for r in replayed[1:]] == ["p0", "p1", "p2"]


def test_replay_skips_cases_an_existing_row_settles():
    cases = _cases([("p0", {"read_length": 150}, STAR)], tier=3, person=False)
    cases += _cases([(f"q{n}", {"organism": "human"}, STAR) for n in range(3)])
    new = _rows(({"organism": "human"}, STAR))
    replayed = replay(table_with(ALIGNMENT, existing_alignment(), new, "c"), new, cases)
    assert [r.pipeline for r in replayed] == ["q0", "q1", "q2"]
