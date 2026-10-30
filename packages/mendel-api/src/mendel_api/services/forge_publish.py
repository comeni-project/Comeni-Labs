"""Publishing a proven draft and merging it (forge MVP 5, spec §3–4).

The API moves the phase and queues; **the worker talks to GitHub**, because the worker alone holds
the token. Opening refuses anything not proven, and runs the registry's own checks on a fresh
`main` before a byte is pushed. Merging reads the checks again and merges exactly the commit it
read. A cron notices what happens on GitHub by hand.

Like `forge_tests`, nothing here strands a phase: each failure says why and returns to where a
person can act.
"""

import logging
from datetime import UTC, datetime

import sqlalchemy as sa
from comeni_core.diagnostics import coded
from comeni_flow.interpret import Refused
from mendel_forge.forging.model import Actor, Adaptation, Status
from mendel_forge.forging.protocol import Phase
from mendel_forge.publishing import (
    Change,
    Decided,
    PublishUnavailable,
    Record,
    ToolFacts,
    check,
    describe,
    fragment,
    place,
    tool_id,
)
from sqlalchemy.exc import IntegrityError

from mendel_api import db, jobs
from mendel_api.identity import default_author
from mendel_api.models import ForgePullRequest
from mendel_api.services import catalogue, forge_tests, forging
from mendel_api.services.github_publisher import publisher
from mendel_api.services.reports import publishing_token_set

log = logging.getLogger(__name__)


def _open_row(session, adaptation_id: str | None = None) -> ForgePullRequest | None:
    query = sa.select(ForgePullRequest).where(ForgePullRequest.state == "open")
    if adaptation_id is not None:
        query = query.where(ForgePullRequest.adaptation == adaptation_id)
    return session.scalar(query)


async def start(adaptation_id: str) -> forging.AdaptationView:
    """Move to `publishing` and queue the opening. One forge pull request is open at a time."""
    if not publishing_token_set():
        raise Refused(forging.NO_TOKEN)
    with db.transaction() as session:
        found = forging.lock(session, adaptation_id)
        if found.phase != Phase.TESTED:
            raise Refused(coded("MF0506", f"a draft is published once its tests are green; "
                                f"this one is {found.phase}"))
        other = _open_row(session)
        if other is not None and other.adaptation != adaptation_id:
            raise Refused(coded("MF0506", f"pull request #{other.number} is open: the next "
                                "starts after it merges"))
        found.phase = Phase.PUBLISHING
    await _queue("publish_forge_tool", adaptation_id, Phase.TESTED)
    return forging.read(adaptation_id)


async def _queue(job: str, adaptation_id: str, back: Phase, *args: str) -> None:
    try:
        queued = await jobs.enqueue(job, adaptation_id, *args,
                                    job_id=f"{job}:{adaptation_id}")
    except Exception:
        queued = False
    if not queued:
        forging.set_phase(adaptation_id, back)
        raise Refused(coded("MF0506", "that could not be queued: try again"))


def publish(adaptation_id: str) -> None:
    """Open the pull request; any failure returns to `tested`, with the reason in the chat."""
    try:
        _publish(adaptation_id)
    except (ValueError, KeyError, OSError, PublishUnavailable) as error:
        log.warning("publishing %s failed: %s", adaptation_id, error)
        _leave(adaptation_id, Phase.PUBLISHING, Phase.TESTED)
        forging.post_message(adaptation_id, role="engine",
                             content=f"Nothing was published. {error}")


def _leave(adaptation_id: str, was: Phase, to: Phase) -> bool:
    with db.transaction() as session:
        found = forging.lock(session, adaptation_id)
        if found.phase != was:
            return False
        found.phase = to
    return True


def _publish(adaptation_id: str) -> None:
    if not forge_tests.proven(adaptation_id):
        raise ValueError(coded("MF0517", "the draft on disk is not the one its tests passed on: "
                               "run them again"))
    github = publisher()
    if github is None:
        raise ValueError(forging.NO_TOKEN)
    adaptation = forging.row(adaptation_id)
    module_id = f"{adaptation.source}/{adaptation.path}"
    with db.session_scope() as session:
        stale = _open_row(session, adaptation_id)
        stale_number = stale.number if stale else None
    if stale_number is not None:
        github.close(stale_number)
        with db.session_scope() as session:
            _open_row(session, adaptation_id).state = "closed"
    checkout = github.checkout()
    place(forging.draft_dir(adaptation_id), checkout, module_id, _facts(adaptation, module_id))
    verb = "updated" if adaptation.reforge else "added"
    fragment(checkout, module_id, adaptation.version, f"{verb}, forged in Comeni.")
    refused = check(checkout)
    if refused:
        raise ValueError(coded("MF0517", "\n".join(refused)))
    drafted = forge_tests.digest(forging.draft_dir(adaptation_id))
    opened_by = default_author()
    change = Change(
        branch=f"forge/{module_id.replace('/', '-')}-{adaptation.version}",
        title=f"{verb.capitalize()} {module_id}@{adaptation.version}",
        body=describe(_record(adaptation_id, module_id, adaptation.version, drafted, opened_by)),
        author=opened_by)
    pull = github.open_pull_request(change)
    try:
        with db.transaction() as session:
            session.add(ForgePullRequest(
                adaptation=adaptation_id, number=pull.number, url=pull.url, branch=pull.branch,
                state="open", checks="pending", head="", digest=drafted, opened_by=opened_by,
                opened_at=datetime.now(UTC),
            ))
    except IntegrityError:  # another adaptation's opened first
        github.close(pull.number)
        raise ValueError(coded("MF0506", "another pull request opened first: try after it "
                               "merges")) from None
    if not _leave(adaptation_id, Phase.PUBLISHING, Phase.IN_REVIEW):
        forging.post_message(adaptation_id, role="engine", content=(
            f"Pull request #{pull.number} opened, but the adaptation changed meanwhile: test it "
            "again, and opening again closes this one."))
        return
    forging.post_message(adaptation_id, role="engine",
                         content=f"Opened pull request #{pull.number}: {pull.url}")


def _facts(adaptation, module_id: str) -> ToolFacts:
    detail = catalogue.read_module(adaptation.source, adaptation.path)
    tools = detail.module.tools
    first = tools[0] if tools else None
    name = adaptation.path.split("/")[0]
    return ToolFacts(id=tool_id(module_id), name=first.name if first else name,
                     description=(first.description if first else None) or detail.row.name,
                     homepage=first.homepage if first else None)


def _record(adaptation_id: str, module_id: str, version: str, drafted: str,
            opened_by: str) -> Record:
    state: Adaptation = forging.load(adaptation_id)
    decided = [
        Decided(item=item.key, drafted_by=item.revisions[0].actor.value,
                decided_by=next((r.by for r in reversed(item.revisions)
                                 if r.actor is Actor.PERSON and r.by), "—"))
        for item in state.items.values() if item.status is Status.APPROVED
    ]
    tests = [(r.name, r.run_id or "") for r in forge_tests.latest(adaptation_id)]
    return Record(module_id=module_id, version=version, digest=drafted, opened_by=opened_by,
                  decided=decided, tests=tests)


async def approve(adaptation_id: str, by: str) -> forging.AdaptationView:
    """A person's click: refused unless CI read green, then the worker merges."""
    with db.transaction() as session:
        found = forging.lock(session, adaptation_id)
        pull = _open_row(session, adaptation_id)
        if found.phase != Phase.IN_REVIEW or pull is None:
            raise Refused(coded("MF0506", "no pull request of this adaptation is waiting"))
        if pull.checks != "green":
            raise Refused(coded("MF0518", pull.says or f"registry CI is {pull.checks}"))
        pull.approved_by = by
    await _queue("merge_forge_tool", adaptation_id, Phase.IN_REVIEW, by)
    return forging.read(adaptation_id)


def merge(adaptation_id: str, by: str) -> None:
    """Read the checks again and merge exactly that head. A refusal says why and stays in review."""
    with db.session_scope() as session:
        pull = _open_row(session, adaptation_id)
        number = pull.number if pull else None
    if number is None:
        return
    try:
        github = publisher()
        if github is None:
            raise PublishUnavailable(forging.NO_TOKEN)
        now = github.state(number)
        if now.state != "open" or now.checks != "green":
            raise PublishUnavailable(coded("MF0518", now.says or f"registry CI is {now.checks}"))
        github.merge(number, now.head)
    except PublishUnavailable as error:
        with db.session_scope() as session:
            _open_row(session, adaptation_id).approved_by = None
        forging.post_message(adaptation_id, role="engine", content=f"Not merged. {error}")
        return
    _ended(adaptation_id, "merged")


def _ended(adaptation_id: str, state: str) -> None:
    """A pull request stopped being open: record it, and move the adaptation if still in review."""
    now = datetime.now(UTC)
    with db.transaction() as session:
        found = forging.lock(session, adaptation_id)
        pull = _open_row(session, adaptation_id)
        if pull is None:  # the cron and a merge saw the same end
            return
        pull.state = state
        pull.merged_at = now if state == "merged" else None
        number, in_review = pull.number, found.phase == Phase.IN_REVIEW
        if in_review:
            found.phase = Phase.MERGED if state == "merged" else Phase.TESTED
    said = (f"Pull request #{number} merged. It reaches the builder with the next release."
            if state == "merged" else f"Pull request #{number} was closed without merging.")
    forging.post_message(adaptation_id, role="engine", content=said)


def poll() -> int:
    """Read every open pull request. Returns how many ended."""
    github = publisher()
    if github is None:
        return 0
    with db.session_scope() as session:
        rows = session.scalars(sa.select(ForgePullRequest).where(
            ForgePullRequest.state == "open")).all()
        session.expunge_all()
    ended = 0
    for row in rows:
        try:
            now = github.state(row.number)
        except PublishUnavailable as error:
            log.warning("could not read pull request #%s: %s", row.number, error)
            continue
        with db.session_scope() as session:
            stored = session.get(ForgePullRequest, row.id)
            stored.checks, stored.head, stored.says = now.checks, now.head, now.says
        if now.state != "open":
            _ended(row.adaptation, now.state)
            ended += 1
    return ended
