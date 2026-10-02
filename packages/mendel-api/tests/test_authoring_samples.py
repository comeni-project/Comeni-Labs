"""An uploaded sample answers a gap: every decided fact recorded as measured, the person's word
standing where it disagrees, nothing guessed (14.7.6.4).

Driven through the service against the throwaway database, with inspections built by hand: the
inspection itself is `test_inspect.py`'s.
"""

import pytest
from comeni_core.plan.draft import DraftGraph
from mendel_api.authoring import state as st
from mendel_api.authoring.types import Mode
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringProposal, PipelineAuthoringSession
from mendel_api.services import authoring, drafts, inspect
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


def _gathering(want: list[str]) -> str:
    draft_id = drafts.create(DraftGraph(), "t", "ana")
    sid = authoring.open_session(draft_id, mode=Mode.BUILD, who="ana")
    with session_scope() as db:
        db.get(PipelineAuthoringSession, sid).goal = {"want": want, "constraints": {}, "stated": []}
    authoring.move(sid, st.Event.WANT_RETURNED, row_version=1)
    authoring.offer_next_gap(sid)
    return sid


def _payload(pid: str) -> dict:
    with session_scope() as db:
        return dict(db.get(PipelineAuthoringProposal, pid).payload)


def _pending_for(sid: str, subject: str) -> str:
    while (pid := authoring.pending_id(sid)) and _payload(pid)["subject"] != subject:
        skip = ("dont_have", "value", "not_sure", "upload")
        options = [o for o in _payload(pid)["options"] if o not in skip]
        authoring.answer_gap(pid, options[0], None, by="ana")
    return authoring.pending_id(sid)


def _facts(sid: str) -> list[dict]:
    with session_scope() as db:
        return list(db.get(PipelineAuthoringSession, sid).facts)


def _measured(**values) -> inspect.Inspection:
    return inspect.Inspection(
        outcome="measured",
        type_id="fastq.reads",
        steps=[],
        facts=[
            inspect.InspectedFact(
                measurement=k,
                value=v,
                pieces=["fastq@1.0.0", f"{k}@1.0.0"],
                evidence={"records": 2000, "rows": 1000, "shorter_file": "x_R2.fq"},
            )
            for k, v in values.items()
        ],
    )


def test_a_measurement_gap_offers_upload_in_place_of_not_sure(clean):
    sid = _gathering(["counts.matrix"])
    options = _payload(_pending_for(sid, "read_length"))["options"]
    assert "upload" in options and "not_sure" not in options and "cant_share" in options


def test_an_input_an_inspector_reads_offers_upload(clean):
    sid = _gathering(["counts.matrix"])
    options = _payload(_pending_for(sid, "fastq.reads"))["options"]
    assert "upload" in options and "have_it" in options


def test_a_measurement_no_inspector_measures_keeps_not_sure(clean):
    sid = _gathering(["counts.matrix"])
    options = _payload(_pending_for(sid, "strandedness"))["options"]
    assert "not_sure" in options and "upload" not in options


def test_clicking_upload_records_nothing(clean):
    """The option opens the upload; the click itself is not an answer."""
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    with pytest.raises(ValueError, match="MI0205"):
        authoring.answer_gap(pid, "upload", None, by="ana")


def test_an_upload_records_every_decided_fact_as_measured(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")  # gaps come inputs, paired, read_length, strandedness
    answer = authoring.answer_with_sample(pid, _measured(read_length=150, paired=True), by="ana")
    facts = _facts(sid)
    rl = next(f for f in facts if f["subject"] == "read_length")
    assert rl["source"] == "measured" and rl["value"] == 150
    assert rl["pieces"] == ["fastq@1.0.0", "read_length@1.0.0"]
    assert set(answer.recorded) == {"read_length", "paired"}
    assert answer.kept == ["fastq.reads"], "the person already said they have reads"
    assert all(f.get("sample") is None for f in facts)
    assert all("shorter_file" not in (f.get("evidence") or {}) for f in facts)


def test_what_the_person_said_is_kept_and_the_difference_reported(clean):
    """Review focus 4: the person said single-end; the file reads as a pair."""
    sid = _gathering(["counts.matrix"])
    authoring.answer_gap(_pending_for(sid, "paired"), "no", None, by="ana")
    pid = _pending_for(sid, "read_length")
    answer = authoring.answer_with_sample(pid, _measured(read_length=150, paired=True), by="ana")
    assert answer.disagreed == ["paired"] and "read_length" in answer.recorded
    assert next(f for f in _facts(sid) if f["subject"] == "paired")["value"] is False


def test_an_undetermined_answer_leaves_the_gap_open(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    undecided = _measured(paired=True)
    undecided.facts.append(
        inspect.InspectedFact(measurement="read_length", undetermined="lengths vary: 100–151")
    )
    authoring.answer_with_sample(pid, undecided, by="ana")
    assert authoring.pending_id(sid) == pid
    assert next(f for f in _facts(sid) if f["subject"] == "paired")["value"] is True


def test_a_second_upload_to_an_answered_gap_is_refused(clean):
    """Review focus 3: two tabs. The second is refused like a duplicate click."""
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    authoring.answer_with_sample(pid, _measured(read_length=150), by="ana")
    before = _facts(sid)
    with pytest.raises(ValueError, match="MI0203"):
        authoring.answer_with_sample(pid, _measured(read_length=150), by="ana")
    assert _facts(sid) == before


def test_compose_goal_carries_the_pieces_and_only_declared_counts(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    authoring.answer_with_sample(pid, _measured(read_length=150), by="ana")
    goal = authoring.compose_goal(sid)
    m = next(m for m in goal.profile.measurements if m.measurement == "read_length")
    assert m.source.value == "measured" and m.pieces == ["fastq@1.0.0", "read_length@1.0.0"]
    assert m.evidence.model_dump(mode="json") == {"records": 2000, "rows": 1000}
