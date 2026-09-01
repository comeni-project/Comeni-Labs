"""Acting on a run — the first verb, and the machinery the other four will reuse.

`docs/design/wiener.md` §11 defines a **closed verb vocabulary**: `cancel`, `relaunch`,
`retry task N`, `pause`, `apply`. Every one is a typed `Intent`, requires approval by a named
human, and leaves an audit line of *who · when · why · prior phase · resulting run id*. §11 also
says this is **"the surface that deserves the hardest audit in Wiener"**, and why the vocabulary
is what makes that audit finite: *a reviewer checks a list of verbs, not a sanitiser.*

**Cancel is first because §11 says it is the cheapest** — *"the only one that needs no
artifact"*. That is an argument for building the machinery under the cheapest verb, never for
skipping it: a second verb built against a first one's shortcut is how a vocabulary becomes a
pile.

═══ WHAT THIS IS NOT ══════════════════════════════════════════════════════════════════════

**Not a shell, and there is no code path from here to one.** Adding a verb means adding a member
to `IntentKind` and a branch here — visibly, in a diff. That is the whole of §11's audit
argument, and it is the reason this module takes an enum rather than a command string.
"""

import os
import secrets
import signal
from datetime import UTC, datetime

from wiener_core.events import EventKind, RunEvent
from wiener_core.policy import IntentKind, Reason
from wiener_core.state import RunPhase

from wiener_api import db, repository
from wiener_api.models import RunIntent
from wiener_api.settings import settings

TERMINAL = {RunPhase.SUCCEEDED, RunPhase.FAILED, RunPhase.CANCELLED, RunPhase.LOST}


class Refused(Exception):
    """The verb was not performed, and the message says why in a sentence a person can act on."""


class Outcome:
    """What a verb actually did — a closed set, because *accepted* and *it worked* differ.

    An audit that records only what was asked for is an audit of intentions. A cancel that found
    no process is a real answer and a different one from a cancel that stopped a running
    pipeline; a reader chasing an orphaned container needs to tell them apart.
    """

    SIGNALLED = "signalled"
    ALREADY_GONE = "already_gone"


def cancel(run_id: str, *, who: str, why: str = "") -> tuple[str, str]:
    """Terminate a run's head process, and record that somebody asked.

    Returns `(outcome, message)`. Raises `Refused` when the verb does not apply.

    **`SIGTERM`, never `SIGKILL`.** Nextflow traps `SIGTERM` and takes its containers down with
    it; `SIGKILL` leaves them running and the work directory locked. The stronger signal is the
    one that looks decisive and leaves the mess.
    """
    with db.session_scope() as session:
        run = repository.run(session, settings.lab_id, run_id)
        if run is None:
            raise Refused(f"no run {run_id}")

        prior = run.phase
        if prior in {phase.value for phase in TERMINAL}:
            # **Named, not generic.** *This run already succeeded* is a different thing to learn
            # from *cannot cancel*, and the second sends somebody looking for a bug.
            raise Refused(f"this run is already {prior}; there is nothing to cancel")

        if run.pid is None:
            raise Refused(
                "this run has no recorded process — it was launched before Wiener kept one, "
                "or it never reached the launcher"
            )

        # **The host, and refusing loudly is the right MVP answer.** `wiener.md` §12.1: the
        # worker holds the host Docker socket, so a replica that did not spawn this run has no
        # process to signal — and a pid that exists *here* belongs to somebody else entirely.
        here = os.uname().nodename
        if run.pid_host and run.pid_host != here:
            raise Refused(
                f"this run was launched on {run.pid_host} and this is {here}; "
                f"cancel it there, or stop the process by hand"
            )

        outcome = _signal(run.pid, run.pid_started_at)

        session.add(RunIntent(
            id=secrets.token_hex(16), lab_id=settings.lab_id, run_id=run_id,
            kind=IntentKind.CANCEL.value, because=Reason.OPERATOR_REQUEST.value,
            who=who, at=datetime.now(UTC), why=why[:2000],
            prior_phase=prior, resulting_run_id=None, outcome=outcome,
        ))

    # **The phase moves through the RECORD, not by assignment** — §7.1, *`run_event` is the
    # source of truth and everything else is a projection*. Writing `run.phase = "cancelled"`
    # would work until somebody replayed the run, at which point it would forget. `CANCELLED`
    # is admitted like any other event, which is also why the console shows it in order beside
    # the tasks that were running when it happened.
    #
    # Appended after the intent is committed: the audit row is the thing that must survive, and
    # a projection that fails leaves a run somebody can still see was cancelled and by whom.
    from wiener_api.services import projection

    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    with db.session_scope() as session:
        # `next_seq` is the ingest path's own, so a cancel takes its place in the same order
        # everything else does — §6.2's *the order Wiener received things in*.
        projection.append(session, settings.lab_id, run_id, RunEvent(
            run_id=run_id, seq=repository.next_seq(session, settings.lab_id, run_id),
            kind=EventKind.CANCELLED, at_ms=now_ms,
        ))

    if outcome == Outcome.ALREADY_GONE:
        return outcome, "the process was already gone; the run is recorded as cancelled"
    return outcome, "asked the run to stop; its containers come down with it"


def _signal(pid: int, started_at: float | None) -> str:
    """Signal a pid, but only when it is still the process we started.

    **A pid is not an identity.** They are reused, and signalling a recycled one kills a
    stranger's process — on a laptop plausibly the user's editor. `started_at` is what makes the
    pair unique, because a process cannot inherit both a number and a start time.

    **Where `/proc` cannot be read the answer is *do not signal*.** Refusing costs a person one
    manual `kill`; guessing wrong costs somebody a process they never offered up.
    """
    from wiener_api.services.launcher import process_started_at

    if started_at is None:
        return Outcome.ALREADY_GONE
    if process_started_at(pid) != started_at:
        return Outcome.ALREADY_GONE
    try:
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return Outcome.ALREADY_GONE
    return Outcome.SIGNALLED
