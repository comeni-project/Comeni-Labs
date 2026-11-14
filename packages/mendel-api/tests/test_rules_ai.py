"""The `rule_proposal` model point (#462): one call, checked where the reply arrives, sent back
once with its problems. A fake client with recorded replies; no model is called."""

import json

import pytest
import sqlalchemy as sa
import yaml
from comeni_ai import ModelAccess
from comeni_core.artifact.pipeline import Pipeline
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation
from mendel_api.services import registry, rules_ai
from mendel_api_tests.database import reachable
from mendel_resolver.proposals import Case, cases_of
from mendel_resolver.rules import DecisionTarget
from support.paths import ROOT

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

STAR, HISAT2 = "nf-core/star/align@2.7.11b", "nf-core/hisat2/align@2.2.2"
ALIGNMENT = DecisionTarget(effect="implementation", of="alignment")


class Model:
    """Replies with each recorded reply in turn."""

    access = ModelAccess(model="fake/rules", base_url="http://local")
    last_prompt = last_response = last_refusal = last_usage = None

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def respond(self, prompt, shape, choices=None):
        self.last_prompt = prompt
        self.prompts.append(prompt)
        self.last_response = json.dumps(self.replies.pop(0))
        return shape.model_validate_json(self.last_response)


@pytest.fixture(autouse=True)
def clean():
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM ai_invocation WHERE prompt_id = 'rules.propose.v1'"))


def _cases(answers):
    return [Case(target=ALIGNMENT, facts=facts, answer=answer, pipeline=f"p{n}",
                 decision="alignment.bam", by_person=True, tier=4)
            for n, (facts, answer) in enumerate(answers)]


def _ask(cases, client):
    existing = next(d for d in registry.stack().rules.decisions
                    if d.key() == "implementation:alignment")
    facts = rules_ai.fact_kinds(cases, existing, registry.stack().measurements)
    return rules_ai.propose(ALIGNMENT, existing, cases, facts, [STAR, HISAT2], client)


def _row(when, then, because="people chose it"):
    return {"when": when, "then": then, "because": because}


def test_a_recorded_reply_becomes_rows_and_an_invocation():
    cases = _cases([({"paired": True}, HISAT2)] * 3)
    model = Model({"rows": [_row({"paired": True}, HISAT2)], "why": "all three were paired"})
    rows, why, invocation, problems = _ask(cases, model)
    assert problems == [] and why == "all three were paired"
    (row,) = rows
    assert row.when == {"paired": True, "read_length": "absent"} and row.then == HISAT2
    assert row.cite == "kept pipelines p0, p1, p2, decision alignment.bam"
    with session_scope() as db:
        recorded = db.get(AiInvocation, invocation)
        assert (recorded.agent, recorded.purpose, recorded.prompt_id) == (
            "forge", "analysis", "rules.propose.v1")
    assert "paired" in model.prompts[0] and STAR in model.prompts[0]


def test_a_row_contradicting_a_person_goes_back_once_then_fails():
    cases = _cases([({"paired": True}, HISAT2), ({"paired": True}, HISAT2),
                    ({"paired": True}, STAR)])
    wrong = {"rows": [_row({"paired": True}, HISAT2)], "why": "mostly hisat2"}
    model = Model(wrong, wrong)
    rows, _, _, problems = _ask(cases, model)
    assert rows == []
    assert problems == [f"p2 alignment.bam: a person chose {STAR}; the table would choose {HISAT2}"]
    assert len(model.prompts) == 2
    assert "a person chose" in model.prompts[1], "the second call is told why the first failed"
    with session_scope() as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(AiInvocation)
                         .where(AiInvocation.prompt_id == "rules.propose.v1")) == 2


def test_a_then_outside_the_legal_answers_is_refused():
    cases = _cases([({"paired": True}, HISAT2)] * 3)
    bad = {"rows": [_row({"paired": True}, "nf-core/bwa/mem@0.7.19")], "why": "x"}
    good = {"rows": [_row({"paired": True}, HISAT2)], "why": "y"}
    model = Model(bad, good)
    rows, why, _, problems = _ask(cases, model)
    assert problems == [] and why == "y" and len(rows) == 1
    assert "nf-core/bwa/mem@0.7.19 is not one of the legal answers" in model.prompts[1]


def test_a_fact_not_given_is_refused():
    cases = _cases([({"paired": True}, HISAT2)] * 3)
    bad = {"rows": [_row({"organism": "human"}, HISAT2)], "why": "x"}
    rows, _, _, problems = _ask(cases, Model(bad, bad))
    assert rows == [] and problems == ["row 1 tests organism, which is not one of the facts given"]


def test_no_rule_is_an_answer():
    cases = _cases([({"paired": True}, HISAT2), ({"paired": False}, STAR), ({}, HISAT2)])
    rows, why, invocation, problems = _ask(cases, Model({"rows": [], "why": "no pattern"}))
    assert (rows, why, problems) == ([], "no pattern", []) and invocation


def test_no_model_configured_says_so(monkeypatch):
    monkeypatch.setattr(rules_ai, "model_access", lambda *a: None)
    rows, _, invocation, problems = _ask(_cases([({"paired": True}, HISAT2)] * 3), None)
    assert (rows, invocation) == ([], None)
    assert problems and problems[0].startswith("MI0501")


def test_the_payload_holds_no_sample_names():
    data = yaml.safe_load((ROOT / "tests/fixtures/pipeline-v9/pipeline.yml").read_text())
    data["facts"]["measurements"].append(
        {"measurement": "read_length", "value": [101, 151], "source": "said"})
    data["facts"]["measurements"] = [m for m in data["facts"]["measurements"]
                                     if not (m["measurement"] == "read_length"
                                             and m["value"] == 150)]
    data["decisions"] = [{"key": "alignment.bam", "subject": "alignment.bam", "kind": "producer",
                          "reason": "asked", "resolved_by": "flag-only", "tier": 4,
                          "candidates": [STAR, HISAT2], "chosen": HISAT2,
                          "human_override": HISAT2}]
    pipeline = Pipeline.model_validate(data)
    cases = [case for n in range(3) for case in
             cases_of(pipeline, registry.stack().registry, f"kept{n}")]
    model = Model({"rows": [_row({"paired": True}, HISAT2)], "why": "paired"})
    _ask(cases, model)
    prompt = model.prompts[0]
    assert "paired" in prompt
    for private in ("101", "151", "genome.fasta", "fastq.reads", "trimgalore", "kept0"):
        assert private not in prompt, private


def test_a_learned_rows_citation_does_not_reach_the_model():
    """Review I2: a learned row's `cite` names kept pipelines; the payload carries no ids."""
    existing = next(d for d in registry.stack().rules.decisions
                    if d.key() == "implementation:alignment")
    learned = existing.model_copy(update={"rows": [*existing.rows, existing.rows[0].model_copy(
        update={"when": {"paired": False, "read_length": "absent"},
                "cite": "kept pipelines kept0secret, decision alignment.bam"})]})
    cases = _cases([({"paired": True}, HISAT2)] * 3)
    model = Model({"rows": [_row({"paired": True}, HISAT2)], "why": "paired"})
    facts = rules_ai.fact_kinds(cases, learned, registry.stack().measurements)
    rules_ai.propose(ALIGNMENT, learned, cases, facts, [STAR, HISAT2], model)
    assert "kept0secret" not in model.prompts[0]
    assert "Dobin" not in model.prompts[0], "no row's cite is sent"


def test_a_malformed_test_is_sent_back_not_raised():
    """Review I1: `{"in": 5}` is a valid predicate shape that raises when evaluated."""
    cases = _cases([({"paired": True}, HISAT2)] * 3)
    bad = {"rows": [_row({"paired": {"in": 5}}, HISAT2)], "why": "x"}
    rows, _, _, problems = _ask(cases, Model(bad, bad))
    assert rows == [] and problems and problems[0].startswith("row 1 cannot be evaluated")


def test_a_then_of_one_is_not_the_legal_answer_true():
    """Issue 489: `1 in [False, True]` is true in Python."""
    target = DecisionTarget(effect="param", of="bam_sorting", name="index_format",
                            when_implementation=["nf-core/samtools/sort@1.24"])
    cases = [Case(target=target, facts={"paired": True}, answer=True, pipeline=f"p{n}",
                  decision="samtools_sort.index_format", by_person=True, tier=4)
             for n in range(3)]
    bad = {"rows": [_row({"paired": True}, 1)], "why": "x"}
    facts = rules_ai.fact_kinds(cases, None, registry.stack().measurements)
    rows, _, _, problems = rules_ai.propose(target, None, cases, facts, [False, True],
                                            Model(bad, bad))
    assert rows == [] and problems == ["row 1: 1 is not one of the legal answers"]


class Unreachable(Model):
    """The provider timed out: no reply arrived at all."""

    def respond(self, prompt, shape, choices=None):
        self.prompts.append(prompt)
        self.last_prompt, self.last_response = prompt, None
        self.last_refusal = "the model did not answer in time"
        return None


def test_a_model_that_never_answered_leaves_nothing_to_store():
    """Issue 489: a timeout is not the model refusing; the target is asked again next time."""
    model = Unreachable()
    rows, _, invocation, problems = _ask(_cases([({"paired": True}, HISAT2)] * 3), model)
    assert (rows, invocation) == ([], None) and len(model.prompts) == 1
    assert problems == ["the model did not answer in time"]
