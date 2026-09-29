"""Gathering: the engine asks for what the want needs, and each answer becomes a typed fact.

Driven through the service against the throwaway database, with no model: clicking an option
needs none (protocol rule 5), and the gap list is the engine's (rule 1).
"""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.authoring import state as st
from mendel_api.authoring.types import Mode, Phase
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession
from mendel_api.services import authoring, drafts
from mendel_api.services import blueprint as bp
from sqlalchemy import text


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


@pytest.fixture
def clean():
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft"
    )
    with session_scope() as session:
        session.execute(text(f"TRUNCATE TABLE {tables}"))
    yield


def _gathering(want: list[str], stated: list[dict] | None = None) -> str:
    """A session moved to GATHERING with a want and no facts, its first gap offered."""
    draft_id = drafts.create(DraftGraph(), "t", "ana")
    sid = authoring.open_session(draft_id, mode=Mode.BUILD, who="ana")
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).goal = {
            "want": want,
            "constraints": {},
            "stated": stated or [],
        }
    authoring.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring.offer_next_gap(sid)
    return sid


def _payload(pid: str) -> dict:
    with session_scope() as db:
        return dict(db.get(PipelineAuthoringProposal, pid).payload)


def _pending_for(sid: str, subject: str) -> str:
    """Answer every earlier gap with its first ordinary option until `subject` is offered."""
    while (pid := authoring.pending_id(sid)) and _payload(pid)["subject"] != subject:
        skip = ("dont_have", "value", "not_sure")
        options = [o for o in _payload(pid)["options"] if o not in skip]
        authoring.answer_gap(pid, options[0], None, by="ana")
    return authoring.pending_id(sid)


def _answer_until(sid: str, subject: str, option: str) -> None:
    authoring.answer_gap(_pending_for(sid, subject), option, None, by="ana")


def _facts(sid: str) -> list[dict]:
    with session_scope() as db:
        return list(db.get(PipelineAuthoringSession, sid).facts)


def test_answering_every_gap_reaches_the_card_with_a_goal_that_builds(clean):
    sid = _gathering(want=["counts.matrix"])
    while (pid := authoring.pending_id(sid)) and "subject" in _payload(pid):
        subject = _payload(pid)["subject"]
        if subject == "read_length":
            authoring.answer_gap(pid, "value", 150, by="ana")
        elif subject == "paired":
            authoring.answer_gap(pid, "yes", None, by="ana")
        elif subject == "strandedness":
            authoring.answer_gap(pid, "reverse", None, by="ana")
        else:
            authoring.answer_gap(pid, "have_it", None, by="ana")
    assert authoring.current_phase(sid) is Phase.GOAL_REVIEW
    goal = authoring.compose_goal(sid)
    assert {h.type_id for h in goal.have} == {"fastq.reads", "genome.fasta", "annotation.gtf"}
    assert {m.measurement: m.value for m in goal.profile.measurements}["read_length"] == 150
    bp.resolve(goal, mode=Mode.BUILD)  # does not raise: #114's defect, closed


def test_the_card_offered_after_gathering_carries_the_composed_goal(clean):
    sid = _gathering(want=["counts.matrix"])
    while (pid := authoring.pending_id(sid)) and "subject" in _payload(pid):
        options = [o for o in _payload(pid)["options"] if o not in ("dont_have", "value")]
        authoring.answer_gap(pid, options[0], None, by="ana")
    card = _payload(authoring.pending_id(sid))
    assert card["block"]["kind"] == "goal_summary"
    assert {h["type_id"] for h in card["goal"]["have"]} >= {"genome.fasta", "annotation.gtf"}


def test_cant_share_leaves_a_measurement_open_and_out_of_the_profile(clean):
    sid = _gathering(want=["counts.matrix"])
    _answer_until(sid, "read_length", "cant_share")
    goal = authoring.compose_goal(sid)
    assert "read_length" not in {m.measurement for m in goal.profile.measurements}
    assert {"subject": "read_length", "source": "open"}.items() <= [
        f for f in _facts(sid) if f["subject"] == "read_length"
    ][0].items()


def test_dont_have_an_input_stops_honestly(clean):
    sid = _gathering(want=["counts.matrix"])
    _answer_until(sid, "genome.fasta", "dont_have")
    assert authoring.current_phase(sid) is Phase.STOPPED
    assert "genome.fasta" in authoring.read(sid)["turns"][-1]["blocks"][0]["text"]


def test_a_value_outside_the_declaration_is_refused_and_nothing_recorded(clean):
    """Review focus 3."""
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    before = _facts(sid)
    with pytest.raises(ValueError, match="MI0208"):
        authoring.answer_gap(pid, "value", -5, by="ana")
    assert authoring.pending_id(sid) == pid and _facts(sid) == before


def test_an_option_the_gap_did_not_offer_is_refused(clean):
    sid = _gathering(want=["counts.matrix"])
    pid = authoring.pending_id(sid)
    with pytest.raises(ValueError, match="MI0205"):
        authoring.answer_gap(pid, "probably", None, by="ana")
    assert authoring.pending_id(sid) == pid and _facts(sid) == []


def test_a_reload_mid_gathering_keeps_the_facts_and_one_pending_gap(clean):
    """Review focus 4. `read` is what a reload calls."""
    sid = _gathering(want=["counts.matrix"])
    _answer_until(sid, "annotation.gtf", "have_it")
    view = authoring.read(sid)
    assert view["pending_proposal"]["kind"] == "gap"
    assert len([f for f in view["facts"] if f["subject"] == "fastq.reads"]) == 1


def test_a_want_nothing_can_make_fails_with_its_code(clean):
    """Review focus 1: an unbuildable want never reaches the card."""
    sid = _gathering(want=["no.such.type"])
    assert authoring.current_phase(sid) is Phase.FAILED
    assert authoring.read(sid)["turns"][-1]["blocks"][0]["code"] == "MI0209"


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
        authoring_jobs, "_client", lambda: Client(ModelAccess(model="fake/test"), transport=Once())
    )
    seq = authoring.say(sid, text)
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))


def test_a_typed_reply_pre_fills_the_gap_and_records_nothing(clean, monkeypatch):
    """#171: a model's reading of a typed reply is a suggestion; the person's click is the fact."""
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    before = _facts(sid)
    _typed(monkeypatch, sid, "yes, both ends were sequenced", {"chose": "yes"})
    assert authoring.pending_id(sid) == pid and _facts(sid) == before
    options = {o["id"]: o for o in _payload(pid)["block"]["options"]}
    assert options["yes"]["recommended"] and "reply" in options["yes"]["note"]
    assert "I read that as Yes" in authoring.read(sid)["turns"][-1]["blocks"][0]["text"]
    authoring.answer_gap(pid, "yes", None, by="ana")
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
    authoring.answer_gap(pid, "yes", None, by="ana")
    length = _payload(_pending_for(sid, "read_length"))["block"]
    assert length["value"] == 150


def test_a_reply_the_model_cannot_map_leaves_the_gap_and_records_nothing(clean, monkeypatch):
    """Never a guess: *unsure* re-offers the options and writes no fact."""
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    before = _facts(sid)
    _typed(monkeypatch, sid, "hmm, the sequencing core did it", {"unsure": True})
    assert authoring.pending_id(sid) == pid and _facts(sid) == before
    last = authoring.read(sid)["turns"][-1]
    assert last["state"] == "answered" and "options" in last["blocks"][0]["text"]


def test_a_typed_value_the_declaration_refuses_is_a_notice_and_nothing_recorded(clean, monkeypatch):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    before = _facts(sid)
    _typed(monkeypatch, sid, "minus five", {"value": -5})
    assert authoring.pending_id(sid) == pid and _facts(sid) == before
    block = authoring.read(sid)["turns"][-1]["blocks"][0]
    assert block["kind"] == "notice" and block["code"] == "MI0208"


def test_an_answered_gap_says_its_answer_in_the_history(clean):
    """Issue 169: the log showed *Type it (bp)* for a typed 150, and the label for the rest."""
    sid = _gathering(want=["counts.matrix"])
    authoring.answer_gap(_pending_for(sid, "read_length"), "value", 150, by="ana")
    history = {d["block"]["asks"]: d["answer"] for d in authoring.read(sid)["history"]}
    assert history["Sequenced read length?"] == "150"
    assert history["This analysis needs fastq.reads. Do you have one?"] == "I have it"


# ── the session's calls, totalled and listed (14.7.4, #191) ───────────────────────────────


def _write_call(sid, *, input_tokens, output_tokens, cached, response=None, purpose="goal"):
    import secrets
    from datetime import UTC, datetime

    from mendel_api.models import AiInvocation

    now = datetime.now(UTC)
    with session_scope() as db:
        db.add(AiInvocation(
            id=secrets.token_hex(16), agent="builder", purpose=purpose, model="fake/test",
            provider="local", prompt_id="builder.goal.v4", prompt_version="v4",
            prompt_digest="0" * 64, input_digests={}, temperature=0.0, state="succeeded",
            failure_code="", started_at=now, finished_at=now, duration_ms=10,
            input_tokens=input_tokens, output_tokens=output_tokens, cached_tokens=cached,
            response=response, session_id=sid,
        ))


def test_usage_sums_the_sessions_calls_and_a_new_session_is_all_zero(clean):
    sid = _gathering(want=["counts.matrix"])
    assert authoring.read(sid)["usage"] == {
        "input": 0, "output": 0, "cached": 0, "calls": 0, "in_flight": False}
    _write_call(sid, input_tokens=3000, output_tokens=40, cached=2800)
    _write_call(sid, input_tokens=None, output_tokens=None, cached=None)  # no usage block
    _write_call("x" * 32, input_tokens=999, output_tokens=9, cached=0)    # another session
    assert authoring.read(sid)["usage"] == {
        "input": 3000, "output": 40, "cached": 2800, "calls": 2, "in_flight": False}


def test_the_call_list_carries_each_reply_oldest_first(clean):
    sid = _gathering(want=["counts.matrix"])
    _write_call(sid, input_tokens=10, output_tokens=1, cached=None, response='{"a": 1}')
    listed = authoring.calls(sid)
    assert [c["response"] for c in listed] == ['{"a": 1}']
    assert listed[0]["purpose"] == "goal" and listed[0]["input"] == 10


def test_the_calls_route_lists_them_and_refuses_an_unknown_session(clean):
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    client = TestClient(create_app())
    sid = _gathering(want=["counts.matrix"])
    _write_call(sid, input_tokens=10, output_tokens=1, cached=None, response="{}")
    assert client.get(f"/api/pipeline/authoring/{sid}/calls").json()[0]["response"] == "{}"
    assert client.get(f"/api/pipeline/authoring/{sid}").json()["usage"]["calls"] == 1
    assert client.get("/api/pipeline/authoring/" + "0" * 32 + "/calls").status_code == 404



def test_the_models_constraints_are_suggestions_never_in_the_goal(clean):
    """#176: *gene_level, normalised* arrived in the typed goal unasked; now the card offers."""
    draft_id = drafts.create(DraftGraph(), "t", "ana")
    sid = authoring.open_session(draft_id, mode=Mode.BUILD, who="ana")
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).goal = {
            "want": ["counts.matrix"],
            "constraints": {},
            "suggested": {"required_states": [{"type_id": "counts.matrix",
                                               "states": ["gene_level"]}]},
            "stated": [],
        }
    authoring.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring.offer_next_gap(sid)
    while (pid := authoring.pending_id(sid)) and "subject" in _payload(pid):
        options = [o for o in _payload(pid)["options"] if o not in ("dont_have", "value")]
        authoring.answer_gap(pid, options[0], None, by="ana")
    assert not authoring.compose_goal(sid).constraints.required_states
    card = _payload(authoring.pending_id(sid))["block"]
    assert card["suggested"] == [{"type_id": "counts.matrix", "states": ["gene_level"]}]


# ── each question phrased by a model (14.7.4, #167, #186) ─────────────────────────────────


def _asked(asks, option=None, value=None):
    from mendel_api.authoring.types import AskedGap

    return AskedGap(asks=asks, already_option=option, already_value=value)


def test_a_phrased_question_replaces_the_engines_words_in_place_and_keeps_the_options(clean):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    before = _payload(pid)["block"]
    authoring.store_phrasing(sid, "paired", _asked("Were both ends of each fragment sequenced?"))
    after = _payload(pid)["block"]
    assert after["asks"] == "Were both ends of each fragment sequenced?"
    assert after["phrasing"] == "done"
    assert [o["id"] for o in after["options"]] == [o["id"] for o in before["options"]]


def test_a_phrasing_that_arrives_after_the_answer_changes_nothing(clean):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    authoring.answer_gap(pid, "yes", None, by="ana")
    answered = _payload(pid)["block"]
    authoring.store_phrasing(sid, "paired", _asked("late", option="no"))
    assert _payload(pid)["block"] == answered


def test_already_pre_fills_and_an_unoffered_one_is_dropped(clean):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    authoring.store_phrasing(sid, "paired", _asked("Paired?", option="maybe"))
    assert not any(o["recommended"] for o in _payload(pid)["block"]["options"])
    authoring.store_phrasing(sid, "paired", _asked("Paired?", option="yes"))
    assert {o["id"] for o in _payload(pid)["block"]["options"] if o["recommended"]} == {"yes"}


def test_a_prefetched_phrasing_is_used_when_its_gap_is_offered(clean):
    sid = _gathering(want=["counts.matrix"])
    authoring.store_phrasing(sid, "strandedness", _asked("Which way was the library made?"))
    pid = _pending_for(sid, "strandedness")
    block = _payload(pid)["block"]
    assert block["asks"] == "Which way was the library made?" and block["phrasing"] == "done"


def test_without_a_model_nothing_is_pending_and_nothing_is_queued(clean, monkeypatch):
    import asyncio

    from mendel_api import jobs
    from mendel_api.services import authoring_jobs

    monkeypatch.setattr(authoring, "_model_configured", lambda: False)
    queued: list = []

    async def enqueue(*args, **kwargs):
        queued.append(kwargs)
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    sid = _gathering(want=["counts.matrix"])
    assert _payload(authoring.pending_id(sid))["block"]["phrasing"] == "none"
    asyncio.run(authoring_jobs.enqueue_phrasing(sid))
    assert queued == []


def test_phrasing_is_queued_for_this_gap_and_the_next_once_not_per_poll(clean, monkeypatch):
    import asyncio

    from mendel_api import jobs
    from mendel_api.services import authoring_jobs

    monkeypatch.setattr(authoring, "_model_configured", lambda: True)
    queued: list = []

    async def enqueue(*args, **kwargs):
        queued.append((args, kwargs))
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    sid = _gathering(want=["counts.matrix"])
    asyncio.run(authoring_jobs.enqueue_phrasing(sid))
    asyncio.run(authoring_jobs.enqueue_phrasing(sid))
    ids = [kw["job_id"] for _, kw in queued]
    assert len(set(ids)) == 2 and all(":phrase:" in i for i in ids)
    assert [args[2] for args, _ in queued[:2]] == ["fastq.reads", "genome.fasta"]


def test_a_question_waiting_for_its_words_counts_as_in_flight(clean, monkeypatch):
    monkeypatch.setattr(authoring, "_model_configured", lambda: True)
    sid = _gathering(want=["counts.matrix"])
    assert authoring.read(sid)["usage"]["in_flight"] is True
    authoring.phrasing_failed(sid, "fastq.reads")
    assert authoring.read(sid)["usage"]["in_flight"] is False
