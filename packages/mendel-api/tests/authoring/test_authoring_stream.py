"""What the one stream reads from the server (one builder plan 3): when the open question was
asked, so the chat can dock it once the person talks past it, and what a receipt changed, so an
announcement can point at it."""

from mendel_api.authoring.types import Receipt, ReceiptAbout, parse_block
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal
from mendel_api.services import session as facade
from mendel_api_tests.gathering import _gathering, _pending_for
from mendel_api_tests.gathering import clean as clean


def test_the_open_question_says_when_it_was_asked(clean):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    with session_scope() as db:
        created = db.get(PipelineAuthoringProposal, pid).created_at
    assert facade.read(sid)["pending_proposal"]["asked_at"] == created.isoformat()


def test_a_receipt_says_what_it_changed():
    receipt = Receipt(id="r-1", summary="Set strandedness.", revision=3, by="person",
                      about=ReceiptAbout(node="SUBREAD_FEATURECOUNTS", subject="strandedness"))
    again = parse_block(receipt.model_dump(mode="json"))
    assert again.about == ReceiptAbout(node="SUBREAD_FEATURECOUNTS", subject="strandedness")


def test_a_receipt_about_nothing_in_particular_has_no_about():
    assert parse_block(Receipt(id="r-2", summary="Built.", revision=1, by="resolver")
                       .model_dump(mode="json")).about is None


def test_what_was_asked_for_and_is_not_offered_reaches_the_page(clean, monkeypatch):
    """Part I.2: a request the model reads as not offered is a note the page shows, and the
    conversation says so once (the correction path's receipt)."""
    import asyncio
    import json

    from comeni_ai import Client, ModelAccess
    from mendel_api.services import authoring_jobs, decisions
    from mendel_authoring import commands

    class Once:
        def send(self, access, prompt: str) -> str:
            return json.dumps({"not_offered": [{"quote": "differential expression"}]})

    monkeypatch.setattr(authoring_jobs, "_client",
                        lambda *_: Client(ModelAccess(model="fake/test"), transport=Once()))
    sid = _gathering(want=["counts.matrix"])
    seq = facade.perform(commands.Say(sid, "and then differential expression please")).result
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))
    picture = facade.read(sid)
    assert picture["not_offered"] == ["differential expression"]
    said = [b["summary"] for t in picture["turns"] for b in t["blocks"] if b["kind"] == "receipt"]
    assert any("not offered here" in s.lower() for s in said), said
    decisions.retract_asked(picture["draft_id"], "differential expression", who="ana")
    assert facade.read(sid)["not_offered"] == []
