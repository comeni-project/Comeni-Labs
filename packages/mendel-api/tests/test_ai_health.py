"""`/health/ai` — what an operator checks when a generation is not happening.

**Three facts, not one `ok`.** No worker is a compose problem, no model is a `.env` problem,
and a queue with eleven things in it is neither — it is the system working. A single boolean
gives a red light and no next step.

No Redis and no provider are reached: `_worker_and_depth` is replaced, and the model probe is
pointed at a socket this file opens. What is under test is the *reporting*, and reporting is
exactly what a live broker would make untestable in CI.
"""

import asyncio

import pytest
from comeni_ai import access
from mendel_api.routes import health


@pytest.fixture(autouse=True)
def no_ambient_model(monkeypatch):
    """Clear every name `from_env` reads, current and deprecated.

    A developer with `COMENI_AI_MODEL` exported would otherwise turn *the no-AI lane reports
    itself* green for the wrong reason — the same trap `test_a_model_lane_is_empty_by_default`
    names one file over.
    """
    for name in (*access.DEPRECATED, *access.DEPRECATED.values()):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def quiet_broker(monkeypatch):
    """Redis, answered without one. Returns a setter so a case can say what it saw."""
    state = {"worker": False, "depth": 0}

    async def _answer():
        return state["worker"], state["depth"]

    monkeypatch.setattr(health, "_worker_and_depth", _answer)
    return state


def _ask() -> health.AiHealth:
    return asyncio.run(health.ai_health())


def test_no_model_is_the_no_ai_lane_rather_than_a_fault(quiet_broker):
    """**`configured: False` is not an error state.** A laboratory that wants no model calls
    does not set one, and every deterministic verb still works — `MI0106` says the same where
    an adaptation meets it. A health check that called this unhealthy would be telling an
    operator to fix a decision somebody made."""
    reported = _ask()
    assert reported.configured is False
    assert reported.model == ""
    assert reported.model_available is None


def test_a_hosted_model_is_reported_and_never_probed(monkeypatch, quiet_broker):
    """**A health check must not bill somebody for asking whether the wires are connected.**
    A provider has no base URL, so there is nothing to open a socket to that is not a paid
    request — and `None` says *not probed* rather than *not reachable*."""
    monkeypatch.setenv(access.MODEL, "claude-opus-5")
    monkeypatch.setenv(access.API_KEY, "sk-not-a-real-key")

    reported = _ask()
    assert (reported.configured, reported.model) == (True, "claude-opus-5")
    assert reported.model_available is None


def test_the_credential_never_reaches_the_response(monkeypatch, quiet_broker):
    """The model id distinguishes a local model from a hosted one, which is what this field is
    for. A key is a credential and a base URL is a network fact about somebody's deployment;
    neither belongs in a response that is read over somebody's shoulder."""
    monkeypatch.setenv(access.MODEL, "claude-opus-5")
    monkeypatch.setenv(access.API_KEY, "sk-secret-value")
    monkeypatch.setenv(access.BASE_URL, "http://internal.lab:11434")

    body = _ask().model_dump_json()
    assert "sk-secret-value" not in body
    assert "internal.lab" not in body


def test_a_local_endpoint_that_answers_is_reported_available(monkeypatch, quiet_broker):
    """A real socket, opened by this test. A mocked probe would assert that the mock was
    called, which is a different claim from *this reaches something*."""

    async def _serve():
        server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        monkeypatch.setenv(access.MODEL, "ollama/qwen2.5-coder:14b")
        monkeypatch.setenv(access.BASE_URL, f"http://127.0.0.1:{port}")
        reported = await health.ai_health()
        server.close()
        await server.wait_closed()
        return reported

    assert asyncio.run(_serve()).model_available is True


def test_a_local_endpoint_that_is_not_there_is_reported_unavailable(monkeypatch, quiet_broker):
    """**The whole point of the field.** An `ai-worker` running against an Ollama nobody
    started fails every generation with a connection error the page reports as a failure — this
    is where that shows up as configuration rather than as the model being bad."""
    # Port 1 needs privileges to bind and nothing listens on it, so the connect fails fast
    # without depending on what else is running on this machine.
    monkeypatch.setenv(access.MODEL, "ollama/qwen2.5-coder:14b")
    monkeypatch.setenv(access.BASE_URL, "http://127.0.0.1:1")

    assert _ask().model_available is False


def test_a_missing_worker_is_reported_even_when_a_model_answers(monkeypatch, quiet_broker):
    """**The failure that is invisible from every other screen.** With no AI worker the queue
    never drains and an adaptation simply sits at `queued` — the work queue draws it correctly
    and says nothing about why it is not moving."""
    monkeypatch.setenv(access.MODEL, "claude-opus-5")
    quiet_broker["worker"] = False
    quiet_broker["depth"] = 3

    reported = _ask()
    assert reported.worker_available is False
    assert reported.queue_depth == 3


def test_an_unreachable_broker_is_not_reported_as_a_healthy_worker():
    """Reporting a worker on a broker nobody can talk to is the most confident possible wrong
    answer, and the queue depth is unknowable in the same breath."""
    from mendel_api.settings import settings

    original = settings.redis_url
    try:
        object.__setattr__(settings, "redis_url", "redis://127.0.0.1:1")
        assert asyncio.run(health._worker_and_depth()) == (False, 0)
    finally:
        object.__setattr__(settings, "redis_url", original)


def test_the_probe_does_not_wait_on_the_fault_it_reports():
    """**A health endpoint that hangs on a dead broker is a health endpoint that fails at the
    one moment it is read.** `create_pool` retries five times with a delay by default; this took
    several seconds to answer *no* before `conn_retries` was set to zero here."""
    import time

    from mendel_api.settings import settings

    original = settings.redis_url
    try:
        object.__setattr__(settings, "redis_url", "redis://127.0.0.1:1")
        start = time.monotonic()
        asyncio.run(health._worker_and_depth())
        assert time.monotonic() - start < health.PROBE_SECONDS * 2
    finally:
        object.__setattr__(settings, "redis_url", original)
