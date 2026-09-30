"""The living pipeline over HTTP, with a fake queue, a fake model and a real database.

**Task 7's checkpoint is the first test here, and it is run literally**: submit a turn with a fake
queued job, reload immediately and see it pending, run the job, reload, and see the admitted
assistant blocks exactly once — then deliver the job a second time and see nothing change, not
even a second model call.

The queue is replaced at `authoring_jobs.enqueue_*` and the model at `authoring_jobs._client`,
the two seams those modules name for it. Redis and a provider are not what this file is about;
`test_forge_jobs.py` covers the queue and `test_authoring_ai.py` covers the calls.
"""

import asyncio
import json

import pytest
from comeni_ai import Client, ModelAccess, ModelUnavailableError
from fastapi.testclient import TestClient
from mendel_api import ai_worker, jobs, worker
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import AiInvocation
from mendel_api.routes import authoring as routes
from mendel_api.services import authoring_jobs
from sqlalchemy import select, text


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


needs_db = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def clean(monkeypatch):
    """Every table a session touches, in one statement, and no model configured by default."""
    for name in ("COMENI_AI_MODEL", "MENDEL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    tables = (
        "forge_message, forge_event, forge_revision, forge_adaptation, forge_catalogue_item, "
        "forge_source_snapshot, ai_invocation, pipeline_authoring_proposal, "
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft"
    )
    with session_scope() as session:
        session.execute(text(f"TRUNCATE TABLE {tables}"))
    yield


@pytest.fixture
def queue(monkeypatch):
    """Every enqueue answers `True` and is remembered."""
    queued: list[tuple] = []

    async def turn(session_id, seq):
        queued.append(("turn", session_id, seq))
        return True

    async def build(session_id, row_version):
        queued.append(("build", session_id, row_version))
        return True

    monkeypatch.setattr(authoring_jobs, "enqueue_turn", turn)
    monkeypatch.setattr(authoring_jobs, "enqueue_build", build)
    return queued


class Answers:
    def __init__(self, *bodies) -> None:
        self.bodies = list(bodies)
        self.sent: list[str] = []

    def send(self, access, prompt: str) -> str:
        self.sent.append(prompt)
        body = self.bodies.pop(0) if len(self.bodies) > 1 else self.bodies[0]
        if isinstance(body, Exception):
            raise body
        return body


def _model(monkeypatch, *bodies) -> Answers:
    transport = Answers(*bodies)
    monkeypatch.setattr(
        authoring_jobs,
        "_client",
        lambda: Client(ModelAccess(model="fake/test"), transport=transport),
    )
    return transport


GOAL = json.dumps(
    {
        "want": ["counts.matrix"],
        "constraints": {"required_states": {"counts.matrix": ["gene_level"]}},
        "ack": "A gene-level counts matrix — got it. A few questions first.",
        "questions": [],
    }
)
"""The model's answer under `builder.goal.v3`: the want only. What it needs is gathered."""

ANSWERS = {
    "read_length": ("value", 150),
    "strandedness": ("reverse", None),
    "paired": ("yes", None),
}
"""How `_gather` answers each measurement gap; every input gap is answered *I have it*."""


def _run(session_id: str, seq: int) -> str:
    return asyncio.run(authoring_jobs.answer_authoring_turn({}, session_id, seq))


def _begin(client, queue, mode: str = "build") -> tuple[str, int]:
    response = client.post(
        "/api/pipeline/authoring",
        json={"prompt": "I have RNA-seq reads and want gene counts", "mode": mode},
    )
    assert response.status_code == 201, response.text
    session_id = response.json()["session"]["id"]
    return session_id, queue[-1][2]


def _session(client, session_id: str) -> dict:
    response = client.get(f"/api/pipeline/authoring/{session_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _gather(client, session_id: str) -> dict:
    """Answer every gap through the route, as a person clicking would, until the card."""
    view = _session(client, session_id)
    while (pending := view["pending_proposal"]) and pending["kind"] == "gap":
        subject = _subject(session_id, pending["id"])
        option, value = ANSWERS.get(subject, ("have_it", None))
        response = client.post(
            f"/api/pipeline/authoring/{session_id}/proposals/{pending['id']}/decide",
            json={
                "decision": "accepted",
                "expected_revision": view["revision"],
                "option": option,
                "value": value,
            },
        )
        assert response.status_code == 200, response.text
        view = _session(client, session_id)
    return view


def _subject(session_id: str, proposal_id: str) -> str:
    from mendel_api.models import PipelineAuthoringProposal

    with session_scope() as db:
        return db.get(PipelineAuthoringProposal, proposal_id).payload["subject"]


def _goal_review(client, queue, monkeypatch, mode: str = "build") -> dict:
    session_id, seq = _begin(client, queue, mode)
    _model(monkeypatch, GOAL)
    _run(session_id, seq)
    return _gather(client, session_id)


# ── the checkpoint ────────────────────────────────────────────────────────────────────────


@needs_db
def test_a_turn_is_pending_on_reload_and_answered_exactly_once(client, clean, queue, monkeypatch):
    """**Task 7's checkpoint, literally.**"""
    session_id, seq = _begin(client, queue)
    assert queue == [("turn", session_id, seq)]

    pending = _session(client, session_id)
    assert [(t["role"], t["state"]) for t in pending["turns"]] == [
        ("person", "answered"),
        ("assistant", "pending"),
    ]

    transport = _model(monkeypatch, GOAL)
    _run(session_id, seq)
    answered = _session(client, session_id)
    assistant = [t for t in answered["turns"] if t["role"] == "assistant"]
    assert len(assistant) == 1 and assistant[0]["state"] == "answered"
    assert [b["kind"] for b in assistant[0]["blocks"]] == ["narrative"]
    # The want is read; what it needs is the engine's to ask, one gap at a time (14.7.3).
    assert answered["phase"] == "gathering"
    assert answered["pending_proposal"]["kind"] == "gap"

    # A second delivery of the same job: nothing changes, and no second call is made.
    _run(session_id, seq)
    again = _session(client, session_id)
    assert again["turns"] == answered["turns"]
    assert len(transport.sent) == 1
    with session_scope() as db:
        assert len(db.scalars(select(AiInvocation)).all()) == 1


def test_the_turn_job_is_named_by_its_session_and_turn(monkeypatch):
    """`builder:turn:<session>:<seq>` — derived from what the work is about, so two deliveries
    collide at the queue."""
    seen = {}

    async def enqueue(name, *args, job_id=None, queue=jobs.DEFAULT_QUEUE):
        seen.update(name=name, args=args, job_id=job_id, queue=queue)
        return True

    monkeypatch.setattr(jobs, "enqueue", enqueue)
    asyncio.run(authoring_jobs.enqueue_turn("abc123", 3))

    assert seen == {
        "name": "answer_authoring_turn",
        "args": ("abc123", 3),
        "job_id": "builder:turn:abc123:3",
        "queue": jobs.AI_QUEUE,
    }


# ── the visible states ────────────────────────────────────────────────────────────────────


@needs_db
def test_no_configured_model_is_a_visible_failure_and_retry_queues_a_fresh_turn(
    client, clean, queue
):
    session_id, seq = _begin(client, queue)
    _run(session_id, seq)
    failed = _session(client, session_id)

    notice = failed["turns"][-1]["blocks"][0]
    assert notice["kind"] == "notice" and notice["code"] == "MI0106"
    assert failed["phase"] == "failed" and failed["model_configured"] is False

    response = client.post(f"/api/pipeline/authoring/{session_id}/retry")
    assert response.status_code == 200, response.text
    assert response.json() == {"phase": "understanding", "queued": True}
    retried = _session(client, session_id)
    assert retried["turns"][-1]["state"] == "pending"
    assert queue[-1][2] > seq, "retry reopened the failed turn instead of adding one"


@needs_db
def test_a_provider_failure_reaches_the_page_as_a_code_and_never_as_its_own_words(
    client, clean, queue, monkeypatch
):
    session_id, seq = _begin(client, queue)
    _model(monkeypatch, ModelUnavailableError("MA0007: fake/test: http://10.0.0.5:11434 refused"))
    _run(session_id, seq)
    body = client.get(f"/api/pipeline/authoring/{session_id}").text

    assert "MA0007" in body
    assert "10.0.0.5" not in body


@needs_db
def test_a_refused_answer_leaves_the_session_where_it_was(client, clean, queue, monkeypatch):
    """A badly-shaped answer is not a failure of the session. The person can say it again."""
    session_id, seq = _begin(client, queue)
    _model(monkeypatch, "I think you want featureCounts.")
    _run(session_id, seq)
    session = _session(client, session_id)

    assert session["phase"] == "understanding"
    assert session["turns"][-1]["blocks"][0]["code"] == "MA0004"


# ── the deterministic requests ────────────────────────────────────────────────────────────


@needs_db
def test_accepting_the_goal_builds_inline_and_offers_the_first_step(
    client, clean, queue, monkeypatch
):
    """Build resolves in the request — no queue between a click and its answer."""
    session = _goal_review(client, queue, monkeypatch)
    proposal = session["pending_proposal"]
    response = client.post(
        f"/api/pipeline/authoring/{session['id']}/proposals/{proposal['id']}/decide",
        json={"decision": "accepted", "expected_revision": session["revision"]},
    )
    assert response.status_code == 200, response.text
    decided = response.json()

    assert decided["phase"] == "building" and decided["queued"] is False
    building = _session(client, session["id"])
    assert building["pending_proposal"]["id"] == decided["next_proposal"]
    assert building["pending_proposal"]["block"]["kind"] == "step_proposal"
    # The step on offer has its final position already; nothing not yet shown has one.
    offered = building["pending_proposal"]["block"]["node"]
    assert set(building["placement"]) == {offered}
    assert [q for q in queue if q[0] == "build"] == []


@needs_db
def test_a_spawn_goal_is_resolved_on_the_ai_worker(client, clean, queue, monkeypatch):
    """Spawn gathers from the person (14.7.3); the last answer confirms the card by policy and
    the blueprint is resolved on the AI worker, never inline in the request."""
    session_id, seq = _begin(client, queue, "spawn")
    _model(monkeypatch, GOAL)
    _run(session_id, seq)
    session = _gather(client, session_id)

    assert session["phase"] == "resolving"
    assert [q for q in queue if q[0] == "build"] == [("build", session_id, session["row_version"])]
    asyncio.run(authoring_jobs.build_authoring_blueprint({}, session_id))
    # Spawn does not stop at the first step: the policy accepts every settled one, so the RNA-seq
    # blueprint — no tier-4 step choice — is complete by the end of the job.
    assert _session(client, session_id)["phase"] == "complete"


@needs_db
def test_accepting_a_step_moves_the_revision_and_the_preview_follows(
    client, clean, queue, monkeypatch
):
    session = _goal_review(client, queue, monkeypatch)
    goal_id = session["pending_proposal"]["id"]
    goal = client.post(
        f"/api/pipeline/authoring/{session['id']}/proposals/{goal_id}/decide",
        json={"decision": "accepted", "expected_revision": 0},
    ).json()

    before = client.get(f"/api/pipeline/authoring/{session['id']}/preview").json()
    decided = client.post(
        f"/api/pipeline/authoring/{session['id']}/proposals/{goal['next_proposal']}/decide",
        json={"decision": "accepted", "expected_revision": goal["revision"], "option": "keep"},
    ).json()
    after = client.get(f"/api/pipeline/authoring/{session['id']}/preview").json()

    assert before == {"revision": goal["revision"], "state": "empty", "text": "", "findings": []}
    assert decided["revision"] == goal["revision"] + 1
    history = [d for d in _session(client, session["id"])["history"] if d["kind"] != "gap"]
    assert [(d["kind"], d["state"]) for d in history] == [
        ("goal", "accepted"),
        ("step", "accepted"),
    ]
    assert history[1]["chosen_contract"] == "nf-core/star/genomegenerate@1.11.0"
    assert after["revision"] == decided["revision"]
    assert "star_genomegenerate" in after["text"]


@needs_db
def test_an_old_picture_of_the_draft_is_refused_with_its_code(client, clean, queue, monkeypatch):
    session = _goal_review(client, queue, monkeypatch)
    proposal = session["pending_proposal"]
    response = client.post(
        f"/api/pipeline/authoring/{session['id']}/proposals/{proposal['id']}/decide",
        json={"decision": "accepted", "expected_revision": 9},
    )

    assert response.status_code == 422
    assert response.json()["detail"].startswith("MI0201")


@needs_db
def test_a_proposal_cannot_be_decided_through_another_sessions_path(
    client, clean, queue, monkeypatch
):
    first = _goal_review(client, queue, monkeypatch)
    second, _ = _begin(client, queue)
    response = client.post(
        f"/api/pipeline/authoring/{second}/proposals/{first['pending_proposal']['id']}/decide",
        json={"decision": "accepted", "expected_revision": 0},
    )
    assert response.status_code == 404


@needs_db
def test_a_follow_up_during_goal_review_is_answered_as_an_explanation(
    client, clean, queue, monkeypatch
):
    session = _goal_review(client, queue, monkeypatch)
    response = client.post(
        f"/api/pipeline/authoring/{session['id']}/messages", json={"text": "why these steps?"}
    )
    assert response.status_code == 202, response.text
    seq = response.json()["seq"]

    _model(monkeypatch, json.dumps({"explain": "counting needs aligned, sorted reads"}))
    _run(session["id"], seq)
    reply = _session(client, session["id"])["turns"][-1]

    assert reply["state"] == "answered"
    assert reply["blocks"][0]["kind"] == "narrative"


@needs_db
def test_a_follow_up_while_gathering_is_answered_not_crashed(client, clean, queue, monkeypatch):
    """While gathering, the session's goal column holds the want and the model's summary, which
    is not a `Goal`; grounding a follow-up on it must not fail validation (14.7.3)."""
    session_id, seq = _begin(client, queue)
    _model(monkeypatch, GOAL)
    _run(session_id, seq)
    response = client.post(
        f"/api/pipeline/authoring/{session_id}/messages", json={"text": "why a genome?"}
    )
    _model(monkeypatch, json.dumps({"explain": "reads are aligned against it"}))
    _run(session_id, response.json()["seq"])
    reply = _session(client, session_id)["turns"][-1]
    assert reply["state"] == "answered", reply


# ── what the boundary will not accept ─────────────────────────────────────────────────────


def test_starting_a_session_accepts_prose_and_a_mode_and_nothing_else():
    """No name, no path, no model id. Listed literally, as `test_forge_routes.py` lists its own:
    every one of those would be a `str`, so no rule could tell them apart."""
    assert set(routes.BeginAuthoring.model_fields) == {"prompt", "mode"}
    assert set(routes.SayToAuthoring.model_fields) == {"text"}
    assert set(routes.DecideProposal.model_fields) == {
        "decision", "expected_revision", "goal", "option", "value"
    }


def test_the_authoring_jobs_run_on_the_ai_worker_and_nowhere_else():
    """`AIWorkerSettings.functions` is the allowlist of what may reach a provider."""
    ai = set(ai_worker.AIWorkerSettings.functions)
    ordinary = set(worker.WorkerSettings.functions)

    for job in (authoring_jobs.answer_authoring_turn, authoring_jobs.build_authoring_blueprint):
        assert job in ai, f"{job.__name__} is not on the AI worker"
        assert job not in ordinary, f"{job.__name__} would run beside a source sync"
    assert not ai & ordinary



# ── Task 10: editing without a model, and the receipt the server writes ───────────────────


def _building(client, queue, monkeypatch) -> tuple[dict, dict]:
    session = _goal_review(client, queue, monkeypatch)
    goal = client.post(
        f"/api/pipeline/authoring/{session['id']}/proposals/{session['pending_proposal']['id']}/decide",
        json={"decision": "accepted", "expected_revision": 0},
    ).json()
    return _session(client, session["id"]), goal


@needs_db
def test_an_edited_goal_is_confirmed_without_a_model_call(client, clean, queue, monkeypatch):
    """A structured edit on the goal card needs no model — the person corrected a field, and the
    engine can check a field."""
    session = _goal_review(client, queue, monkeypatch)
    transport = _model(monkeypatch, GOAL)
    edited = dict(session["pending_proposal"]["block"]["goal"])
    edited["want"] = ["counts.matrix", "qc.report"]

    response = client.post(
        f"/api/pipeline/authoring/{session['id']}/proposals/{session['pending_proposal']['id']}/decide",
        json={"decision": "accepted", "expected_revision": 0, "goal": edited},
    )
    assert response.status_code == 200, response.text
    assert _session(client, session["id"])["goal"]["want"] == ["counts.matrix", "qc.report"]
    assert transport.sent == []


@needs_db
def test_an_edited_goal_naming_an_undeclared_type_is_refused_like_a_models(
    client, clean, queue, monkeypatch
):
    session = _goal_review(client, queue, monkeypatch)
    edited = dict(session["pending_proposal"]["block"]["goal"])
    edited["want"] = ["rnaseq.counts"]

    response = client.post(
        f"/api/pipeline/authoring/{session['id']}/proposals/{session['pending_proposal']['id']}/decide",
        json={"decision": "accepted", "expected_revision": 0, "goal": edited},
    )
    assert response.status_code == 422
    assert response.json()["detail"].startswith("MI0204")
    assert _session(client, session["id"])["phase"] == "goal_review"


@needs_db
def test_a_step_proposal_says_what_it_reads_as_well_as_what_it_makes(
    client, clean, queue, monkeypatch
):
    building, _ = _building(client, queue, monkeypatch)
    block = building["pending_proposal"]["block"]
    assert block["node"] == "star_genomegenerate"
    assert set(block["consumes"]) == {"genome.fasta", "annotation.gtf"}


@needs_db
def test_a_direct_edit_writes_a_receipt_the_server_composed(client, clean, queue, monkeypatch):
    """The receipt is derived from the difference — the browser sends a graph and nothing that
    could be told to the log."""
    building, goal = _building(client, queue, monkeypatch)
    graph = building["graph"]
    graph["nodes"].append({"id": "fastqc_1", "contract_id": "nf-core/fastqc@0.12.1", "params": []})

    response = client.post(
        f"/api/pipeline/authoring/{building['id']}/edits", json={"graph": graph}
    )
    assert response.status_code == 200, response.text
    after = _session(client, building["id"])

    receipt = after["turns"][-1]["blocks"][0]
    assert receipt["kind"] == "receipt"
    assert receipt["summary"] == "you added FASTQC_1"
    assert after["revision"] == goal["revision"] + 1


@needs_db
def test_an_edit_re_offers_the_pending_step_at_the_new_revision(client, clean, queue, monkeypatch):
    """Otherwise the proposal on the card would be stale the moment somebody moved a box, and
    accepting it would be refused with nothing left to answer."""
    building, _ = _building(client, queue, monkeypatch)
    before = building["pending_proposal"]
    graph = building["graph"]
    graph["nodes"].append({"id": "fastqc_1", "contract_id": "nf-core/fastqc@0.12.1", "params": []})

    edited = client.post(f"/api/pipeline/authoring/{building['id']}/edits", json={"graph": graph})
    after = _session(client, building["id"])

    assert edited.json()["reoffered"] == after["pending_proposal"]["id"] != before["id"]
    assert after["pending_proposal"]["block"]["node"] == before["block"]["node"]
    assert after["pending_proposal"]["draft_revision"] == after["revision"]


@needs_db
def test_adding_the_offered_step_by_hand_moves_the_offer_on(client, clean, queue, monkeypatch):
    building, _ = _building(client, queue, monkeypatch)
    offered = building["pending_proposal"]["block"]
    graph = building["graph"]
    graph["nodes"].append({"id": offered["node"], "contract_id": offered["contract"], "params": []})

    client.post(f"/api/pipeline/authoring/{building['id']}/edits", json={"graph": graph})
    after = _session(client, building["id"])

    assert after["pending_proposal"] is not None
    assert after["pending_proposal"]["block"]["node"] != offered["node"]


@needs_db
def test_an_edit_that_changes_nothing_writes_nothing(client, clean, queue, monkeypatch):
    building, _ = _building(client, queue, monkeypatch)
    turns = len(building["turns"])
    client.post(f"/api/pipeline/authoring/{building['id']}/edits",
                json={"graph": building["graph"]})
    after = _session(client, building["id"])
    assert len(after["turns"]) == turns
    assert after["revision"] == building["revision"]


def test_the_vocabulary_a_goal_card_may_use_is_the_registrys():
    client = TestClient(create_app())
    types = client.get("/api/pipeline/authoring/vocabulary").json()["types"]
    assert "counts.matrix" in types
    assert "gene_level" in types["counts.matrix"]


def test_an_edit_body_is_the_graph_and_nothing_else():
    assert set(routes.EditAuthoringDraft.model_fields) == {"graph"}


# ── the family step (#194) ────────────────────────────────────────────────────────────────


FAMILY = json.dumps(
    {"fits": "yes", "families": ["counts"], "ack": "Gene counts — got it. A few questions first."}
)
NO_FIT = json.dumps(
    {"fits": "no", "families": [], "ack": "Variant calls — noted.", "unclear": "Which result?"}
)
GOAL_V7 = json.dumps({"want": ["counts.matrix"], "constraints": {}, "questions": []})


def _family_step_on(monkeypatch):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "family_step_from", 0)


@needs_db
def test_the_family_call_acknowledges_and_the_goal_call_follows(client, clean, queue, monkeypatch):
    _family_step_on(monkeypatch)
    session_id, seq = _begin(client, queue)
    transport = _model(monkeypatch, FAMILY, GOAL_V7)
    _run(session_id, seq)
    view = _session(client, session_id)
    assistant = [t for t in view["turns"] if t["role"] == "assistant"][0]
    assert assistant["blocks"][0]["text"] == "Gene counts — got it. A few questions first."
    assert view["phase"] == "gathering" and len(transport.sent) == 2


@needs_db
def test_no_family_fits_asks_and_never_calls_the_goal(client, clean, queue, monkeypatch):
    _family_step_on(monkeypatch)
    session_id, seq = _begin(client, queue)
    _model(
        monkeypatch,
        NO_FIT,
    )
    _run(session_id, seq)
    view = _session(client, session_id)
    blocks = [t for t in view["turns"] if t["role"] == "assistant"][0]["blocks"]
    assert [b["kind"] for b in blocks] == ["narrative", "question"]
    assert blocks[1]["asks"] == "Which result?"
    assert view["phase"] == "understanding"
    assert "builder.family.v2" in {
        r.prompt_id for r in _rows_now()
    } and "builder.goal.v7" not in {r.prompt_id for r in _rows_now()}, "the goal call is not made"


@needs_db
def test_a_turn_answered_with_a_question_makes_exactly_one_call(client, clean, queue, monkeypatch):
    """Issue 201: the turn is answered, so nothing else may spend a call on it."""
    _family_step_on(monkeypatch)
    session_id, seq = _begin(client, queue)
    transport = _model(
        monkeypatch,
        NO_FIT,
    )
    _run(session_id, seq)
    assert len(transport.sent) == 1


@needs_db
def test_a_goal_answer_that_asks_makes_exactly_one_call(client, clean, queue, monkeypatch):
    """Issue 201, the one-step path: the goal call asks, the session stays in understanding."""
    session_id, seq = _begin(client, queue)
    asked = {
        "want": ["counts.matrix"],
        "ack": "Counts — noted.",
        "questions": [{"asks": "Gene or transcript level?", "why_open": "Both are possible"}],
    }
    transport = _model(monkeypatch, json.dumps(asked))
    _run(session_id, seq)
    assert len(transport.sent) == 1
    assert _session(client, session_id)["phase"] == "understanding"


def _rows_now():
    with session_scope() as db:
        return list(db.scalars(select(AiInvocation)).all())


@needs_db
def test_no_family_and_no_question_gets_the_engines_question(client, clean, queue, monkeypatch):
    _family_step_on(monkeypatch)
    session_id, seq = _begin(client, queue)
    _model(monkeypatch, json.dumps({"fits": "no", "families": [], "ack": "Noted."}))
    _run(session_id, seq)
    blocks = [t for t in _session(client, session_id)["turns"] if t["role"] == "assistant"][0][
        "blocks"
    ]
    assert blocks[1]["asks"] == "Which kind of result do you want?"


@needs_db
def test_a_no_with_a_family_listed_still_asks(client, clean, queue, monkeypatch):
    """#202: the families beside a `no` are ignored, never half-trusted."""
    _family_step_on(monkeypatch)
    session_id, seq = _begin(client, queue)
    transport = _model(
        monkeypatch,
        json.dumps({"fits": "no", "families": ["annotation"], "ack": "Variant calls — noted."}),
    )
    _run(session_id, seq)
    view = _session(client, session_id)
    blocks = [t for t in view["turns"] if t["role"] == "assistant"][0]["blocks"]
    assert blocks[1]["asks"] == "Which kind of result do you want?"
    assert view["phase"] == "understanding" and len(transport.sent) == 1


@needs_db
def test_unsure_asks_with_the_models_question(client, clean, queue, monkeypatch):
    _family_step_on(monkeypatch)
    session_id, seq = _begin(client, queue)
    _model(
        monkeypatch,
        json.dumps(
            {"fits": "unsure", "families": [], "ack": "Noted.", "unclear": "Counts or peaks?"}
        ),
    )
    _run(session_id, seq)
    blocks = [t for t in _session(client, session_id)["turns"] if t["role"] == "assistant"][0][
        "blocks"
    ]
    assert blocks[1]["asks"] == "Counts or peaks?"


@needs_db
def test_a_yes_with_nothing_listed_asks(client, clean, queue, monkeypatch):
    """Review focus 2: v7 shown no family would be shown nothing."""
    _family_step_on(monkeypatch)
    session_id, seq = _begin(client, queue)
    transport = _model(monkeypatch, json.dumps({"fits": "yes", "families": [], "ack": "Ok."}))
    _run(session_id, seq)
    assert _session(client, session_id)["phase"] == "understanding"
    assert len(transport.sent) == 1
