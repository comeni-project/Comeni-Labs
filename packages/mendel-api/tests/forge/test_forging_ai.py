"""The forge's model calls: replies validated twice, nothing invalid stored (spec §3).

A fake client stands in for the provider: it hands back canned JSON and validates it against the
requested shape, as `comeni_ai.Client.respond` does. No live model.
"""

import json
import shutil

import pytest
import sqlalchemy as sa
from comeni_ai import ModelAccess, Usage
from fastapi.testclient import TestClient
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import AiInvocation
from mendel_api.services import catalogue, forging, forging_ai
from mendel_api.settings import settings
from mendel_api_tests.catalogue import FIXTURES, FakeSource
from mendel_api_tests.database import reachable
from mendel_forge.forging.model import KEY, Move, Piece
from pydantic import ValidationError

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


class FakeClient:
    """Replies in order; a reply that does not fit the shape is `None`, as the real client."""

    def __init__(self, *replies: dict):
        self.replies = [json.dumps(r) for r in replies]
        self.access = ModelAccess(model="fake/forge", base_url="http://local")
        self.last_prompt = self.last_response = self.last_refusal = None
        self.last_usage = None
        self.prompts: list[str] = []

    def respond(self, prompt, shape, choices=None):
        self.prompts.append(prompt)
        self.last_prompt, self.last_response = prompt, self.replies.pop(0)
        try:
            return shape.model_validate_json(self.last_response)
        except ValidationError as error:
            self.last_refusal = f"MA0004: {str(error).splitlines()[0]}"
            return None


@pytest.fixture
def adaptation(tmp_path, monkeypatch) -> str:
    with session_scope() as db:
        for table in ("forge_pull_request", "forge_test_run", "forge_step",
                      "forge_message", "forge_revision",
                      "forge_item",
                      "forge_adaptation",
                      "catalogue_module", "catalogue_sync"):
            db.execute(sa.text(f"DELETE FROM {table}"))
        db.execute(sa.text("DELETE FROM ai_invocation WHERE agent = 'forge'"))
    cache = tmp_path / "forge"
    shutil.copytree(FIXTURES / "bwa" / "mem", cache / "nf-core-modules/modules/nf-core/bwa/mem")
    monkeypatch.setattr(settings, "forge_cache", cache)
    catalogue.run_sync(FakeSource(["bwa/mem"]))
    return forging.start("nf-core", "bwa/mem", "rafael").id


QUESTIONS = {"questions": [{"key": "questions:role", "asks": "Which role?", "options": [
    {"id": "alignment", "label": "alignment", "because": "it aligns reads"}],
    "suggested": "alignment"}]}
CONTRACT = {"items": {
    "contract:process": {"nf_process": "BWA_MEM", "nf_include": "modules/nf-core/bwa/mem/main",
                         "roles": ["alignment"]},
    "contract:input:reads": {"position": 0, "name": "reads", "type_id": "fastq.reads"},
    "contract:output:bam": {"position": 0, "name": "bam", "type_id": "alignment.bam"},
}, "because": {"contract:process": "BWA_MEM in main.nf"}}


def _answer(adaptation_id: str) -> None:
    forging_ai.draft_piece(adaptation_id, Piece.QUESTIONS, FakeClient(QUESTIONS))
    item = forging.load(adaptation_id).items["questions:role"]
    forging.act(adaptation_id, forging.person(Move.ANSWER, "questions:role",
                                              expected=item.current.n,
                                              value={"choice": "alignment"}, because=None))


def test_drafting_questions_stores_proposals_and_records_the_call(adaptation):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    item = forging.load(adaptation).items["questions:role"]
    assert item.status == "proposed"
    assert item.current.actor == "ai" and item.current.invocation
    with session_scope() as db:
        row = db.get(AiInvocation, item.current.invocation)
        assert row.agent == "forge" and row.prompt_id == "forge.questions.v2"


def test_drafting_the_contract_stores_proposals(adaptation):
    _answer(adaptation)
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, FakeClient(CONTRACT))
    items = forging.load(adaptation).items
    assert items["contract:input:reads"].status == "proposed"
    assert items["contract:process"].current.because == "BWA_MEM in main.nf"


def test_the_prompt_carries_the_module_and_the_registry(adaptation):
    client = FakeClient(QUESTIONS)
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, client)
    assert "BWA_MEM" in client.prompts[0] and "fastq.reads" in client.prompts[0]


def test_an_invalid_reply_is_retried_once_then_shown_never_stored(adaptation):
    _answer(adaptation)
    wrong = {"items": {**CONTRACT["items"], "contract:input:reads": {
        "position": 0, "name": "reads", "type_id": "nothing.here"}}}
    client = FakeClient(wrong, wrong)
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, client)
    assert len(client.prompts) == 2
    assert "MF0507" in client.prompts[1], "the retry tells the model what was wrong"
    assert not [k for k in forging.load(adaptation).items if k.startswith("contract:")]
    messages = forging.read(adaptation).messages
    assert messages and messages[-1].role == "engine"
    assert "MF0507" in " ".join(messages[-1].details)


def test_a_refused_questions_draft_tells_the_retry_why(adaptation):
    numbered = {"questions": [{**QUESTIONS["questions"][0], "key": "questions:input_type2"}]}
    client = FakeClient(numbered, QUESTIONS)
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, client)
    assert len(client.prompts) == 2
    assert "input_type2" in client.prompts[1], "the retry tells the model what was wrong"
    assert "input_type2" not in client.prompts[0]
    assert list(forging.load(adaptation).items) == ["questions:role"]


def test_the_questions_prompt_teaches_a_key_for_each_input_and_output(adaptation):
    client = FakeClient(QUESTIONS)
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, client)
    for key in ("questions:input_type:reads", "questions:output_type:bam"):
        assert KEY.match(key)
    assert "questions:input_type:<input>" in client.prompts[0]
    assert "questions:output_type:<output>" in client.prompts[0]


def test_a_refused_chat_reply_tells_the_retry_why(adaptation):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    seq = forging.post_message(adaptation, role="person", content="approve it")
    approving = {"text": "done", "commands": [
        {"move": "approve", "item": "questions:role", "because": "asked to"}]}
    client = FakeClient(approving, approving)
    forging_ai.answer_message(adaptation, seq, client)
    assert len(client.prompts) == 2
    assert "Your previous reply was refused" in client.prompts[1]
    assert "Your previous reply was refused" not in client.prompts[0]


def test_a_chat_reply_with_an_approve_is_refused(adaptation):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    before = forging.load(adaptation)
    seq = forging.post_message(adaptation, role="person", content="approve it")
    approving = {"text": "done", "commands": [
        {"move": "approve", "item": "questions:role", "because": "asked to"}]}
    forging_ai.answer_message(adaptation, seq, FakeClient(approving, approving))
    assert forging.load(adaptation) == before
    assert "nothing changed" in forging.read(adaptation).messages[-1].content


def test_a_chat_add_proposes_a_new_item(adaptation):
    _answer(adaptation)
    seq = forging.post_message(adaptation, role="person", content="add the reads input",
                               item="contract:input:reads")
    adding = {"text": "Added.", "commands": [
        {"move": "add", "item": "contract:input:reads",
         "value": {"position": 0, "name": "reads", "type_id": "fastq.reads"},
         "because": "main.nf takes reads first"}]}
    forging_ai.answer_message(adaptation, seq, FakeClient(adding))
    item = forging.load(adaptation).items["contract:input:reads"]
    assert item.status == "proposed" and item.current.move == "add"
    reply = forging.read(adaptation).messages[-1]
    assert reply.role == "ai" and reply.commands and reply.item == "contract:input:reads"


def test_a_chat_card_names_the_revision_it_shows(adaptation):
    """Review I4: approving a card approves the value on it, or is refused as stale."""
    _answer(adaptation)
    seq = forging.post_message(adaptation, role="person", content="add reads")
    adding = {"text": "Added.", "commands": [
        {"move": "add", "item": "contract:input:reads",
         "value": {"position": 0, "name": "reads", "type_id": "fastq.reads"}, "because": "x"}]}
    forging_ai.answer_message(adaptation, seq, FakeClient(adding))
    card = forging.read(adaptation).messages[-1].commands[0]
    assert card["n"] == forging.load(adaptation).items["contract:input:reads"].current.n


def test_drafting_that_was_not_queued_does_not_strand_the_page(adaptation, monkeypatch):
    """Review I1: a refused enqueue says so and leaves the phase as it was."""
    import asyncio

    from comeni_flow.interpret import Refused
    from mendel_api import jobs

    async def refused(*args, **kwargs):
        return False

    monkeypatch.setattr(jobs, "enqueue", refused)
    with pytest.raises(Refused, match="MF0506"):
        asyncio.run(forging.ask_to_draft(adaptation, "questions"))
    assert forging.read(adaptation).phase == "reviewing"


def test_the_forge_jobs_free_their_id_when_done():
    """Review I1: a finished draft must not block the next for as long as ARQ keeps results."""
    from mendel_api.ai_worker import AIWorkerSettings

    forge = [f for f in AIWorkerSettings.functions
             if getattr(f, "name", "") in ("draft_forge_piece", "answer_forge_message")]
    assert len(forge) == 2 and all(f.keep_result_s == 0 for f in forge)


TEST_DRAFT = {"items": {"tests:test:paired": {
    "inputs": {"reads": ["genomics/sarscov2/illumina/fastq/test_1.fastq.gz"]},
    "expect": [{"port": "bam", "pattern": "*.bam"}]}},
    "because": {"tests:test:paired": "the module's first nf-test"}}


def _ready_for_tests(adaptation: str) -> None:
    _answer(adaptation)
    forging.act(adaptation, forging.person(Move.WRITE, "contract:process", expected=None, value={
        "nf_process": "BWA_MEM", "nf_include": "modules/nf-core/bwa/mem/main"}, because=None))
    for key, name, type_id in (("contract:input:reads", "reads", "fastq.reads"),
                               ("contract:output:bam", "bam", "alignment.bam")):
        forging.act(adaptation, forging.person(Move.WRITE, key, expected=None, value={
            "position": 0, "name": name, "type_id": type_id}, because=None))
    for key in ("parameters:none", "vocabulary:none", "rules:none"):
        forging.act(adaptation, forging.person(Move.WRITE, key, expected=None,
                                               value={"because": "nothing"}, because=None))


def test_drafting_tests_reads_the_modules_nf_test(adaptation):
    tests = forging.module_folder("nf-core", "bwa/mem") / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "main.nf.test").write_text("input[0] = file(params.modules_testdata_base_path + "
                                        "'genomics/sarscov2/x.fastq.gz')")
    _ready_for_tests(adaptation)
    client = FakeClient(TEST_DRAFT)
    forging_ai.draft_piece(adaptation, Piece.TESTS, client)
    assert "genomics/sarscov2/x.fastq.gz" in client.prompts[0]
    item = forging.load(adaptation).items["tests:test:paired"]
    assert item.status == "proposed" and item.current.actor == "ai"
    with session_scope() as db:
        assert db.get(AiInvocation, item.current.invocation).prompt_id == "forge.tests.v1"


def test_a_module_with_no_nf_test_is_drafted_from_its_meta(adaptation):
    shutil.rmtree(forging.module_folder("nf-core", "bwa/mem") / "tests", ignore_errors=True)
    _ready_for_tests(adaptation)
    client = FakeClient(TEST_DRAFT)
    forging_ai.draft_piece(adaptation, Piece.TESTS, client)
    assert "(this module has no nf-test)" in client.prompts[0]


def test_a_drafted_data_commit_is_refused(adaptation):
    _ready_for_tests(adaptation)
    value = {**TEST_DRAFT["items"]["tests:test:paired"], "data_commit": "abc"}
    wrong = {"items": {"tests:test:paired": value}}
    forging_ai.draft_piece(adaptation, Piece.TESTS, FakeClient(wrong, wrong))
    assert "tests:test:paired" not in forging.load(adaptation).items
    assert "wasn't usable" in forging.read(adaptation).messages[-1].content

# ── what the AI did, as a record the page can follow (#420, #430) ─────────────────────────────


def _usage(self):
    self.last_usage = Usage(model="fake/forge", duration_ms=9, input_tokens=120, output_tokens=30,
                            cached_tokens=5)


class CountingClient(FakeClient):
    def respond(self, prompt, shape, choices=None):
        reply = super().respond(prompt, shape, choices)
        _usage(self)
        return reply


def _kinds(adaptation):
    return [e.kind for e in forging.events(adaptation)]


def test_a_forge_call_records_its_tokens(adaptation):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, CountingClient(QUESTIONS))
    with session_scope() as session:
        call = session.scalars(sa.select(AiInvocation)).one()
        assert (call.input_tokens, call.output_tokens, call.cached_tokens) == (120, 30, 5)


def test_a_draft_leaves_each_step_in_order(adaptation):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, CountingClient(QUESTIONS))
    assert _kinds(adaptation) == ["started", "asking", "called", "checking", "saved"]
    found = forging.events(adaptation)
    assert [e.seq for e in found] == sorted(e.seq for e in found)
    assert found[0].data["piece"] == "questions"
    assert found[1].data == {"attempt": 1, "attempts": 2, "model": "fake/forge"}
    assert found[2].data["input_tokens"] == 120
    assert found[2].data["output_tokens"] == 30
    assert found[4].data["items"] == 1


def test_a_refused_attempt_appears_when_it_happens(adaptation):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, CountingClient({"nope": 1}, QUESTIONS))
    kinds = _kinds(adaptation)
    assert kinds.count("refused") == 1
    assert kinds.index("refused") < kinds.index("saved")
    refused = next(e for e in forging.events(adaptation) if e.kind == "refused")
    assert refused.data["attempt"] == 1 and refused.data["problems"]


def test_giving_up_says_it_in_a_sentence_with_the_detail_apart(adaptation):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, CountingClient({"nope": 1}, {"nope": 2}))
    message = forging.read(adaptation).messages[-1]
    assert message.content == "The questions draft wasn't usable, so nothing was saved."
    assert ":" not in message.content
    assert message.details
    assert message.resolved is False


def test_a_refused_draft_is_resolved_once_its_piece_has_items(adaptation):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, CountingClient({"nope": 1}, {"nope": 2}))
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, CountingClient(QUESTIONS))
    assert forging.read(adaptation).messages[0].resolved is True


def test_no_model_is_a_sentence_too(adaptation, monkeypatch):
    monkeypatch.setattr(forging_ai, "_client", lambda purpose: None)
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS)
    message = forging.read(adaptation).messages[-1]
    assert message.content.startswith("No model is set for the forge")
    assert "MI0106" in " ".join(message.details)


def test_a_chat_reply_leaves_its_steps(adaptation):
    seq = forging.post_message(adaptation, role="person", content="Add a question")
    forging_ai.answer_message(adaptation, seq, CountingClient({"text": "Okay.", "commands": []}))
    assert _kinds(adaptation)[:2] == ["started", "asking"]
    assert forging.events(adaptation)[0].data["what"] == "replying"


@pytest.fixture
def client():
    return TestClient(create_app())


def test_the_record_can_be_read_after_a_point(adaptation, client):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, CountingClient(QUESTIONS))
    every = client.get(f"/api/forge/adaptations/{adaptation}/events").json()
    assert [e["kind"] for e in every][:2] == ["started", "asking"]
    later = client.get(f"/api/forge/adaptations/{adaptation}/events",
                       params={"after": every[2]["seq"]}).json()
    assert [e["kind"] for e in later] == ["checking", "saved"]


def test_the_stream_sends_what_is_new_then_ends_when_nothing_is_working(adaptation, client):
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, CountingClient(QUESTIONS))
    with client.stream("GET", f"/api/forge/adaptations/{adaptation}/events/stream") as answer:
        assert answer.headers["content-type"].startswith("text/event-stream")
        text = "".join(answer.iter_text())
    body, _, ended = text.partition("event: end")
    sent = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert [e["kind"] for e in sent] == ["started", "asking", "called", "checking", "saved"]
    assert ended
