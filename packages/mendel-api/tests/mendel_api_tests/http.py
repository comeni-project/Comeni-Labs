"""Reusable http scenarios and fixtures for API tests."""

import asyncio
import json

import pytest
from comeni_ai import Client, ModelAccess
from fastapi.testclient import TestClient
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.models import AiInvocation
from mendel_api.services import authoring_jobs
from mendel_api.services import session as session_service
from mendel_api.stages import _jobs
from sqlalchemy import select

from mendel_api_tests.database import reachable, truncate

needs_db = pytest.mark.skipif(not reachable(), reason="no database — run `make test-db`")


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
        "pipeline_authoring_turn, pipeline_authoring_session, pipeline_draft, gate_run"
    )
    with session_scope() as session:
        session.execute(truncate(f"TRUNCATE TABLE {tables}"))
    yield


@pytest.fixture
def queue(monkeypatch):
    """Every enqueue answers `True` and is remembered."""
    queued: list[tuple] = []

    async def enqueue(job):  # every job an action asks for, after its commit (plan 1c)
        if job.name == _jobs.ANSWER:
            queued.append(("turn", *job.args))
        return True

    monkeypatch.setattr(session_service, "_enqueue", enqueue)
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
        lambda *_: Client(ModelAccess(model="fake/test"), transport=transport),
    )
    return transport


GOAL = json.dumps(
    {
        "wants": [{"type": "counts.matrix"}],
        "requires": [{"type": "counts.matrix", "states": ["gene_level"]}],
        "say": "A gene-level counts matrix — got it. A few questions first.",
        "questions": [],
    }
)
"""The model's answer under `builder.goal.v8` (#307): the want, and a state it suggests (no
quote, so offered on the card, as the old `constraints` were). What it needs is gathered."""


ANSWERS = {
    "read_length": ("value", 150),
    "strandedness": ("reverse", None),
    "paired": ("yes", None),
}
"""How `_gather` answers each measurement gap; every input gap is answered *I have it*."""


def _run(session_id: str, seq: int) -> str:
    return asyncio.run(authoring_jobs.answer_authoring_turn({}, session_id, seq))


def _begin(client, queue) -> tuple[str, int]:
    response = client.post(
        "/api/pipeline/authoring",
        json={"prompt": "I have RNA-seq reads and want gene counts"},
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


def _goal_review(client, queue, monkeypatch) -> dict:
    session_id, seq = _begin(client, queue)
    _model(monkeypatch, GOAL)
    _run(session_id, seq)
    return _gather(client, session_id)


# ── Task 10: editing without a model, and the receipt the server writes ───────────────────
def _building(client, queue, monkeypatch) -> tuple[dict, dict]:
    session = _goal_review(client, queue, monkeypatch)
    goal = client.post(
        f"/api/pipeline/authoring/{session['id']}/proposals/{session['pending_proposal']['id']}/decide",
        json={"decision": "accepted", "expected_revision": 0},
    ).json()
    return _session(client, session["id"]), goal


# ── the family step (#194) ────────────────────────────────────────────────────────────────
FAMILY = json.dumps(
    {"fits": "yes", "families": ["counts"], "ack": "Gene counts — got it. A few questions first."}
)


NO_FIT = json.dumps(
    {"fits": "no", "families": [], "ack": "Variant calls — noted.", "unclear": "Which result?"}
)


GOAL_V7 = json.dumps({"wants": [{"type": "counts.matrix"}], "questions": []})


def _family_step_on(monkeypatch):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "family_step_from", 0)


def _rows_now():
    with session_scope() as db:
        return list(db.scalars(select(AiInvocation)).all())


UNREACHABLE = json.dumps({"wants": [{"type": "annotation.gtf"}], "questions": []})
"""`annotation.gtf` is declared in the real registry, and nothing produces it."""
