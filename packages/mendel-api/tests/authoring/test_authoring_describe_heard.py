"""What the person said is recorded from the first sentence when the model quotes it, and
offered when it does not (Part I.0 spec §5.3, §6.2)."""

import json

from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import authoring_decisions, decisions, suggestions
from mendel_api.settings import settings
from mendel_api_tests.http import (
    _begin,
    _model,
    _run,
    _session,
    needs_db,
)
from mendel_api_tests.http import clean as clean  # noqa: F401
from mendel_api_tests.http import (
    client as client,  # noqa: F401
)
from mendel_api_tests.http import (
    queue as queue,  # noqa: F401
)

pytestmark = needs_db

PROMPT = "I have RNA-seq reads and want gene counts"
"""What `_begin` sends: the quotes below are cut from it."""


def _draft(session_id: str) -> str:
    with session_scope() as db:
        return db.get(PipelineAuthoringSession, session_id).draft_id


def _read(monkeypatch, client, queue, reply: dict) -> dict:
    monkeypatch.setattr(settings, "family_step_from", 10_000)  # the one-step call: one reply
    session_id, seq = _begin(client, queue)
    _model(monkeypatch, json.dumps(reply))
    _run(session_id, seq)
    return _session(client, session_id)


def test_a_quoted_want_and_fact_are_recorded_and_not_asked(monkeypatch, client, clean, queue):
    session = _read(
        monkeypatch,
        client,
        queue,
        {
            "wants": [{"type": "counts.matrix", "quote": "gene counts"}],
            "inputs": [{"type": "fastq.reads", "quote": "RNA-seq reads"}],
            "say": "Gene counts — got it.",
        },
    )
    draft = _draft(session["id"])
    assert decisions.heard_of(draft)[("want", "counts.matrix")][0] == "gene counts"
    assert [i.type_id for i in decisions.read(draft).inputs if i.present] == ["fastq.reads"]
    assert not authoring_decisions.confirmed(draft)
    assert session["pending_proposal"]["envelope"]["subject"] != "fastq.reads"


def test_an_unquoted_fact_is_offered_and_pre_fills_its_question(monkeypatch, client, clean, queue):
    session = _read(
        monkeypatch,
        client,
        queue,
        {
            "wants": [{"type": "counts.matrix", "quote": "gene counts"}],
            "inputs": [{"type": "fastq.reads"}],
        },
    )
    draft = _draft(session["id"])
    assert not [i for i in decisions.read(draft).inputs if i.present]
    assert [v.change.subject for v in suggestions.pending(session["id"])] == ["fastq.reads"]
    pending = session["pending_proposal"]
    assert pending["envelope"]["subject"] == "fastq.reads"
    options = {o["id"]: o for o in pending["block"]["options"]}
    assert options["have_it"]["recommended"] and options["have_it"]["note"] == "suggested by AI"


def test_what_is_not_offered_is_kept_in_their_words(monkeypatch, client, clean, queue):
    session = _read(
        monkeypatch,
        client,
        queue,
        {
            "wants": [{"type": "counts.matrix", "quote": "gene counts"}],
            "not_offered": [{"quote": "RNA-seq"}, {"quote": "variant calling"}],
        },
    )
    assert [a.phrase for a in decisions.read_asked(_draft(session["id"]))] == ["RNA-seq"]


def test_a_dead_end_retracts_the_want_instead_of_clearing_an_extraction(
    monkeypatch, client, clean, queue
):
    session = _read(monkeypatch, client, queue, {"wants": [{"type": "annotation.gtf"}]})
    assert session["phase"] == "understanding"
    assert not [w for w in decisions.read(_draft(session["id"])).wants if w.present]


def test_an_unedited_card_confirms_without_moving_a_decision(monkeypatch, client, clean, queue):
    from mendel_api_tests.http import _goal_review

    session = _goal_review(client, queue, monkeypatch)
    draft = _draft(session["id"])
    with session_scope() as db:
        before = db.get(PipelineDraft, draft).decision_revision
    card = session["pending_proposal"]
    answer = client.post(
        f"/api/pipeline/authoring/{session['id']}/proposals/{card['id']}/decide",
        json={"decision": "accepted", "expected_revision": session["revision"]},
    )
    assert answer.status_code == 200, answer.text
    with session_scope() as db:
        row = db.get(PipelineDraft, draft)
        assert row.confirmed_revision == before
        assert row.decision_revision == before
