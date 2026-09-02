"""The first verb — Plan 6 phase 1, `docs/design/wiener.md` §11.

**The most dangerous code in Wiener so far**, and these tests are shaped by that rather than by
coverage: a bug here signals somebody else's process. §11 calls this *"the surface that deserves
the hardest audit"*, and the reason the vocabulary is closed is that a reviewer can then check a
list of verbs instead of a sanitiser.
"""

import os
import secrets
import subprocess
import sys
from datetime import UTC, datetime

import pytest
from wiener_api import repository
from wiener_api.models import Run, RunIntent
from wiener_api.services import launcher, verbs
from wiener_api.settings import settings


def _run(session, **overrides) -> Run:
    fields = {
        "id": secrets.token_hex(16), "lab_id": settings.lab_id,
        "artifact_id": secrets.token_hex(16), "submitted_by": "operator",
        "submitted_at": datetime.now(UTC), "phase": "running", "executor": "local",
        "ingest_secret": secrets.token_hex(16),
    }
    row = Run(**{**fields, **overrides})
    session.add(row)
    session.commit()
    return row


def _sleeper() -> subprocess.Popen:
    """A real process to signal. **Not a mock**, because the thing under test is whether a
    signal reaches a pid and whether the start-time check lets it — neither of which a mock can
    be wrong about."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])


# ── what it refuses, which is most of the value ──────────────────────────────────────────


def test_a_terminal_run_is_refused_by_name(session):
    """*This run is already succeeded* is a different thing to learn from *cannot cancel*, and
    the second sends somebody looking for a bug that is a state."""
    row = _run(session, phase="succeeded")
    with pytest.raises(verbs.Refused, match="already succeeded"):
        verbs.cancel(row.id, who="operator")


def test_a_run_with_no_recorded_process_is_refused_rather_than_guessed(session):
    """**Every run launched before Plan 6 is this run.** Nothing is back-filled, and the honest
    answer is to say there is no recorded process — never to signal a pid that was inferred."""
    row = _run(session)
    with pytest.raises(verbs.Refused, match="no recorded process"):
        verbs.cancel(row.id, who="operator")


def test_a_run_from_another_host_is_refused_and_says_where(session):
    """`wiener.md` §12.1: the worker holds the host Docker socket, so a replica that did not
    spawn this run has no process to signal — and a pid that exists *here* belongs to somebody
    else entirely. Refusing loudly is the MVP answer; the message names the host."""
    row = _run(session, pid=1, pid_started_at=1.0, pid_host="some-other-box")
    with pytest.raises(verbs.Refused, match="some-other-box"):
        verbs.cancel(row.id, who="operator")


def test_a_recycled_pid_is_never_signalled(session):
    """**The one that would hurt somebody.** Pids are reused; signalling a recycled one kills a
    stranger's process, which on a laptop is plausibly the user's editor.

    This run records a live pid — our own — with the *wrong* start time, which is exactly what a
    recycled number looks like. It must come back `already_gone` and send no signal.
    """
    row = _run(session, pid=os.getpid(), pid_started_at=1.0,
               pid_host=os.uname().nodename)

    outcome, _ = verbs.cancel(row.id, who="operator")
    assert outcome == verbs.Outcome.ALREADY_GONE
    # Still alive, which is the assertion that matters: we did not signal ourselves.
    assert os.getpid()


def test_an_unverifiable_pid_is_not_signalled(session):
    """Where `/proc` cannot be read the answer is *do not signal*. Refusing costs a person one
    manual `kill`; guessing costs somebody a process they never offered up."""
    row = _run(session, pid=os.getpid(), pid_started_at=None,
               pid_host=os.uname().nodename)
    outcome, _ = verbs.cancel(row.id, who="operator")
    assert outcome == verbs.Outcome.ALREADY_GONE


# ── what it does ─────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not os.path.isdir("/proc"), reason="the pid check reads /proc")
def test_it_signals_a_real_process_and_the_process_stops(session):
    """**A real process, really signalled.** SIGTERM rather than SIGKILL: Nextflow traps the
    first and takes its containers down with it, and the stronger signal is the one that looks
    decisive and leaves the mess."""
    child = _sleeper()
    try:
        row = _run(session, pid=child.pid,
                   pid_started_at=launcher.process_started_at(child.pid),
                   pid_host=os.uname().nodename)

        outcome, _ = verbs.cancel(row.id, who="operator", why="it was the wrong genome")
        assert outcome == verbs.Outcome.SIGNALLED
        assert child.wait(timeout=10) != 0, "the process did not stop"
    finally:
        if child.poll() is None:
            child.kill()


@pytest.mark.skipif(not os.path.isdir("/proc"), reason="the pid check reads /proc")
def test_the_phase_moves_through_the_record_and_survives_a_replay(session):
    """**§7.1: `run_event` is the source of truth and everything else is a projection.**

    Writing `run.phase = "cancelled"` would work until somebody replayed the run, at which point
    it would forget it was ever cancelled — the one thing the audit exists to remember. So the
    cancel is admitted as an event, and this asserts the *replay*, not the row.
    """
    from wiener_api.services.projection import state_of

    child = _sleeper()
    try:
        row = _run(session, pid=child.pid,
                   pid_started_at=launcher.process_started_at(child.pid),
                   pid_host=os.uname().nodename)
        verbs.cancel(row.id, who="operator")

        assert state_of(session, settings.lab_id, row.id).phase.value == "cancelled", (
            "a replay of the record did not reach cancelled — the phase was written on the row"
        )
    finally:
        if child.poll() is None:
            child.kill()


@pytest.mark.skipif(not os.path.isdir("/proc"), reason="the pid check reads /proc")
def test_the_audit_row_carries_all_five_of_section_elevens_fields(session):
    """§11's line is *who · when · why · prior phase · resulting run id*.

    **`prior_phase` is the load-bearing one**: a cancel on a run that was already failing is a
    different act from one on a healthy run, and the phase afterwards cannot tell them apart.
    """
    child = _sleeper()
    try:
        row = _run(session, pid=child.pid,
                   pid_started_at=launcher.process_started_at(child.pid),
                   pid_host=os.uname().nodename)
        verbs.cancel(row.id, who="operator", why="wrong reference genome")

        intent = session.query(RunIntent).filter_by(run_id=row.id).one()
        assert intent.who == "operator"
        assert intent.at is not None
        assert intent.why == "wrong reference genome"
        assert intent.prior_phase == "running", "the phase BEFORE the verb, not after"
        assert intent.resulting_run_id is None, "cancel makes no new run; relaunch will"
        assert intent.kind == "cancel"
        assert intent.because == "operator_request"
        assert intent.outcome == verbs.Outcome.SIGNALLED
    finally:
        if child.poll() is None:
            child.kill()


def test_the_endpoint_refuses_with_a_sentence_and_a_409(client, session):
    row = _run(session, phase="succeeded")
    got = client.post(f"/api/runs/{row.id}/cancel", json={"why": ""})
    assert got.status_code == 409
    assert "already succeeded" in got.json()["detail"]


def test_every_query_on_the_new_table_lives_in_the_repository_or_here(session):
    """A177's rule — a tenant filter you can forget is a leak — applies to `run_intent` too.

    This test does not enforce it (`tests/test_tenancy.py` scans for that); it asserts the row
    is written with the laboratory stamped on it, which is the half a scan cannot see.
    """
    row = _run(session, pid=1, pid_started_at=1.0, pid_host=os.uname().nodename)
    verbs.cancel(row.id, who="operator")
    intent = session.query(RunIntent).filter_by(run_id=row.id).one()
    assert intent.lab_id == settings.lab_id


def test_repository_is_where_the_intent_query_would_live():
    """The rule is about *where*, and the scan in `tests/test_tenancy.py` is what holds it. This
    names the rule so a reader adding `intents_of()` puts it in the right file."""
    assert hasattr(repository, "run"), "the repository is still the one place queries live"
