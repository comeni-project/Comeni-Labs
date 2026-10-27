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
