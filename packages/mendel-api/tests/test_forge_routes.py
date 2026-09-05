"""The forge's HTTP surface: what it exposes, what it refuses, and what it will not accept.

**The allowlist tests are the point of this file.** §7 opens with *no request body accepts a
path, provider key, base URL, or model name*, and that cannot be checked by a rule — every one
of those is a `str`. So the fields are listed literally, the way `test_egress.py` lists what may
cross a door and `test_ai_schemas.py` lists what a response may carry.
"""

import pytest
from fastapi.testclient import TestClient
from mendel_api.db import session_scope
from mendel_api.main import create_app
from mendel_api.routes import forge as routes
from mendel_api.services import forge_jobs
from pydantic import BaseModel
from sqlalchemy import text


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
def no_queue(monkeypatch):
    """Every enqueue answers `True` without a broker.

    Redis is not what these tests are about — `test_forge_jobs.py` covers the queue — and a
    route test that needed one would be a route test nobody runs in CI.
    """
    queued = []

    async def fake(*args, **kwargs):
        queued.append((args, kwargs))
        return True

    for name in ("enqueue_sync", "enqueue_scaffold", "enqueue_generation", "enqueue_publish"):
        monkeypatch.setattr(forge_jobs, name, fake)

    async def fake_answer(adaptation_id, message_id):
        queued.append((adaptation_id, message_id))
        return True

    monkeypatch.setattr(forge_jobs, "enqueue_answer", fake_answer)
    return queued


# ── the boundary §7 opens with ────────────────────────────────────────────────────────


REQUEST_FIELDS = {
    "Reason": {"reason"},
    "Ask": {"message"},
    "Start": {"catalogue_item_id"},
    "Approval": {"reason", "rule_candidate_ids"},
}
"""Every field of every request body on this surface, listed literally.

**A path cannot be recognised by its type.** `registry_root`, `model`, `base_url` and `api_key`
are all `str`, exactly like `reason` — so what stops one arriving is that adding it means
editing this dict, which is a diff that says *these are all the things a caller may send*.

That is `test_egress.py`'s construction for the outbound side and
`test_ai_schemas.py`'s for the model's answers. This is the third place the same argument
holds, and it is the one a browser reaches.
"""


def test_no_request_body_accepts_a_path_a_key_or_a_model():
    """§7's opening sentence, as a check.

    Every network, filesystem, model and registry choice comes from `settings`. A body that
    could name one would be a second answer to a question that file answers once — and worse,
    an answer a *browser* supplies.
    """
    for name, fields in REQUEST_FIELDS.items():
        model = getattr(routes, name)
        assert set(model.model_fields) == fields, (
            f"{name} gained or lost a field. If it is a path, a model id, a base URL or a "
            "credential, a caller can now choose what only `settings` may."
        )
    assert REQUEST_FIELDS, "an empty table would make this loop assert nothing"


RESPONSES = {
    # What a `202` carries — checked by the 202 tests, which assert what it says rather than
    # what a caller may send.
    "Queued",
    # The catalogue's answer. A row is a tool plus where it stands with us, and neither half
    # is anything a browser supplies.
    "CatalogueRow",
    "CataloguePage",
}
"""Models on this surface that a caller never sends.

**Listed rather than subtracted by a rule**, for the same reason `REQUEST_FIELDS` is literal:
there is no property of a Pydantic model that says *this one is outbound*, so the only thing
that stops a request body being waved through as "probably a response" is that somebody had to
type its name here and say which it is.
"""


def test_the_table_covers_every_request_body_on_this_surface():
    """**The hole in the test above.** It walks its own table, so a body added to `forge.py`
    and not to the table is a body nothing inspects — the same shape as the egress guard taking
    its roots from `vars(egress)` rather than from `DOORS`, which walked three doors out of
    four while reporting green."""
    defined = {
        name
        for name, obj in vars(routes).items()
        if isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj.__module__ == routes.__name__
    }
    assert defined - RESPONSES == set(REQUEST_FIELDS)


def test_every_request_body_forbids_unknown_fields():
    """`extra="forbid"` is what makes the allowlist mean anything. A body that ignored an
    unknown key would accept `{"reason": "x", "registry_root": "/etc"}` and the test above
    would be describing a model rather than a boundary."""
    for name in REQUEST_FIELDS:
        assert getattr(routes, name).model_config.get("extra") == "forbid", name


def test_a_body_carrying_a_registry_root_is_rejected(client, no_queue):
    """The allowlist as behaviour rather than as reflection — one asserts the shape, this
    asserts what an actual request does with it."""
    answer = client.post(
        "/api/forge/adaptations",
        json={"catalogue_item_id": "a" * 64, "registry_root": "/etc"},
    )
    assert answer.status_code == 422


# ── the schema both consumers read ────────────────────────────────────────────────────


def test_every_forge_operation_has_a_stable_operation_id(client):
    """`frontend/src/api/` is generated from this document and an agent driving Mendel reads
    the same one, so an operation without an `operationId` is a gap in both consumers at once —
    and a generated client names it something invented from the path, which then changes when
    the path does."""
    schema = client.get("/openapi.json").json()
    forge = {
        path: spec
        for path, spec in schema["paths"].items()
        if path.startswith("/api/forge")
    }
    assert forge, "no forge paths in the schema"
    ids = []
    for path, spec in forge.items():
        for method, operation in spec.items():
            assert "operationId" in operation, f"{method.upper()} {path}"
            assert operation["tags"] == ["forge"], f"{method.upper()} {path}"
            ids.append(operation["operationId"])
    assert len(ids) == len(set(ids)), "two operations share an id"


def test_the_surface_is_the_paths_the_plan_names(client):
    """§7 lists them. Held literally so an endpoint arriving without a line in the plan is a
    diff somebody has to look at.

    **Two arrived in Task 11 that §7 does not list**, and they are recorded here rather than
    waved through: `/candidate` and `/approval`. §8.5 asks the review page for a semantic
    graph, per-field provenance, side-by-side files, clickable evidence and an approval button
    that explains itself — and every one of those is a *read* the twelve paths could not
    answer. `/adaptations/{id}` carries the workflow row and its revisions; the candidate is
    files in the workspace and the refusals are computed, so neither could be folded in without
    making the detail response mean two things.
    """
    schema = client.get("/openapi.json").json()
    assert sorted(p for p in schema["paths"] if p.startswith("/api/forge")) == [
        "/api/forge/adaptations",
        "/api/forge/adaptations/{adaptation_id}",
        "/api/forge/adaptations/{adaptation_id}/approval",
        "/api/forge/adaptations/{adaptation_id}/approve",
        "/api/forge/adaptations/{adaptation_id}/archive",
        "/api/forge/adaptations/{adaptation_id}/candidate",
        "/api/forge/adaptations/{adaptation_id}/changes",
        "/api/forge/adaptations/{adaptation_id}/messages",
        "/api/forge/adaptations/{adaptation_id}/retry",
        "/api/forge/adaptations/{adaptation_id}/revisions/{revision_id}",
        "/api/forge/catalogue",
        "/api/forge/catalogue/{item_id}",
        "/api/forge/overview",
        "/api/forge/sources/sync",
    ]


def test_the_older_endpoints_are_still_served(client):
    """§8's last box: *keep existing endpoints alive during the migration*. `/tools`,
    `/sources` and `/contracts` are what the built SPA reads today, and removing them in the
    change that adds their replacement breaks the interface for as long as the rework takes."""
    schema = client.get("/openapi.json").json()
    # The real paths, checked against the served document rather than guessed from the router
    # names — `/api/sources` and `/api/contracts` are prefixes, not endpoints, and asserting
    # them would be a test that passes on a system where nothing under them exists.
    for path in (
        "/api/tools",
        "/api/sources/draft",
        "/api/contracts/{id}",
        "/api/attention",
    ):
        assert path in schema["paths"], f"{path} disappeared"


QUEUED_MUTATIONS = {
    "/api/forge/sources/sync",
    "/api/forge/adaptations",
    "/api/forge/adaptations/{adaptation_id}/retry",
    "/api/forge/adaptations/{adaptation_id}/messages",
    "/api/forge/adaptations/{adaptation_id}/changes",
    "/api/forge/adaptations/{adaptation_id}/approve",
}
"""The six that hand work to a worker. **Archive is not among them** — it is one row moving and
it finishes when the request does, so a 202 there would promise a worker that never runs."""


def test_a_queued_mutation_answers_202(client):
    """§7. A `200` says *this is done*; what has happened is that a row exists and a worker will
    get to it. A page reading `200` as done shows a finished adaptation that has not started."""
    schema = client.get("/openapi.json").json()
    for path in QUEUED_MUTATIONS:
        post = schema["paths"][path]["post"]
        assert "202" in post["responses"], f"{path} does not declare a 202"
        assert "200" not in post["responses"], f"{path} still declares a 200"


def test_archive_answers_200_because_nothing_is_queued(client):
    """The distinction is the point of the rule. Archiving is the one mutation on this surface
    that is finished when the response is written."""
    post = client.get("/openapi.json").json()["paths"][
        "/api/forge/adaptations/{adaptation_id}/archive"
    ]["post"]
    assert "200" in post["responses"]
    assert "202" not in post["responses"]


@needs_db
def test_an_unknown_adaptation_is_a_refusal_rather_than_a_500(client, no_queue):
    """One handler turns every coded `ValueError` into a 422, and a `KeyError` into a 404 —
    the convention the forge's CLI already followed. A caller reads the code, not the prose.

    **Needs a database**, because the refusal comes from the row not existing. The two tests
    above it do not: an empty or oversized question is refused before anything is read, which
    is the cheaper check being made first rather than an accident.
    """
    answer = client.post(
        "/api/forge/adaptations/deadbeef/messages", json={"message": "why this type?"}
    )
    assert answer.status_code in (404, 422)


def test_an_empty_question_is_refused_before_a_model_is_reached(client, no_queue):
    """An empty turn costs a model call and tells the next reader nothing."""
    answer = client.post("/api/forge/adaptations/deadbeef/messages", json={"message": "   "})
    assert answer.status_code == 422


def test_a_message_longer_than_the_limit_is_refused(client, no_queue):
    """This string crosses egress door 5, and an unbounded field is one somebody eventually
    pastes a file into."""
    answer = client.post(
        "/api/forge/adaptations/deadbeef/messages",
        json={"message": "x" * (routes.review_service.MAX_MESSAGE + 1)},
    )
    assert answer.status_code == 422
