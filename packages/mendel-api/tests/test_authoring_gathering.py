"""Gathering: the engine asks for what the want needs, and each answer becomes a typed fact.

Driven through the service against the throwaway database, with no model: clicking an option
needs none (protocol rule 5), and the gap list is the engine's (rule 1).
"""

import authoring_setup
import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.authoring.types import Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession
from mendel_api.services import blueprint as bp
from mendel_api.services import drafts
from mendel_api.services import session as facade
from mendel_api.stages import gathering
from mendel_api.stages import goal as goal_stage
from mendel_authoring import commands
from mendel_authoring import state as st
from mendel_postgres import reachable, truncate

pytestmark = pytest.mark.skipif(
    not reachable(), reason="no database — run `docker compose up -d postgres`"
)


@pytest.fixture
def clean():
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft, gate_run"
    )
    with session_scope() as session:
        session.execute(truncate(f"TRUNCATE TABLE {tables}"))
    yield


def _gathering(want: list[str], stated: list[dict] | None = None) -> str:
    """A session moved to GATHERING with a want and no facts, its first gap offered."""
    draft_id = drafts.create(DraftGraph(), "t", "ana")
    sid = facade.perform(commands.OpenSession(draft_id, "ana")).result
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).extraction = {
            "want": want,
            "constraints": {},
            "stated": stated or [],
        }
    authoring_setup.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring_setup.offer_next_gap(sid)
    return sid


def _payload(pid: str) -> dict:
    with session_scope() as db:
        return dict(db.get(PipelineAuthoringProposal, pid).payload)


def _pending_for(sid: str, subject: str) -> str:
    """Answer every earlier gap with its first ordinary option until `subject` is offered."""
    while (pid := facade.pending_id(sid)) and _payload(pid)["subject"] != subject:
        skip = ("dont_have", "value", "not_sure", "upload")
        options = [o for o in _payload(pid)["options"] if o not in skip]
        facade.perform(commands.AnswerGap(pid, options[0], None, "ana"))
    return facade.pending_id(sid)


def _answer_until(sid: str, subject: str, option: str) -> None:
    facade.perform(commands.AnswerGap(_pending_for(sid, subject), option, None, "ana"))


def _facts(sid: str) -> list[dict]:
    return facade.read(sid)["facts"]


def test_answering_every_gap_reaches_the_card_with_a_goal_that_builds(clean):
    sid = _gathering(want=["counts.matrix"])
    while (pid := facade.pending_id(sid)) and "subject" in _payload(pid):
        subject = _payload(pid)["subject"]
        if subject == "read_length":
            facade.perform(commands.AnswerGap(pid, "value", 150, "ana"))
        elif subject == "paired":
            facade.perform(commands.AnswerGap(pid, "yes", None, "ana"))
        elif subject == "strandedness":
            facade.perform(commands.AnswerGap(pid, "reverse", None, "ana"))
        else:
            facade.perform(commands.AnswerGap(pid, "have_it", None, "ana"))
    assert facade.current_phase(sid) is Phase.GOAL_REVIEW
    goal = gathering.compose_goal(sid)
    assert {h.type_id for h in goal.have} == {"fastq.reads", "genome.fasta", "annotation.gtf"}
    assert {m.measurement: m.value for m in goal.profile.measurements}["read_length"] == 150
    bp.resolve(goal)  # does not raise: #114's defect, closed


def test_the_card_offered_after_gathering_carries_the_composed_goal(clean):
    sid = _gathering(want=["counts.matrix"])
    while (pid := facade.pending_id(sid)) and "subject" in _payload(pid):
        options = [o for o in _payload(pid)["options"] if o not in ("dont_have", "value", "upload")]
        facade.perform(commands.AnswerGap(pid, options[0], None, "ana"))
    card = _payload(facade.pending_id(sid))
    assert card["block"]["kind"] == "goal_summary"
    assert {h["type_id"] for h in card["goal"]["have"]} >= {"genome.fasta", "annotation.gtf"}


def test_cant_share_leaves_a_measurement_open_and_out_of_the_profile(clean):
    sid = _gathering(want=["counts.matrix"])
    _answer_until(sid, "read_length", "cant_share")
    goal = gathering.compose_goal(sid)
    assert "read_length" not in {m.measurement for m in goal.profile.measurements}
    assert {"subject": "read_length", "source": "open"}.items() <= [
        f for f in _facts(sid) if f["subject"] == "read_length"
    ][0].items()


def test_dont_have_an_input_stops_honestly(clean):
    sid = _gathering(want=["counts.matrix"])
    _answer_until(sid, "genome.fasta", "dont_have")
    assert facade.current_phase(sid) is Phase.STOPPED
    assert "reference genome (FASTA)" in facade.read(sid)["turns"][-1]["blocks"][0]["text"]


def test_a_value_outside_the_declaration_is_refused_and_nothing_recorded(clean):
    """Review focus 3."""
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    before = _facts(sid)
    with pytest.raises(ValueError, match="MI0208"):
        facade.perform(commands.AnswerGap(pid, "value", -5, "ana"))
    assert facade.pending_id(sid) == pid and _facts(sid) == before


def test_an_option_the_gap_did_not_offer_is_refused(clean):
    sid = _gathering(want=["counts.matrix"])
    pid = facade.pending_id(sid)
    with pytest.raises(ValueError, match="MI0205"):
        facade.perform(commands.AnswerGap(pid, "probably", None, "ana"))
    assert facade.pending_id(sid) == pid and _facts(sid) == []


def test_a_reload_mid_gathering_keeps_the_facts_and_one_pending_gap(clean):
    """Review focus 4. `read` is what a reload calls."""
    sid = _gathering(want=["counts.matrix"])
    _answer_until(sid, "annotation.gtf", "have_it")
    view = facade.read(sid)
    assert view["pending_proposal"]["kind"] == "gap"
    assert len([f for f in view["facts"] if f["subject"] == "fastq.reads"]) == 1


def test_a_want_nothing_can_make_asks_instead_of_failing(clean, caplog):
    """#202: a model-chosen want nothing makes is a question, never `failed`."""
    caplog.set_level("INFO")
    sid = _gathering(want=["no.such.type"])
    view = facade.read(sid)
    assert facade.current_phase(sid) is Phase.UNDERSTANDING
    blocks = view["turns"][-1]["blocks"]
    assert [b["kind"] for b in blocks] == ["notice", "question"]
    assert blocks[0]["code"] == "MI0209" and blocks[0]["notice"] == "validation"
    assert "no.such.type" not in blocks[0]["text"], "the model's guess is never shown as fact"
    assert "no.such.type" in caplog.text, "the server log says which type"
    assert blocks[1]["asks"] == gathering.UNREACHABLE_ASK
    assert "no.such.type" not in blocks[1]["asks"]
    with session_scope() as db:
        assert db.get(PipelineAuthoringSession, sid).extraction is None, "the want is cleared"
    assert view["pending_proposal"] is None


def test_a_gap_is_answered_through_decide_with_an_option_or_a_typed_value(clean):
    """The route: one click, or one typed value, and the next question is in the response."""
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    client = TestClient(create_app())
    sid = _gathering(want=["counts.matrix"])
    base = f"/api/pipeline/authoring/{sid}"

    view = client.get(base).json()
    assert view["pending_proposal"]["kind"] == "gap"
    assert "have_it" in view["pending_proposal"]["options"]

    pid = _pending_for(sid, "read_length")
    refused = client.post(
        f"{base}/proposals/{pid}/decide",
        json={"decision": "accepted", "expected_revision": 0, "option": "value", "value": -5},
    )
    assert refused.status_code == 422 and "MI0208" in refused.text

    answered = client.post(
        f"{base}/proposals/{pid}/decide",
        json={"decision": "accepted", "expected_revision": 0, "option": "value", "value": 150},
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["next_proposal"] not in (None, pid)
    facts = client.get(base).json()["facts"]
    assert {"subject": "read_length", "value": 150, "source": "person_said"}.items() <= [
        f for f in facts if f["subject"] == "read_length"
    ][0].items()


def _typed(monkeypatch, sid: str, text: str, reply: dict) -> None:
    """The person types an answer; the job reads it with a recorded model reply."""
    import asyncio
    import json

    from comeni_ai import Client, ModelAccess
    from mendel_api.services import authoring_jobs

    class Once:
        def send(self, access, prompt: str) -> str:
            return json.dumps(reply)

    monkeypatch.setattr(
        authoring_jobs,
        "_client",
        lambda *_: Client(ModelAccess(model="fake/test"), transport=Once()),
    )
    seq = facade.perform(commands.Say(sid, text)).result
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))


def test_a_typed_reply_pre_fills_the_gap_and_records_nothing(clean, monkeypatch):
    """#171: a model's reading of a typed reply is a suggestion; the person's click is the fact."""
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    before = _facts(sid)
    _typed(monkeypatch, sid, "yes, both ends were sequenced", {"chose": "yes"})
    assert facade.pending_id(sid) == pid and _facts(sid) == before
    options = {o["id"]: o for o in _payload(pid)["block"]["options"]}
    assert options["yes"]["recommended"] and "reply" in options["yes"]["note"]
    assert "I read that as Yes" in facade.read(sid)["turns"][-1]["blocks"][0]["text"]
    facade.perform(commands.AnswerGap(pid, "yes", None, "ana"))
    paired = [f for f in _facts(sid) if f["subject"] == "paired"][0]
    assert paired["value"] is True and paired["source"] == "person_said"


def test_a_stated_fact_pre_fills_its_gap_and_waits_for_the_click(clean):
    """#170: *paired-end* in the first sentence is heard, and still confirmed by the person."""
    sid = _gathering(
        want=["counts.matrix"],
        stated=[
            {"kind": "measurement", "subject": "paired", "value": True},
            {"kind": "measurement", "subject": "read_length", "value": 150},
        ],
    )
    pid = _pending_for(sid, "paired")
    options = {o["id"]: o for o in _payload(pid)["block"]["options"]}
    assert options["yes"]["recommended"] and options["yes"]["note"] == "you mentioned it"
    assert not options["no"]["recommended"]
    assert not [f for f in _facts(sid) if f["subject"] == "paired"]
    facade.perform(commands.AnswerGap(pid, "yes", None, "ana"))
    length = _payload(_pending_for(sid, "read_length"))["block"]
    assert length["value"] == 150


def test_a_reply_the_model_cannot_map_leaves_the_gap_and_records_nothing(clean, monkeypatch):
    """Never a guess: *unsure* re-offers the options and writes no fact."""
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    before = _facts(sid)
    _typed(monkeypatch, sid, "hmm, the sequencing core did it", {"unsure": True})
    assert facade.pending_id(sid) == pid and _facts(sid) == before
    last = facade.read(sid)["turns"][-1]
    assert last["state"] == "answered" and "options" in last["blocks"][0]["text"]


def test_a_typed_value_the_declaration_refuses_is_a_notice_and_nothing_recorded(clean, monkeypatch):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    before = _facts(sid)
    _typed(monkeypatch, sid, "minus five", {"value": -5})
    assert facade.pending_id(sid) == pid and _facts(sid) == before
    block = facade.read(sid)["turns"][-1]["blocks"][0]
    assert block["kind"] == "notice" and block["code"] == "MI0208"


def test_an_answered_gap_says_its_answer_in_the_history(clean):
    """Issue 169: the log showed *Type it (bp)* for a typed 150, and the label for the rest."""
    sid = _gathering(want=["counts.matrix"])
    facade.perform(commands.AnswerGap(_pending_for(sid, "read_length"), "value", 150, "ana"))
    history = {d["block"]["asks"]: d["answer"] for d in facade.read(sid)["history"]}
    assert history["Sequenced read length?"] == "150"
    assert history["Do you have the sequencing reads (FASTQ) this analysis needs?"] == "I have it"


# ── the session's calls, totalled and listed (14.7.4, #191) ───────────────────────────────


def _write_call(sid, *, input_tokens, output_tokens, cached, response=None, purpose="goal"):
    import secrets
    from datetime import UTC, datetime

    from mendel_api.models import AiInvocation

    now = datetime.now(UTC)
    with session_scope() as db:
        db.add(
            AiInvocation(
                id=secrets.token_hex(16),
                agent="builder",
                purpose=purpose,
                model="fake/test",
                provider="local",
                prompt_id="builder.goal.v4",
                prompt_version="v4",
                prompt_digest="0" * 64,
                input_digests={},
                temperature=0.0,
                state="succeeded",
                failure_code="",
                started_at=now,
                finished_at=now,
                duration_ms=10,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached,
                response=response,
                session_id=sid,
            )
        )


def test_usage_sums_the_sessions_calls_and_a_new_session_is_all_zero(clean):
    sid = _gathering(want=["counts.matrix"])
    assert facade.read(sid)["usage"] == {
        "input": 0,
        "output": 0,
        "cached": 0,
        "calls": 0,
        "in_flight": False,
    }
    _write_call(sid, input_tokens=3000, output_tokens=40, cached=2800)
    _write_call(sid, input_tokens=None, output_tokens=None, cached=None)  # no usage block
    _write_call("x" * 32, input_tokens=999, output_tokens=9, cached=0)  # another session
    assert facade.read(sid)["usage"] == {
        "input": 3000,
        "output": 40,
        "cached": 2800,
        "calls": 2,
        "in_flight": False,
    }


def test_the_call_list_carries_each_reply_oldest_first(clean):
    sid = _gathering(want=["counts.matrix"])
    _write_call(sid, input_tokens=10, output_tokens=1, cached=None, response='{"a": 1}')
    listed = facade.calls(sid)
    assert [c["response"] for c in listed] == ['{"a": 1}']
    assert listed[0]["purpose"] == "goal" and listed[0]["input"] == 10
    assert "reply_format" in listed[0]  # #194: null for a row written before it was recorded


def test_the_calls_route_lists_them_and_refuses_an_unknown_session(clean):
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    client = TestClient(create_app())
    sid = _gathering(want=["counts.matrix"])
    _write_call(sid, input_tokens=10, output_tokens=1, cached=None, response="{}")
    listed = client.get(f"/api/pipeline/authoring/{sid}/calls").json()
    assert listed[0]["response"] == "{}" and "reply_format" in listed[0]
    assert client.get(f"/api/pipeline/authoring/{sid}").json()["usage"]["calls"] == 1
    assert client.get("/api/pipeline/authoring/" + "0" * 32 + "/calls").status_code == 404


def test_the_models_constraints_are_suggestions_never_in_the_goal(clean):
    """#176: *gene_level, normalised* arrived in the typed goal unasked; now the card offers."""
    draft_id = drafts.create(DraftGraph(), "t", "ana")
    sid = facade.perform(commands.OpenSession(draft_id, "ana")).result
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).extraction = {
            "want": ["counts.matrix"],
            "constraints": {},
            "suggested": {
                "required_states": [{"type_id": "counts.matrix", "states": ["gene_level"]}]
            },
            "stated": [],
        }
    authoring_setup.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring_setup.offer_next_gap(sid)
    while (pid := facade.pending_id(sid)) and "subject" in _payload(pid):
        options = [o for o in _payload(pid)["options"] if o not in ("dont_have", "value", "upload")]
        facade.perform(commands.AnswerGap(pid, options[0], None, "ana"))
    assert not gathering.compose_goal(sid).constraints.required_states
    card = _payload(facade.pending_id(sid))["block"]
    assert card["suggested"] == [{"type_id": "counts.matrix", "states": ["gene_level"]}]


# ── each question phrased by a model (14.7.4, #167, #186) ─────────────────────────────────


def _asked(asks, option=None, value=None):
    from mendel_api.authoring.types import AskedGap

    return AskedGap(asks=asks, already_option=option, already_value=value)


def test_a_phrased_question_replaces_the_engines_words_in_place_and_keeps_the_options(clean):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    before = _payload(pid)["block"]
    facade.perform(
        commands.StorePhrasing(
            sid,
            "paired",
            _asked("Were both ends of each fragment sequenced?").model_dump(mode="json"),
            stamp=gathering.phrasing_context(sid, "paired"),
        )
    )
    after = _payload(pid)["block"]
    assert after["asks"] == "Were both ends of each fragment sequenced?"
    assert after["phrasing"] == "done"
    assert [o["id"] for o in after["options"]] == [o["id"] for o in before["options"]]


def test_a_phrasing_that_arrives_after_the_answer_changes_nothing(clean):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    facade.perform(commands.AnswerGap(pid, "yes", None, "ana"))
    answered = _payload(pid)["block"]
    facade.perform(
        commands.StorePhrasing(
            sid,
            "paired",
            _asked("late", option="no").model_dump(mode="json"),
            stamp=gathering.phrasing_context(sid, "paired"),
        )
    )
    assert _payload(pid)["block"] == answered


def test_already_pre_fills_and_an_unoffered_one_is_dropped(clean):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    facade.perform(
        commands.StorePhrasing(
            sid,
            "paired",
            _asked("Paired?", option="maybe").model_dump(mode="json"),
            stamp=gathering.phrasing_context(sid, "paired"),
        )
    )
    assert not any(o["recommended"] for o in _payload(pid)["block"]["options"])
    facade.perform(
        commands.StorePhrasing(
            sid,
            "paired",
            _asked("Paired?", option="yes").model_dump(mode="json"),
            stamp=gathering.phrasing_context(sid, "paired"),
        )
    )
    assert {o["id"] for o in _payload(pid)["block"]["options"] if o["recommended"]} == {"yes"}


def test_a_prefetched_phrasing_expires_when_earlier_answers_change_its_context(clean):
    sid = _gathering(want=["counts.matrix"])
    facade.perform(
        commands.StorePhrasing(
            sid,
            "strandedness",
            _asked("Which way was the library made?").model_dump(mode="json"),
            stamp=gathering.phrasing_context(sid, "strandedness"),
        )
    )
    pid = _pending_for(sid, "strandedness")
    block = _payload(pid)["block"]
    assert block["asks"] != "Which way was the library made?"
    assert block["phrasing"] == "none"


def test_a_refused_prefetch_is_retried_for_a_new_decision_context(clean, monkeypatch):
    """#196: refused while it was the *next* question, it used to wait `pending` for ever —
    its job id spent, nothing left to settle it."""
    monkeypatch.setattr(gathering, "_model_configured", lambda: True)
    sid = _gathering(want=["counts.matrix"])
    facade.perform(
        commands.PhrasingFailed(
            sid, "strandedness", stamp=gathering.phrasing_context(sid, "strandedness")
        )
    )
    assert "strandedness" not in gathering.to_phrase(sid)
    block = _payload(_pending_for(sid, "strandedness"))["block"]
    assert block["phrasing"] == "pending"
    assert "strandedness" in gathering.to_phrase(sid)


async def _queue_phrasing(sid: str) -> None:
    """What `ask` queues on entering a question (plan 1c), through the facade's queue seam."""
    from mendel_api.services import session
    from mendel_api.stages import _jobs

    for subject in gathering.to_phrase(sid):
        await session._enqueue(_jobs.phrase(sid, subject))


def test_without_a_model_nothing_is_pending_and_nothing_is_queued(clean, monkeypatch):
    import asyncio

    from mendel_api import jobs

    monkeypatch.setattr(gathering, "_model_configured", lambda: False)
    queued: list = []

    async def enqueue(*args, **kwargs):
        queued.append(kwargs)
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    sid = _gathering(want=["counts.matrix"])
    assert _payload(facade.pending_id(sid))["block"]["phrasing"] == "none"
    asyncio.run(_queue_phrasing(sid))
    assert queued == []


def test_phrasing_is_queued_for_this_gap_and_the_next_once_not_per_poll(clean, monkeypatch):
    import asyncio

    from mendel_api import jobs

    monkeypatch.setattr(gathering, "_model_configured", lambda: True)
    queued: list = []

    async def enqueue(*args, **kwargs):
        queued.append((args, kwargs))
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    sid = _gathering(want=["counts.matrix"])
    asyncio.run(_queue_phrasing(sid))
    asyncio.run(_queue_phrasing(sid))
    ids = [kw["job_id"] for _, kw in queued]
    assert len(set(ids)) == 2 and all(":phrase:" in i for i in ids)
    assert [args[2] for args, _ in queued[:2]] == ["fastq.reads", "genome.fasta"]


def test_a_question_waiting_for_its_words_counts_as_in_flight(clean, monkeypatch):
    monkeypatch.setattr(gathering, "_model_configured", lambda: True)
    sid = _gathering(want=["counts.matrix"])
    assert facade.read(sid)["usage"]["in_flight"] is True
    facade.perform(
        commands.PhrasingFailed(
            sid, "fastq.reads", stamp=gathering.phrasing_context(sid, "fastq.reads")
        )
    )
    assert facade.read(sid)["usage"]["in_flight"] is False


# ── the read-back (14.7.4, #176) ──────────────────────────────────────────────────────────


def _to_card(sid):
    while (pid := facade.pending_id(sid)) and "subject" in _payload(pid):
        options = [o for o in _payload(pid)["options"] if o not in ("dont_have", "value", "upload")]
        facade.perform(commands.AnswerGap(pid, options[0], None, "ana"))
    return facade.pending_id(sid)


def test_the_read_back_is_written_from_the_composed_goal(clean):
    sid = _gathering(want=["counts.matrix"])
    _to_card(sid)
    described = goal_stage.readback_context(sid)
    for part in ("fastq.reads", "genome.fasta", "annotation.gtf", "counts.matrix", "you said"):
        assert part in described, part


def test_a_read_back_lands_on_the_card_and_a_failed_one_leaves_the_engines_sentence(
    clean, monkeypatch
):
    monkeypatch.setattr(gathering, "_model_configured", lambda: True)
    sid = _gathering(want=["counts.matrix"])
    card = _to_card(sid)
    assert _payload(card)["block"]["readback_pending"] is True
    facade.perform(
        commands.StoreReadback(
            sid,
            "You'll get a table of gene counts from your reads.",
            stamp=goal_stage.readback_context_stamp(sid),
        )
    )
    block = _payload(card)["block"]
    assert block["readback"] == "You'll get a table of gene counts from your reads."
    assert block["readback_pending"] is False


def test_a_failed_read_back_clears_the_wait(clean, monkeypatch):
    monkeypatch.setattr(gathering, "_model_configured", lambda: True)
    sid = _gathering(want=["counts.matrix"])
    card = _to_card(sid)
    facade.perform(commands.ReadbackFailed(sid, stamp=goal_stage.readback_context_stamp(sid)))
    block = _payload(card)["block"]
    assert block["readback"] is None and block["readback_pending"] is False


def test_a_gap_is_offered_with_its_name_and_explanation(clean):
    """Part I.1: the question names the thing, and the offer carries why it is asked."""
    sid = _gathering(["counts.matrix"])
    payload = _payload(_pending_for(sid, "fastq.reads"))
    assert payload["block"]["asks"] == (
        "Do you have the sequencing reads (FASTQ) this analysis needs?")
    assert payload["explain"]["name"] == "sequencing reads (FASTQ)"
    assert payload["explain"]["needed"]
