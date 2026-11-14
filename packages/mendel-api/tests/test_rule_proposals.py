"""Rule proposals end to end (#462): kept pipelines in, a proposal checked and replayed, an
approval written to the installation's own layer, and the next build settling the question by it.

A fake model with a recorded reply; no model is called."""

import json
import secrets
import shutil
import time
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
import yaml
from comeni_ai import ModelAccess
from comeni_core.artifact.pipeline import Pipeline
from comeni_flow.interpret import Refused
from mendel_api.db import session_scope
from mendel_api.models import PipelineDraft, RuleProposal
from mendel_api.services import blueprint, proposals, rules_ai
from mendel_api.settings import settings
from mendel_api_tests.database import reachable, truncate
from mendel_compiler import pipeline_file
from support.paths import ROOT

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

STAR, HISAT2 = "nf-core/star/align@2.7.11b", "nf-core/hisat2/align@2.2.2"
FIXTURE = ROOT / "tests/fixtures/pipeline-v9/pipeline.yml"
SLUG = "implementation-alignment"


class Model:
    access = ModelAccess(model="fake/rules", base_url="http://local")
    last_prompt = last_response = last_refusal = last_usage = None

    def __init__(self, reply=None):
        self.reply = reply or {"rows": [{"when": {"paired": True}, "then": HISAT2,
                                         "because": "our runs are paired"}],
                               "why": "every person chose HISAT2 on paired reads"}
        self.calls = 0

    def respond(self, prompt, shape, choices=None):
        self.calls += 1
        self.last_prompt = prompt
        self.last_response = json.dumps(self.reply)
        return shape.model_validate_json(self.last_response)


def _pipeline(answer=HISAT2) -> Pipeline:
    data = yaml.safe_load(FIXTURE.read_text())
    data["facts"]["measurements"] = [m for m in data["facts"]["measurements"]
                                     if m["measurement"] != "read_length"]
    data["decisions"] = [{"key": "alignment.bam", "subject": "alignment.bam", "kind": "producer",
                          "reason": "asked", "resolved_by": "flag-only", "tier": 4,
                          "candidates": [STAR, HISAT2], "chosen": answer,
                          "human_override": answer}]
    return Pipeline.model_validate(data)


def keep(answer=HISAT2) -> str:
    """A kept draft: its row, and its `pipeline.yml` where `keep` writes it."""
    draft_id = secrets.token_hex(16)
    pipeline = _pipeline(answer)
    (settings.draft_root / draft_id).mkdir(parents=True)
    pipeline_file.write(settings.draft_root / draft_id, pipeline)
    now = datetime.now(UTC)
    with session_scope() as db:
        db.add(PipelineDraft(id=draft_id, who="tester", name="d",
                             graph={"nodes": [], "edges": []}, updated_at=now, provenance={},
                             revision=0, kept_at=now, kept_digest=pipeline.content_digest()))
    return draft_id


@pytest.fixture(autouse=True)
def installation(tmp_path, monkeypatch):
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM rule_proposal"))
        db.execute(truncate("TRUNCATE TABLE pipeline_authoring_proposal, pipeline_authoring_turn, "
                            "pipeline_authoring_session, pipeline_draft, gate_run"))
        db.execute(sa.text("DELETE FROM ai_invocation WHERE prompt_id = 'rules.propose.v1'"))
    monkeypatch.setattr(settings, "draft_root", tmp_path / "drafts")
    monkeypatch.setattr(settings, "own_layer", tmp_path / "layer")
    proposals.kept.cache_clear() if hasattr(proposals.kept, "cache_clear") else None
    return tmp_path


@pytest.fixture
def three():
    return [keep() for _ in range(3)]


def _goal(tmp_path):
    starter = yaml.safe_load(settings.example_goal.read_text())
    starter["facts"]["measurements"] = [m for m in starter["facts"]["measurements"]
                                        if m["measurement"] != "read_length"]
    path = tmp_path / "goal.yml"
    path.write_text(yaml.safe_dump(starter))
    return pipeline_file.goal_from(path)


def _align(tmp_path):
    built, _ = blueprint.resolve(_goal(tmp_path))
    return next(step for step in built.pipeline.steps if step.id.endswith("align"))


def test_running_proposes_one_rule_with_evidence_check_and_replay(three):
    model = Model()
    assert proposals.run(model) == 1
    view = proposals.read()
    (proposal,) = view.proposals
    assert proposal.target_key == "implementation:alignment"
    assert proposal.why == "every person chose HISAT2 on paired reads"
    (row,) = proposal.rows
    assert row["when"] == {"paired": True, "read_length": "absent"} and row["then"] == HISAT2
    assert row["because"] == "our runs are paired"
    assert row["cite"].startswith("kept pipelines ")
    assert sorted(e.pipeline for e in proposal.evidence) == sorted(three)
    assert all(e.answer == HISAT2 for e in proposal.evidence)
    assert proposal.check == [] and not proposal.stale
    assert [r.agrees for r in proposal.replay] == [True, True, True]
    assert proposal.model == "fake/rules" and proposal.invocation


def test_approving_writes_the_learned_table_and_the_next_build_uses_it(three, installation):
    assert _align(installation).why.tier == 4, "asked before anything is learned"
    proposals.run(Model())
    (proposal,) = proposals.read().proposals
    proposals.approve(proposal.id, "rafael")
    learned = settings.own_layer / "rules/learned" / f"{SLUG}.yml"
    text = learned.read_text()
    assert "approved by rafael" in text and proposal.invocation in text
    assert all(pipeline in text for pipeline in three)
    align = _align(installation)
    assert align.module.contract_id == HISAT2 and align.why.tier == 3
    assert "kept pipelines" in align.why.model_dump_json()
    view = proposals.read()
    assert view.proposals == [] and [u.slug for u in view.in_use] == [SLUG]


def test_running_again_with_no_new_answers_asks_nothing(three):
    model = Model()
    proposals.run(model)
    assert proposals.run(model) == 0 and model.calls == 1


def test_a_rejected_proposal_is_not_asked_again_until_evidence_changes(three):
    model = Model()
    proposals.run(model)
    (proposal,) = proposals.read().proposals
    proposals.reject(proposal.id, "rafael")
    assert proposals.read().proposals == []
    assert proposals.run(model) == 0
    keep()
    assert proposals.run(model) == 1 and model.calls == 2


def test_a_new_answer_supersedes_an_open_proposal(three):
    proposals.run(Model())
    (first,) = proposals.read().proposals
    keep()
    proposals.run(Model())
    (second,) = proposals.read().proposals
    assert second.id != first.id
    with session_scope() as db:
        assert db.get(RuleProposal, first.id).status == "superseded"


def test_withdrawing_brings_the_question_back(three, installation):
    proposals.run(Model())
    (proposal,) = proposals.read().proposals
    proposals.approve(proposal.id, "rafael")
    assert _align(installation).why.tier == 3
    proposals.withdraw(SLUG, "rafael")
    assert not (settings.own_layer / "rules/learned" / f"{SLUG}.yml").exists()
    assert _align(installation).why.tier == 4
    assert proposals.read().in_use == []
    with session_scope() as db:
        assert db.get(RuleProposal, proposal.id).status == "withdrawn"


def test_a_stale_or_failing_proposal_cannot_be_approved(three):
    proposals.run(Model())
    (proposal,) = proposals.read().proposals
    keep()
    assert proposals.read().proposals[0].stale
    with pytest.raises(Refused, match="MI0500"):
        proposals.approve(proposal.id, "rafael")
    proposals.reject(proposal.id, "rafael")
    with pytest.raises(Refused, match="MI0500"):
        proposals.approve(proposal.id, "rafael")


def test_a_reply_the_engine_refuses_twice_is_listed_as_not_proposed(three):
    wrong = Model({"rows": [{"when": {"paired": True}, "then": STAR, "because": "x"}],
                   "why": "x"})
    assert proposals.run(wrong) == 1
    view = proposals.read()
    assert view.proposals == []
    (refused,) = view.refused
    assert refused.status == "refused" and "a person chose" in refused.problems[0]


@pytest.mark.asyncio
async def test_no_model_refuses_to_start(monkeypatch):
    monkeypatch.setattr(rules_ai, "model_access", lambda *a: None)
    with pytest.raises(Refused, match="MI0501"):
        await proposals.start()
    assert proposals.read().model is False


def test_two_hundred_kept_pipelines_read_quickly():
    first = keep()
    now = datetime.now(UTC)
    with session_scope() as db:
        digest = db.get(PipelineDraft, first).kept_digest
        for _ in range(199):
            draft_id = secrets.token_hex(16)
            shutil.copytree(settings.draft_root / first, settings.draft_root / draft_id)
            db.add(PipelineDraft(id=draft_id, who="tester", name="d",
                                 graph={"nodes": [], "edges": []}, updated_at=now,
                                 provenance={}, revision=0, kept_at=now, kept_digest=digest))
    started = time.monotonic()
    view = proposals.read()
    assert time.monotonic() - started < 2.0
    assert len(proposals.cases()) == 200 and view.proposals == []


def test_the_routes_read_approve_and_withdraw(three, monkeypatch):
    from fastapi.testclient import TestClient
    from mendel_api import jobs
    from mendel_api.main import create_app

    async def idle(*args, **kwargs):
        return False

    monkeypatch.setattr(jobs, "running", idle)
    proposals.run(Model())
    http = TestClient(create_app())
    page = http.get("/api/rules/proposals").json()
    (proposal,) = page["proposals"]
    assert page["running"] is False
    approved = http.post(f"/api/rules/proposals/{proposal['id']}/approve").json()
    assert [u["slug"] for u in approved["in_use"]] == [SLUG]
    again = http.post(f"/api/rules/proposals/{proposal['id']}/approve")
    assert again.status_code == 422 and again.json()["detail"].startswith("MI0500")
    assert http.post(f"/api/rules/learned/{SLUG}/withdraw").json()["in_use"] == []
    assert http.post("/api/rules/learned/nothing/withdraw").status_code == 404
