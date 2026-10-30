"""Running a tool's tests as Wiener runs, and deciding green (forge MVP 4, spec §4).

**Green counts only for the draft it ran against.** Each attempt records the draft's digest, and
`proven` compares it with what is on disk now.

Nothing here can strand an adaptation in `testing`: a test that cannot be built or submitted fails
at once, a Wiener that stops answering fails after `SILENCE`, and how a set ends is decided
against the locked row, so a command that landed meanwhile stands.
"""

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

import sqlalchemy as sa
import yaml
from comeni_core.declared.tooltest import ToolTest
from comeni_core.diagnostics import coded
from comeni_flow.interpret import Refused
from mendel_compiler import pipeline_file
from mendel_forge.forging.protocol import Phase
from mendel_forge.model import Problem
from mendel_forge.runner import FINISHED, RunnerUnavailable
from mendel_forge.testing import build_test_pipeline, module_files, params_for
from mendel_resolver import layers

from mendel_api import db, jobs
from mendel_api.models import ForgeAdaptation, ForgeTestRun
from mendel_api.services import bundle, forging
from mendel_api.services.wiener_runner import runner
from mendel_api.settings import settings

log = logging.getLogger(__name__)

SILENCE = timedelta(hours=1)
"""How long Wiener may stop answering before a run counts as lost to us."""


def digest(folder: Path) -> str:
    """Of the draft layer: sorted (path, sha256) pairs, as Wiener addresses what it is handed."""
    pairs = sorted((str(p.relative_to(folder)), hashlib.sha256(p.read_bytes()).hexdigest())
                   for p in folder.rglob("*") if p.is_file())
    return hashlib.sha256(repr(pairs).encode()).hexdigest()


async def start(adaptation_id: str) -> forging.AdaptationView:
    """Move to `testing` and queue the submission; `Refused` unless just assembled."""
    if not settings.wiener_url:
        raise Refused(forging.NO_WIENER)
    with db.transaction() as session:
        found = forging.lock(session, adaptation_id)
        if found.phase != Phase.ASSEMBLED:
            raise Refused(coded("MF0506", "tests run once a draft is assembled, one set at a "
                                f"time; this one is {found.phase}"))
        found.phase = Phase.TESTING
    try:
        queued = await jobs.enqueue("run_forge_tests", adaptation_id,
                                    job_id=f"forge-tests:{adaptation_id}")
    except Exception:
        queued = False
    if not queued:
        forging.set_phase(adaptation_id, Phase.ASSEMBLED)
        raise Refused(coded("MF0506", "the tests could not be queued: try again"))
    return forging.read(adaptation_id)


def _tests(adaptation_id: str) -> tuple[list[ToolTest], layers.Layers]:
    adaptation = forging.row(adaptation_id)
    stack = layers.load([settings.registry_root, *forging.pending_layers(adaptation_id),
                         forging.draft_dir(adaptation_id)])
    return stack.tests[f"{adaptation.source}/{adaptation.path}@{adaptation.version}"], stack


def submit_all(adaptation_id: str) -> None:
    """Submit every test as a run. One that fails to start is recorded and the rest still go."""
    now = datetime.now(UTC)
    drafted = digest(forging.draft_dir(adaptation_id))
    with db.session_scope() as session:
        attempt = (session.scalar(sa.select(sa.func.max(ForgeTestRun.attempt)).where(
            ForgeTestRun.adaptation == adaptation_id)) or 0) + 1
    try:
        tests, stack = _tests(adaptation_id)
    except (ValueError, KeyError) as error:
        _record(adaptation_id, attempt, "(all)", drafted, None, repr(error), now)
        conclude(adaptation_id)
        return
    for test in tests:
        run_id, says = None, None
        try:
            run_id = _submit(test, stack)
        except (ValueError, KeyError, OSError, RunnerUnavailable) as error:
            log.warning("forge test %s of %s did not start: %s", test.name, adaptation_id, error)
            says = str(error)
        _record(adaptation_id, attempt, test.name, drafted, run_id, says, now)
    conclude(adaptation_id)


def _submit(test: ToolTest, stack: layers.Layers) -> str:
    pipeline = build_test_pipeline(test, stack)
    archive = bundle.archive(pipeline_file.dump(pipeline), pipeline,
                             module_files(pipeline, stack))
    return runner().submit(archive, f"forge test: {test.contract} {test.name}",
                           params_for(test, pipeline))


def _record(adaptation_id: str, attempt: int, name: str, drafted: str, run_id: str | None,
            says: str | None, now: datetime) -> None:
    with db.transaction() as session:
        session.add(ForgeTestRun(
            adaptation=adaptation_id, attempt=attempt, name=name, digest=drafted, run_id=run_id,
            state="running" if run_id else "failed", says=says, started_at=now, heard_at=now,
            finished_at=None if run_id else now,
        ))


def green(test: ToolTest, process: str, files: list[str]) -> list[Problem]:
    """Every expected output published by the tool's own process, by name."""
    prefix = f"{process.lower()}/"
    published = [f.removeprefix(prefix) for f in files if f.startswith(prefix)]
    return [
        Problem(code="MF0515", says=f"output {e.port}: nothing published matches {e.pattern}")
        for e in test.expect
        if not any(fnmatch(name, e.pattern) or fnmatch(PurePosixPath(name).name, e.pattern)
                   for name in published)
    ]


def _declared(adaptation_id: str, name: str) -> tuple[ToolTest, str]:
    """The test as assembled, and its tool's process, read from the draft."""
    adaptation = forging.row(adaptation_id)
    tool = forging.draft_dir(adaptation_id) / "tools" / adaptation.source / adaptation.path
    data = yaml.safe_load((tool / "tests" / f"{name}.yml").read_text())
    data.pop("declares")
    contract = yaml.safe_load((tool / "contract.yml").read_text())
    return ToolTest.model_validate(data), contract["nf_process"]


def _verdict(row: ForgeTestRun, phase: str) -> tuple[str, str | None]:
    """How a finished run ends: (`passed` or `failed`, what went wrong)."""
    if phase != "succeeded":
        return "failed", f"the run {phase} in Wiener"
    test, process = _declared(row.adaptation, row.name)
    problems = green(test, process, runner().results(row.run_id))
    return ("failed", "; ".join(p.says for p in problems)) if problems else ("passed", None)


def poll() -> int:
    """Read every open run; conclude each set that ended. Returns how many runs finished."""
    with db.session_scope() as session:
        open_runs = session.scalars(sa.select(ForgeTestRun).where(
            ForgeTestRun.state == "running")).all()
        session.expunge_all()
    finished = 0
    touched: set[str] = set()
    now = datetime.now(UTC)
    for row in open_runs:
        try:
            phase = runner().state(row.run_id)
            state, says = _verdict(row, phase) if phase in FINISHED else (None, None)
        except RunnerUnavailable as error:
            if now - row.heard_at <= SILENCE:
                continue
            state, says = "failed", f"no answer from Wiener for an hour: {error}"
        except (OSError, ValueError, KeyError) as error:  # the draft moved under the run
            state, says = "failed", f"the result could not be read: {error!r}"
        with db.session_scope() as session:
            stored = session.get(ForgeTestRun, row.id)
            stored.heard_at = now
            if state is not None:
                stored.state, stored.says, stored.finished_at = state, says, now
        if state is not None:
            finished += 1
            touched.add(row.adaptation)
    for adaptation_id in sorted(touched):
        conclude(adaptation_id)
    return finished


def latest(adaptation_id: str) -> list[ForgeTestRun]:
    with db.session_scope() as session:
        attempt = session.scalar(sa.select(sa.func.max(ForgeTestRun.attempt)).where(
            ForgeTestRun.adaptation == adaptation_id))
        found = session.scalars(sa.select(ForgeTestRun).where(
            ForgeTestRun.adaptation == adaptation_id, ForgeTestRun.attempt == attempt)
            .order_by(ForgeTestRun.name)).all()
        session.expunge_all()
    return list(found)


def conclude(adaptation_id: str) -> None:
    """End the latest set when none of it still runs, against the adaptation as it is now."""
    runs = latest(adaptation_id)
    if not runs or any(r.state == "running" for r in runs):
        return
    failed = [r for r in runs if r.state != "passed"]
    with db.transaction() as session:
        found: ForgeAdaptation = forging.lock(session, adaptation_id)
        if found.phase != Phase.TESTING:
            return
        found.phase = Phase.ASSEMBLED if failed else Phase.TESTED
    forging.post_message(adaptation_id, role="engine", content=(
        coded("MF0515", "\n".join(f"{r.name}: {r.says}" for r in failed)) if failed else
        "Tests passed: each run succeeded and every declared output exists. This shows the tool "
        "runs, not that its results are correct."))


def proven(adaptation_id: str) -> bool:
    """Whether the draft on disk is the one its latest tests passed on: what publishing asks."""
    runs = latest(adaptation_id)
    if not runs or forging.row(adaptation_id).phase not in {Phase.TESTED, Phase.PUBLISHING}:
        return False
    drafted = digest(forging.draft_dir(adaptation_id))
    return all(r.state == "passed" and r.digest == drafted for r in runs)
