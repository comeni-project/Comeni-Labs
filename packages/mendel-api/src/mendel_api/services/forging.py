"""Adaptations: storing forging's state and moving it with commands (forge MVP 3, spec §6).

The rules are `mendel_forge.forging.rules`, pure; this module loads an adaptation's rows into
its pure state, applies a command, and writes back only what changed, in one transaction. The
unique `(adaptation, item, n)` is the last word on a race: two decisions against one revision
cannot both land.
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from comeni_core.declared.contract import ModuleContract
from comeni_core.diagnostics import coded
from comeni_flow.interpret import Refused
from mendel_forge.forging import rules
from mendel_forge.forging.model import (
    Actor,
    Adaptation,
    Command,
    Item,
    Move,
    Revision,
    Status,
)
from mendel_forge.forging.protocol import Phase
from mendel_forge.forging.values import items_of
from pydantic import BaseModel, JsonValue
from sqlalchemy.exc import IntegrityError

from mendel_api import db, jobs
from mendel_api.identity import default_author
from mendel_api.models import ForgeAdaptation, ForgeItem, ForgeMessage, ForgeRevision
from mendel_api.services import catalogue, registry


class RevisionView(BaseModel):
    n: int
    move: Move
    actor: Actor
    value: JsonValue = None
    because: str | None = None
    by: str | None = None
    invocation: str | None = None


class ItemView(BaseModel):
    key: str
    piece: str
    status: Status
    value: JsonValue = None
    current_n: int
    revisions: list[RevisionView]


class MessageView(BaseModel):
    seq: int
    role: str
    item: str | None
    content: str
    commands: list[dict] = []
    pending: bool = False
    at: datetime


class AdaptationView(BaseModel):
    id: str
    source: str
    path: str
    version: str | None
    base: str
    reforge: str | None
    phase: str
    depends_on: list[str]
    started_by: str
    started_at: datetime
    abandoned_at: datetime | None
    next_piece: str | None
    ready: bool
    items: list[ItemView]
    messages: list[MessageView]


class AdaptationSummary(BaseModel):
    id: str
    path: str
    version: str | None
    phase: str
    next_piece: str | None
    approved: int
    total: int
    waiting: int
    """Proposals waiting for the person."""
    drafting: bool
    started_by: str
    started_at: datetime


class AdaptationList(BaseModel):
    adaptations: list[AdaptationSummary]


class CommandBody(BaseModel):
    """A person's command. **There is no `actor` field**: the route sets it, so a body cannot
    claim to be the AI or anyone else."""

    model_config = {"extra": "forbid"}

    move: Move
    item: str
    expected: int | None = None
    value: JsonValue = None
    because: str | None = None


def start(source: str, path: str, by: str, reforge: str | None = None) -> AdaptationView:
    detail = catalogue.read_module(source, path)  # KeyError → MF0503 at the route
    adaptation_id = uuid.uuid4().hex
    with db.transaction() as session:
        session.add(ForgeAdaptation(
            id=adaptation_id, source=source, path=path, version=detail.row.tool_version,
            base=registry.registry_label(), reforge=reforge, phase=Phase.REVIEWING,
            depends_on=[], started_by=by, started_at=datetime.now(UTC),
        ))
        session.flush()
        if reforge is not None:
            state = Adaptation()
            for key, value in sorted(items_of(_contract(reforge)).items()):
                state = rules.apply(state, Command(move=Move.DRAFT, actor=Actor.REGISTRY,
                                                   item=key, value=value,
                                                   because="the registry's current contract"))
            _write(session, adaptation_id, Adaptation(), state)
    return read(adaptation_id)


def _contract(contract_id: str) -> ModuleContract:
    found = next((c for c in registry.stack().registry.all() if c.id == contract_id), None)
    if found is None:
        raise KeyError(contract_id)
    return found


def load(adaptation_id: str) -> Adaptation:
    with db.session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        if row is None:
            raise KeyError(adaptation_id)
        items = session.scalars(sa.select(ForgeItem).where(ForgeItem.adaptation == adaptation_id))
        revisions = session.scalars(
            sa.select(ForgeRevision).where(ForgeRevision.adaptation == adaptation_id)
            .order_by(ForgeRevision.item, ForgeRevision.n)
        ).all()
        by_item: dict[str, list[Revision]] = {}
        for r in revisions:
            by_item.setdefault(r.item, []).append(Revision(
                n=r.n, move=r.move, actor=r.actor, value=r.value, because=r.because,
                invocation=r.invocation, by=r.by,
            ))
        return Adaptation(
            items={i.item: Item(key=i.item, piece=i.piece, status=i.status,
                                revisions=tuple(by_item.get(i.item, ())))
                   for i in items},
            depends_on=tuple(row.depends_on or ()),
        )


def act(adaptation_id: str, command: Command) -> AdaptationView:
    """Apply one command and store what changed. `Refused` from the rules, or on a lost race."""
    before = load(adaptation_id)
    after = rules.apply(before, command)
    try:
        with db.transaction() as session:
            _write(session, adaptation_id, before, after)
    except IntegrityError as error:
        raise Refused(coded(
            "MF0506", f"{command.item} changed while you decided: reload and decide again",
        )) from error
    return read(adaptation_id)


def _write(session, adaptation_id: str, before: Adaptation, after: Adaptation) -> None:
    now = datetime.now(UTC)
    for key, item in after.items.items():
        old = before.items.get(key)
        known_n = old.current.n if old else 0
        for revision in item.revisions:
            if revision.n > known_n:
                session.add(ForgeRevision(
                    adaptation=adaptation_id, item=key, n=revision.n, piece=item.piece,
                    move=revision.move, actor=revision.actor, value=revision.value,
                    because=revision.because, invocation=revision.invocation, by=revision.by,
                    at=now,
                ))
        if old is None or old.status is not item.status or known_n != item.current.n:
            session.merge(ForgeItem(adaptation=adaptation_id, item=key, piece=item.piece,
                                    status=item.status, current_n=item.current.n))
    session.flush()


def person(move: Move, item: str, *, expected: int | None, value: JsonValue,
           because: str | None) -> Command:
    return Command(move=move, actor=Actor.PERSON, item=item, expected=expected, value=value,
                   because=because, by=default_author())


def read(adaptation_id: str) -> AdaptationView:
    state = load(adaptation_id)
    with db.session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        messages = session.scalars(
            sa.select(ForgeMessage).where(ForgeMessage.adaptation == adaptation_id)
            .order_by(ForgeMessage.seq)
        ).all()
        next_piece = rules.next_piece(state)
        return AdaptationView(
            id=row.id, source=row.source, path=row.path, version=row.version, base=row.base,
            reforge=row.reforge, phase=row.phase, depends_on=list(row.depends_on or []),
            started_by=row.started_by, started_at=row.started_at,
            abandoned_at=row.abandoned_at,
            next_piece=next_piece.value if next_piece else None,
            ready=rules.ready_to_assemble(state),
            items=[_item_view(i) for i in sorted(state.items.values(), key=lambda i: i.key)],
            messages=[MessageView(seq=m.seq, role=m.role, item=m.item, content=m.content,
                                  commands=m.commands or [], pending=m.pending, at=m.at)
                      for m in messages],
        )


def _item_view(item: Item) -> ItemView:
    return ItemView(
        key=item.key, piece=item.piece, status=item.status, value=item.value,
        current_n=item.current.n,
        revisions=[RevisionView(**r.model_dump()) for r in item.revisions],
    )


def summaries() -> AdaptationList:
    with db.session_scope() as session:
        rows = session.scalars(
            sa.select(ForgeAdaptation).where(ForgeAdaptation.abandoned_at.is_(None))
            .order_by(ForgeAdaptation.started_at.desc())
        ).all()
        ids = [r.id for r in rows]
        meta = {r.id: r for r in rows}
    found = []
    for adaptation_id in ids:
        state, row = load(adaptation_id), meta[adaptation_id]
        statuses = [i.status for i in state.items.values()]
        nxt = rules.next_piece(state)
        found.append(AdaptationSummary(
            id=row.id, path=row.path, version=row.version, phase=row.phase,
            next_piece=nxt.value if nxt else None,
            approved=sum(s is Status.APPROVED for s in statuses), total=len(statuses),
            waiting=sum(s in {Status.PROPOSED, Status.REOPENED} for s in statuses),
            drafting=row.phase in {Phase.DRAFTING, Phase.ASKING},
            started_by=row.started_by, started_at=row.started_at,
        ))
    return AdaptationList(adaptations=found)


async def say(adaptation_id: str, content: str, item: str | None, by: str) -> MessageView:
    load(adaptation_id)
    with db.transaction() as session:
        seq = (session.scalar(sa.select(sa.func.max(ForgeMessage.seq))
                              .where(ForgeMessage.adaptation == adaptation_id)) or 0) + 1
        message = ForgeMessage(adaptation=adaptation_id, seq=seq, role="person", item=item,
                               content=content, commands=[], pending=True,
                               at=datetime.now(UTC))
        session.add(message)
        session.flush()
        view = MessageView(seq=seq, role="person", item=item, content=content, pending=True,
                           at=message.at)
    await jobs.enqueue("answer_forge_message", adaptation_id, seq, queue=jobs.AI_QUEUE)
    return view


def abandon(adaptation_id: str) -> None:
    with db.transaction() as session:
        row = session.get(ForgeAdaptation, adaptation_id)
        if row is None:
            raise KeyError(adaptation_id)
        row.abandoned_at = datetime.now(UTC)
