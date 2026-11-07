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
        for table in ("forge_review", "forge_pull_request", "forge_test_run", "forge_step",
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
        assert row.agent == "forge" and row.prompt_id == "forge.questions.v7"


def test_a_redraft_sees_only_what_the_person_settled(adaptation):
    """#457 walk: GPT redrafting quast left gemma's open questions alone, because the prompt
    listed them as "so far". An open proposal is an earlier model's guess: a redraft drafts it
    fresh. An answer and a removal are the person's, and the drafter keeps seeing both."""
    first = {"questions": [*QUESTIONS["questions"], {
        "key": "questions:input_type:reads", "asks": "Which type?", "options": [
            {"id": "earlier.guess", "label": "earlier guess", "because": "a weak model said so"}],
        "suggested": "earlier.guess"}, {
        "key": "questions:output_type:bam", "asks": "Which type?", "options": [
            {"id": "alignment.bam", "label": "aligned reads", "because": "BAM"}]}]}
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(first))
    state = forging.load(adaptation)
    forging.act(adaptation, forging.person(Move.ANSWER, "questions:role",
                                           expected=state.items["questions:role"].current.n,
                                           value={"choice": "alignment"}, because=None))
    forging.act(adaptation, forging.person(
        Move.REMOVE, "questions:output_type:bam",
        expected=state.items["questions:output_type:bam"].current.n, value=None,
        because="not needed"))
    again = FakeClient({"questions": [{
        "key": "questions:input_type:reads", "asks": "Which type?", "options": [
            {"id": "fastq.reads", "label": "reads", "because": "FASTQ per sample"}],
        "suggested": "fastq.reads"}]})
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, again)
    sent = again.prompts[0]
    assert "earlier.guess" not in sent, "the earlier open proposal anchored the redraft"
    assert "questions:role" in sent and '"choice": "alignment"' in sent, "the answer is context"
    assert "questions:output_type:bam [removed]" in sent, "a removal stays visible, not re-asked"
    assert forging.load(adaptation).items["questions:input_type:reads"].current.value[
        "suggested"] == "fastq.reads"


def test_a_contract_redraft_does_not_see_its_earlier_open_proposal(adaptation):
    """The quast contract's first draft had nf_include ending in main.nf; a redraft shown that
    proposal would be anchored to it, as questions were."""
    _answer(adaptation)
    wrong = {"items": {**CONTRACT["items"], "contract:process": {
        **CONTRACT["items"]["contract:process"], "nf_include": "modules/nf-core/bwa/mem/main.nf"}},
        "because": {}}
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, FakeClient(wrong))
    again = FakeClient(CONTRACT)
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, again)
    assert "bwa/mem/main.nf" not in again.prompts[0]
    assert '"choice": "alignment"' in again.prompts[0], "the answered questions are context"


def test_the_questions_prompt_says_the_versions_topic_is_not_a_port(adaptation):
    client = FakeClient(QUESTIONS)
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, client)
    assert "nf-core's versions channel for the run's software report" in client.prompts[0]


def test_drafting_the_contract_stores_proposals(adaptation):
    _answer(adaptation)
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, FakeClient(CONTRACT))
    items = forging.load(adaptation).items
    assert items["contract:input:reads"].status == "proposed"
    assert items["contract:process"].current.because == "BWA_MEM in main.nf"


def test_the_contract_prompt_teaches_nf_include_and_a_folder_format(adaptation):
    """#459: v4's own example was `.../module/main.nf`, and GPT copied it for quast, which
    keys no module. A directory output also got no format."""
    _answer(adaptation)
    client = FakeClient(CONTRACT)
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, client)
    sent = client.prompts[0]
    assert "main.nf\"" not in sent.split("=== the module")[0], "an example still ends in .nf"
    assert '"nf_include": "modules/nf-core/example/main"' in sent
    assert '"format": ["folder"]' in sent


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


def test_question_context_is_declared_and_handles_missing_source(adaptation):
    from mendel_api.services import forge_context

    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    context = forge_context.read(adaptation, "questions:role")
    assert context.source_available
    assert context.choices[0].explain and context.choices[0].tools
    assert "job" in context.decides
    (forging.module_folder("nf-core", "bwa/mem") / "main.nf").unlink()
    assert not forge_context.read(adaptation, "questions:role").source_available


def test_review_quote_is_checked_and_cannot_change_items(adaptation):
    from mendel_api.services import forge_review

    revisions = forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    before = forging.load(adaptation).model_dump()
    reply = {"comments": [{"item": "questions:role", "comment": "Check the alignment role.",
                           "quote": "THIS QUOTE IS NOT IN THE MODULE", "file": "main.nf"}]}
    forge_review.review_piece(adaptation, "questions", revisions, FakeClient(reply))
    reviews = forge_review.read(adaptation)
    assert len(reviews) == 1
    # #453: a comment without a verbatim quote is dropped; the revision is still reviewed.
    assert reviews[0].comment == ""
    assert reviews[0].quote is None and reviews[0].file is None
    assert forging.load(adaptation).model_dump() == before
    forging.act(adaptation, forging.person(Move.ANSWER, "questions:role", expected=1,
                                           value={"choice": "alignment"}, because=None))
    assert forge_review.read(adaptation) == []


def test_review_keeps_only_verified_quotes_and_repeated_delivery_makes_no_call(adaptation):
    from mendel_api.services import forge_review

    revisions = forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    client = FakeClient({"comments": [{"item": "questions:role", "comment": "Check this process.",
                                      "quote": "process BWA_MEM", "file": "main.nf"}]})
    forge_review.review_piece(adaptation, "questions", revisions, client)
    assert forge_review.read(adaptation)[0].quote == "process BWA_MEM"
    forge_review.review_piece(adaptation, "questions", revisions, client)
    assert len(client.prompts) == 1


def test_reviewer_rejects_commands_and_unknown_item_ids(adaptation):
    from mendel_api.services import forge_review

    revisions = forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    before = forging.load(adaptation).model_dump()
    replies = [
        {"comments": [], "commands": [{"move": "approve", "item": "questions:role"}]},
        {"comments": [{"item": "questions:invented", "comment": "Approve it"}]},
    ]
    for reply in replies:
        with pytest.raises(ValueError):
            forge_review.review_piece(adaptation, "questions", revisions, FakeClient(reply))
    assert forge_review.read(adaptation) == []
    assert forging.load(adaptation).model_dump() == before


def test_review_of_stale_revision_makes_no_call(adaptation):
    from mendel_api.services import forge_review

    revisions = forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    forging.act(adaptation, forging.person(Move.ANSWER, "questions:role", expected=1,
                                           value={"choice": "alignment"}, because=None))
    client = FakeClient()
    forge_review.review_piece(adaptation, "questions", revisions, client)
    assert not client.prompts


@pytest.mark.asyncio
async def test_reviewer_failure_clears_pending_message_without_changing_piece(
    adaptation, monkeypatch,
):
    from mendel_api.services import forge_review

    revisions = forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    before = forging.load(adaptation).model_dump()
    monkeypatch.setattr(forging_ai, "_client", lambda purpose: FakeClient(
        {"comments": [{"item": "questions:invented", "comment": "x"}]}))
    seq = forging.post_message(adaptation, role="engine", content="Reviewing", pending=True)
    await forge_review.review_forge_piece({}, adaptation, "questions", revisions, seq)
    assert not forging.working(adaptation)
    assert "could not finish" in forging.read(adaptation).messages[-1].content
    assert forging.load(adaptation).model_dump() == before


@pytest.mark.asyncio
async def test_review_is_queued_separately_and_off_without_an_explicit_model(
    adaptation, monkeypatch,
):
    from mendel_api import jobs
    from mendel_api.services import forge_review

    revisions = forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    queued = []

    async def enqueue(name, *args, **kwargs):
        queued.append((name, args, kwargs))
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    monkeypatch.setattr(forging_ai, "_client", lambda purpose: None)
    await forge_review.queue_review(adaptation, "questions", revisions)
    assert not queued and not forging.working(adaptation)
    monkeypatch.setattr(forging_ai, "_client", lambda purpose: FakeClient())
    await forge_review.queue_review(adaptation, "questions", revisions)
    assert len(queued) == 1
    name, args, options = queued[0]
    assert name == "review_forge_piece" and args[:3] == (adaptation, "questions", revisions)
    assert options["queue"] == jobs.AI_QUEUE and options["job_id"].startswith("forge:review:")
    assert forging.row(adaptation).phase == "reviewing" and forging.working(adaptation)


def test_question_context_route_and_type_answers_validate_at_the_boundary(adaptation):
    client = TestClient(create_app())
    question = {"questions": [{"key": "questions:output_type:bam", "asks": "What does bam hold?",
        "options": [{"id": "alignment.bam", "label": "alignments",
                     "because": "BWA aligns reads"}]}]}
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(question))
    context = client.get(f"/api/forge/adaptations/{adaptation}/context",
                         params={"item": "questions:output_type:bam"})
    assert context.status_code == 200
    assert context.json()["lines"] and context.json()["optional"]
    for signature in ["not.declared", "alignment.bam::not_declared"]:
        response = client.post(f"/api/forge/adaptations/{adaptation}/commands", json={
            "move": "answer", "item": "questions:output_type:bam", "expected": 1,
            "value": {"choice": signature}})
        assert response.status_code == 422, response.text
    assert forging.load(adaptation).items["questions:output_type:bam"].current.n == 1


@pytest.mark.asyncio
async def test_drafting_stays_busy_until_the_reviewer_is_queued(adaptation, monkeypatch):
    from mendel_api import jobs
    from mendel_api.invocations import InvocationPurpose
    from mendel_forge.forging.protocol import Phase

    client = FakeClient(QUESTIONS)
    monkeypatch.setattr(forging_ai, "_client",
                        lambda purpose: (FakeClient() if purpose is InvocationPurpose.REVIEW
                                         else client))
    queued = []

    async def enqueue(name, *args, **kwargs):
        assert forging.row(adaptation).phase == "drafting"
        assert forging.read(adaptation).messages[-1].pending
        queued.append(name)
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    forging.set_phase(adaptation, Phase.DRAFTING)
    await forging_ai.draft_forge_piece({}, adaptation, "questions")
    assert queued == ["review_forge_piece"]
    assert forging.row(adaptation).phase == "reviewing" and forging.working(adaptation)


def test_contract_retry_names_bad_fields_as_well_as_wrong_piece_items(adaptation):
    _answer(adaptation)
    bad = {"items": {
        "contract:process": {"nf_process": True, "nf_include": False, "container": True},
        "vocabulary:role:extra": {"name": "extra", "explain": "An extra job"},
    }}
    client = FakeClient(bad, bad)
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, client)
    assert len(client.prompts) == 2
    retry = client.prompts[1]
    assert "vocabulary:role:extra: not part of contract" in retry
    assert "nf_process: Input should be a valid string" in retry
    assert "nf_include: Input should be a valid string" in retry
    assert "container: Input should be a valid string" in retry
    assert "contract:process" not in forging.load(adaptation).items


def test_a_contract_draft_can_use_an_explicitly_approved_new_type(adaptation):
    _answer(adaptation)
    forging.act(adaptation, forging.person(Move.ANSWER, "questions:output_type:bam",
        expected=None, value={"choice": "alignment.custom", "new": True}, because=None))
    contract = {**CONTRACT["items"], "contract:output:bam": {
        "position": 0, "name": "bam", "type_id": "alignment.custom"}}
    client = FakeClient({"items": contract})
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, client)
    state = forging.load(adaptation)
    assert state.items["contract:output:bam"].value["type_id"] == "alignment.custom"
    assert state.items["contract:output:bam"].status.value == "proposed"
    assert not any(k.startswith("vocabulary:") for k in state.items)


def test_draft_prompt_separates_approved_answers_and_retains_removed_questions(adaptation):
    from mendel_forge.forging.model import Actor, Command

    _answer(adaptation)
    key = "questions:input_type:meta"
    forging.act_all(adaptation, [Command(move=Move.DRAFT, actor=Actor.AI, item=key,
        value={"asks": "What file is meta?", "options": []})])
    forging.act(adaptation, forging.person(Move.REJECT, key, expected=1, value=None, because=None))
    forging.act(adaptation, forging.person(Move.REMOVE, key, expected=2, value=None,
                                          because="Metadata, not a file"))
    client = FakeClient(CONTRACT)
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, client)
    prompt = client.prompts[0]
    assert "=== approved answers (instructions for this piece) ===" in prompt
    assert 'questions:role = {"choice": "alignment"}' in prompt
    assert "questions:input_type:meta [removed]" in prompt
    assert "Do not reintroduce removed questions or ports" in prompt
    assert "zero-based" in prompt
    assert '"nf_process": "EXAMPLE"' in prompt


def test_family_proposals_need_human_approval_and_include_known_family_context(adaptation):
    _answer(adaptation)
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, FakeClient(CONTRACT))
    for key, item in forging.load(adaptation).items.items():
        if item.status == "proposed":
            forging.act(adaptation, forging.person(Move.APPROVE, key,
                expected=item.current.n, value=None, because=None))
    forging.act(adaptation, forging.person(Move.WRITE, "parameters:none",
        expected=None, value={"because": "Defaults"}, because=None))
    key = "vocabulary:family:assembly"
    value = {"id": "assembly", "description": "Assembled sequences and assembly products."}
    client = FakeClient({"items": {key: value}, "because": {key: "The new type needs a family"}})
    forging_ai.draft_piece(adaptation, Piece.VOCABULARY, client)
    item = forging.load(adaptation).items[key]
    assert item.status == "proposed" and item.value == value
    assert "families (first segment of each type ID):" in client.prompts[0]
    assert "alignment" in client.prompts[0]
    assert "Families require human approval" in client.prompts[0]
    with session_scope() as db:
        invocation = db.get(AiInvocation, item.current.invocation)
        assert invocation.prompt_id == "forge.draft.v7"
    forging.act(adaptation, forging.person(Move.APPROVE, key,
        expected=item.current.n, value=None, because=None))
    assert forging.load(adaptation).items[key].status == "approved"


def _typed(*options: dict) -> dict:
    return {"questions": [{"key": "questions:input_type:reads", "asks": "What does reads hold?",
                           "options": list(options), "suggested": options[0]["id"]}]}


def test_the_engine_not_the_model_says_which_options_are_new(adaptation):
    """#451: a declared type the model marked new is not new; an undeclared one it left
    unmarked is. The model's flag is discarded on the way in."""
    reply = _typed({"id": "genome.fasta", "label": "genome", "because": "fasta", "new": True},
                   {"id": "assembly.fasta", "label": "assembly", "because": "contigs"})
    forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(reply, reply))
    items = forging.load(adaptation).items
    assert "questions:input_type:reads" in items, (
        "the draft was refused: the model's `new` flag decided, not the registry")
    options = items["questions:input_type:reads"].value["options"]
    assert options, "the question was stored without options"
    assert {o["id"]: o["new"] for o in options} == {"genome.fasta": False, "assembly.fasta": True}


@pytest.fixture
def quast(tmp_path, monkeypatch, adaptation) -> str:
    """quast beside bwa/mem: three inputs, one per sample and two references (#412)."""
    cache = settings.forge_cache
    shutil.copytree(FIXTURES / "quast", cache / "nf-core-modules/modules/nf-core/quast")
    catalogue.run_sync(FakeSource(["bwa/mem", "quast"]))
    return forging.start("nf-core", "quast", "rafael").id


def test_quasts_walk_suggestions_show_engine_findings(quast):
    """#452: the GPU walk's suggestions, each flagged on the item view and in the context."""
    def asked(name: str, type_id: str) -> dict:
        return {"key": f"questions:input_type:{name}", "asks": f"What does {name} hold?",
                "options": [{"id": type_id, "label": type_id, "because": "fits"}],
                "suggested": type_id}
    forging_ai.draft_piece(quast, Piece.QUESTIONS, FakeClient({"questions": [
        asked("consensus", "genome.fasta"), asked("fasta", "genome.fasta"),
        asked("gff", "annotation.gtf")]}))
    view = {i.key: [f.code for f in i.findings] for i in forging.read(quast).items}
    assert view["questions:input_type:consensus"] == ["MF0520", "MF0521"]
    assert view["questions:input_type:gff"] == ["MF0522"]
    from mendel_api.services import forge_context
    context = forge_context.read(quast, "questions:input_type:consensus")
    assert context.arrival == "sample"
    assert context.channel == "tuple val(meta) , path(consensus)"
    assert [f.code for f in context.findings] == ["MF0520", "MF0521"]
    request = forging_ai.compose(forging.row(quast), forging.load(quast), Piece.QUESTIONS,
                                 prompt="forge.questions.v4")
    assert any(t.id == "genome.fasta" and t.scope == "run" for t in request.known.described)
    assert {f.code for f in request.findings} == {"MF0520", "MF0521", "MF0522"}


def test_a_reviewer_with_no_concern_says_nothing_and_is_not_asked_again(adaptation):
    """#453: v1 had to comment on every item; v2 may return none, and that is recorded."""
    from mendel_api.services import forge_review

    revisions = forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    client = FakeClient({"comments": []})
    forge_review.review_piece(adaptation, "questions", revisions, client)
    reviews = forge_review.read(adaptation)
    assert reviews, "the reviewed revision is recorded"
    assert [r.comment for r in reviews] == [""]
    forge_review.review_piece(adaptation, "questions", revisions, client)
    assert len(client.prompts) == 1
    assert "Engine findings" in client.prompts[0] and "one per" in client.prompts[0]


def test_a_reviewer_key_with_the_prompts_status_label_is_read_as_the_key(adaptation):
    """gemma3:12b replied `questions:role [proposed]`, copying the prompt's label (#453)."""
    from mendel_api.services import forge_review

    revisions = forging_ai.draft_piece(adaptation, Piece.QUESTIONS, FakeClient(QUESTIONS))
    forge_review.review_piece(adaptation, "questions", revisions, FakeClient({"comments": [
        {"item": "questions:role [proposed]", "comment": "Check this process.",
         "quote": "process BWA_MEM", "file": "main.nf"}]}))
    reviews = forge_review.read(adaptation)
    assert reviews, "the review was refused"
    assert [(r.item, r.comment) for r in reviews] == [("questions:role", "Check this process.")]


def test_the_contract_prompt_teaches_constraints(adaptation):
    """#460: the Contract piece can say an input is optional, when an output is written, and
    how inputs constrain each other."""
    _answer(adaptation)
    client = FakeClient(CONTRACT)
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, client)
    sent = client.prompts[0]
    assert '"produced_when"' in sent and "contract:constraint:" in sent and '"absent"' in sent
    with session_scope() as db:
        assert db.query(AiInvocation).order_by(AiInvocation.started_at.desc()).first(
            ).prompt_id == "forge.draft.v7"


def test_a_contract_item_carries_its_engine_finding_on_read(adaptation):
    """#460: an optional input whose nf_inputs entry has no `absent` is MF0532 on the page."""
    _answer(adaptation)
    optional = {"items": {
        **CONTRACT["items"],
        "contract:input:reads": {"position": 0, "name": "reads", "type_id": "fastq.reads",
                                 "required": False},
        "contract:nf_inputs": [{"ports": ["reads"]}],
    }, "because": {}}
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, FakeClient(optional))
    view = forging.read(adaptation)
    found = next(i for i in view.items if i.key == "contract:nf_inputs").findings
    assert [f.code for f in found] == ["MF0532"]


def test_a_constraint_item_reads_as_its_sentence(adaptation):
    _answer(adaptation)
    drafted = {"items": {
        **CONTRACT["items"],
        "contract:constraint:row1": {"when": {"given.reads": "present"}, "forbids": [],
                                  "requires": ["reads"], "because": "it reads them"},
    }, "because": {}}
    forging_ai.draft_piece(adaptation, Piece.CONTRACT, FakeClient(drafted))
    item = next(i for i in forging.read(adaptation).items if i.key == "contract:constraint:row1")
    assert item.sentence == "`reads` is used only with `reads` (it reads them)"


def test_the_item_guide_names_every_kind_the_engine_reads():
    """#468: one description of each item kind, kept in step with the engine's own table."""
    from mendel_forge.forging.values import _FAMILIES

    guide = forging_ai.ITEM_SHAPES.read_text()
    assert _FAMILIES, "the engine declares no item kinds — this test is measuring nothing"
    import re

    missing = [kind for kind in [*_FAMILIES, "<piece>:none"]
               if not re.search(rf"^- {re.escape(kind)}[: ]", guide, re.MULTILINE)]
    assert missing == [], f"the item guide does not describe {missing}"


def test_the_chat_can_add_the_first_constraint_row(adaptation):
    """#468: with no constraint in the draft, the chat was shown no key for one, and refused."""
    _answer(adaptation)
    assert not any(k.startswith("contract:constraint") for k in forging.load(adaptation).items)
    seq = forging.post_message(adaptation, role="person", content="gff needs the reference")
    client = FakeClient({"text": "Nothing to add.", "commands": []})
    forging_ai.answer_message(adaptation, seq, client)
    assert "contract:constraint:row<n>" in client.prompts[0]
    assert "contract:group:group<n>" in client.prompts[0]


def test_the_draft_teaches_a_param_domain_by_its_kind(adaptation):
    """#468 walk: GPT wrote `domain: {type: ...}`; the shape was named but never spelled out."""
    _answer(adaptation)
    reply = {"items": {"parameters:none": {"because": "none"}}, "because": {}}
    client = FakeClient(reply, reply)
    forging_ai.draft_piece(adaptation, Piece.PARAMETERS, client)
    assert '"domain" is null or {"kind": "boolean" | "enum" | "integer" | "number"' in \
        client.prompts[0]
    assert "contract:constraint:row<n>" in client.prompts[0], "the draft reads the shared guide"
