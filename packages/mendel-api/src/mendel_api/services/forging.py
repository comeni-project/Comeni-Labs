"""Adaptations: storing forging's state and moving it with commands (forge MVP 3, spec §6).

The rules are `mendel_forge.forging.rules`, pure; this module loads an adaptation's rows into
its pure state, applies a command, and writes back only what changed, in one transaction. The
unique `(adaptation, item, n)` is the last word on a race: two decisions against one revision
cannot both land.
"""

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from comeni_core.declared.contract import ModuleContract, Provenance
from comeni_core.diagnostics import coded
from comeni_flow.interpret import Refused
from comeni_vendor.ops import PREFIX, REPOS
from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging import rules
from mendel_forge.forging.assemble import ModuleOrigin, Proof, prove, write_layer
from mendel_forge.forging.model import (
    Actor,
    Adaptation,
    Command,
    Item,
    Move,
    Piece,
    Revision,
    Status,
)
from mendel_forge.forging.protocol import Phase
from mendel_forge.forging.validate import check_items, known, pending_used
from mendel_forge.forging.values import items_of, validate_value
from mendel_forge.model import Problem
from pydantic import BaseModel, JsonValue, ValidationError
from sqlalchemy.exc import IntegrityError

from mendel_api import db, jobs
from mendel_api.identity import default_author
from mendel_api.models import ForgeAdaptation, ForgeItem, ForgeMessage, ForgeRevision
from mendel_api.services import catalogue, registry
from mendel_api.settings import settings

log = logging.getLogger(__name__)


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


def module_folder(source: str, path: str) -> Path:
    """The module's files in the catalogue's clone, at the last good sync's commit."""
    return settings.forge_cache / "nf-core-modules" / PREFIX[source] / path


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
    """Apply one command and store what changed. `Refused` from the rules, or on a lost race.
    A value a person writes passes the same checks as the AI's (spec §2)."""
    try:
        with db.transaction() as session:
            _lock(session, adaptation_id)
            before = load(adaptation_id)
            if command.move in {Move.WRITE, Move.CHANGE, Move.ANSWER}:
                _check_person_value(adaptation_id, before, command)
            after = rules.apply(before, command)
            _write(session, adaptation_id, before, after)
    except IntegrityError as error:
        raise Refused(coded(
            "MF0506", f"{command.item} changed while you decided: reload and decide again",
        )) from error
    _after_change(adaptation_id, after)
    return read(adaptation_id)


def _lock(session, adaptation_id: str) -> ForgeAdaptation:
    """One mutation of an adaptation at a time: its row, locked for the transaction (review
    I10). A status written from a stale read could otherwise undo a re-open."""
    found = session.execute(sa.select(ForgeAdaptation).where(
        ForgeAdaptation.id == adaptation_id).with_for_update()).scalar_one_or_none()
    if found is None:
        raise KeyError(adaptation_id)
    return found


def _after_change(adaptation_id: str, state: Adaptation) -> None:
    _record_dependencies(adaptation_id, state)
    if row(adaptation_id).phase in {Phase.ASSEMBLED, Phase.ASSEMBLING}:
        # A change after assembly: the draft no longer stands for what is decided.
        set_phase(adaptation_id, Phase.REVIEWING)
        _changed(adaptation_id)


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


def _check_person_value(adaptation_id: str, state: Adaptation, command: Command) -> None:
    try:
        validate_value(command.item, command.value, answer=command.move is Move.ANSWER)
    except (ValidationError, KeyError) as error:
        raise Refused(coded("MF0507", f"{command.item}: {str(error).splitlines()[0]}")) \
            from None
    if command.item.startswith("questions:") or command.item.endswith(":none"):
        return
    adaptation = row(adaptation_id)
    merged = {k: i.value for k, i in state.items.items()
              if i.status is not Status.REMOVED and not k.startswith("questions:")}
    merged[command.item] = command.value
    spec = ModuleSpec.parse(module_folder(adaptation.source, adaptation.path) / "main.nf")
    problems = check_items(merged, known(registry.stack(), pending=pending_ids(adaptation_id)),
                           spec)
    if problems:
        raise Refused(coded(problems[0].code, problems[0].says))


def act_all(adaptation_id: str, commands: list[Command]) -> dict[str, int]:
    """Apply several commands (one model reply's proposals) all or none. Returns the revision
    each command's item reached, so a chat card can name the value it shows (review I4)."""
    try:
        with db.transaction() as session:
            _lock(session, adaptation_id)
            before = load(adaptation_id)
            after = before
            for command in commands:
                after = rules.apply(after, command)
            _write(session, adaptation_id, before, after)
    except IntegrityError as error:
        raise Refused(coded("MF0506", "the adaptation changed while the AI was drafting")) \
            from error
    _after_change(adaptation_id, after)
    return {c.item: after.items[c.item].current.n for c in commands}


def row(adaptation_id: str) -> ForgeAdaptation:
    with db.session_scope() as session:
        found = session.get(ForgeAdaptation, adaptation_id)
        if found is None:
            raise KeyError(adaptation_id)
        return found


def set_phase(adaptation_id: str, phase: Phase) -> None:
    with db.session_scope() as session:
        session.get(ForgeAdaptation, adaptation_id).phase = phase


def _assembled_vocabulary(adaptation_id: str) -> dict[str, str]:
    """Pending id → the assembled adaptation that proposes it, other than `adaptation_id`.
    Only an assembled adaptation is visible: work in progress never is (spec §5)."""
    with db.session_scope() as session:
        others = session.scalars(sa.select(ForgeAdaptation.id).where(
            ForgeAdaptation.phase == Phase.ASSEMBLED, ForgeAdaptation.abandoned_at.is_(None),
            ForgeAdaptation.id != adaptation_id)).all()
    found: dict[str, str] = {}
    for other in sorted(others):
        for key, item in load(other).items.items():
            if key.startswith(("vocabulary:type:", "vocabulary:role:")) and \
                    item.status is Status.APPROVED:
                found.setdefault(key.rsplit(":", 1)[1], other)
    return found


def pending_ids(adaptation_id: str) -> frozenset[str]:
    """Vocabulary from assembled adaptations this one may use, tagged pending (spec §5)."""
    return frozenset(_assembled_vocabulary(adaptation_id))


def _record_dependencies(adaptation_id: str, state: Adaptation) -> None:
    """Note which assembled adaptations this one's items now rely on."""
    owners = _assembled_vocabulary(adaptation_id)
    values = {k: i.value for k, i in state.items.items() if i.status is not Status.REMOVED}
    used = pending_used(values, known(registry.stack(), pending=frozenset(owners)))
    needed = sorted({owners[i] for i in used})
    with db.session_scope() as session:
        found = session.get(ForgeAdaptation, adaptation_id)
        merged = sorted(set(found.depends_on or []) | set(needed))
        if merged != list(found.depends_on or []):
            found.depends_on = merged


def _changed(adaptation_id: str) -> None:
    """An assembled adaptation re-opened or abandoned: its dependants are marked and the items
    that used its vocabulary re-open, values kept (spec §5). `MF0513`."""
    with db.session_scope() as session:
        dependants = [r.id for r in session.scalars(sa.select(ForgeAdaptation).where(
            ForgeAdaptation.abandoned_at.is_(None)))
            if adaptation_id in (r.depends_on or [])]
    vocabulary = {key.rsplit(":", 1)[1] for key in load(adaptation_id).items
                  if key.startswith(("vocabulary:type:", "vocabulary:role:"))}
    for dependant in dependants:
        state = load(dependant)
        items = {
            key: item.model_copy(update={"status": Status.REOPENED})
            if item.status is Status.APPROVED and _uses(item.value, vocabulary) else item
            for key, item in state.items.items()
        }
        with db.transaction() as session:
            _write(session, dependant, state, state.model_copy(update={"items": items}))
        post_message(dependant, role="engine", content=coded(
            "MF0513", f"it depends on adaptation {adaptation_id}, which changed; the items "
            "using its vocabulary re-opened"))
        if row(dependant).phase == Phase.ASSEMBLED:
            set_phase(dependant, Phase.REVIEWING)
            _changed(dependant)


def _uses(value: JsonValue, ids: set[str]) -> bool:
    if isinstance(value, str):
        return value in ids
    if isinstance(value, dict):
        return any(_uses(v, ids) for v in value.values())
    if isinstance(value, list):
        return any(_uses(v, ids) for v in value)
    return False


def post_message(adaptation_id: str, *, role: str, content: str, item: str | None = None,
                 commands: list[dict] | None = None, invocation: str | None = None) -> int:
    with db.transaction() as session:
        seq = (session.scalar(sa.select(sa.func.max(ForgeMessage.seq))
                              .where(ForgeMessage.adaptation == adaptation_id)) or 0) + 1
        session.add(ForgeMessage(adaptation=adaptation_id, seq=seq, role=role, item=item,
                                 content=content, commands=commands or [],
                                 invocation=invocation, at=datetime.now(UTC)))
    return seq


def answer_message(adaptation_id: str, seq: int, content: str, commands: list[dict],
                   invocation: str | None = None) -> None:
    """The AI's reply to the person's message `seq`, which stops being pending."""
    with db.session_scope() as session:
        asked = session.scalar(sa.select(ForgeMessage).where(
            ForgeMessage.adaptation == adaptation_id, ForgeMessage.seq == seq))
        if asked is not None:
            asked.pending = False
        item = asked.item if asked is not None else None
    post_message(adaptation_id, role="ai", content=content, item=item, commands=commands,
                 invocation=invocation)


def turns(adaptation_id: str, upto: int) -> list[tuple[str, str]]:
    """The conversation up to and including message `upto`, as (role, content)."""
    with db.session_scope() as session:
        found = session.scalars(sa.select(ForgeMessage).where(
            ForgeMessage.adaptation == adaptation_id, ForgeMessage.seq <= upto,
            ForgeMessage.role.in_(("person", "ai"))).order_by(ForgeMessage.seq)).all()
        return [("person" if m.role == "person" else "model",
                 f"[about {m.item}] {m.content}" if m.item else m.content) for m in found]


class AssemblyView(BaseModel):
    loaded: bool
    conforms: bool
    problems: list[Problem]
    blames: str | None
    files: list[str]
    """Paths inside the draft layer, relative to it."""


def draft_dir(adaptation_id: str) -> Path:
    return settings.forge_cache / "drafts" / adaptation_id


def assemble(adaptation_id: str) -> AssemblyView:
    """Write the draft layer and prove it (spec §4). **Whatever fails, the adaptation leaves
    `assembling`**: a failure the draft is to blame for re-opens that piece; any other (the
    registry has no licence text, the module left the catalogue) re-opens nothing and says so."""
    state = load(adaptation_id)
    if not rules.ready_to_assemble(state):
        raise Refused(coded("MF0506", "every piece must be approved before assembling"))
    out = draft_dir(adaptation_id)
    set_phase(adaptation_id, Phase.ASSEMBLING)
    files: list[Path] = []
    try:
        files = _write_draft(adaptation_id, state, out)
        proof = prove(settings.registry_root, pending_layers(adaptation_id), out)
    except ValidationError as error:  # a contract the registry's model refuses
        proof = _failed(str(error), Piece.CONTRACT)
    except Exception as error:
        log.warning("assembling %s failed: %r", adaptation_id, error)
        proof = _failed(str(error).removeprefix("MF0511: ") or repr(error), None)
    _finish(adaptation_id, proof)
    return AssemblyView(loaded=proof.loaded, conforms=proof.conforms, problems=proof.problems,
                        blames=proof.blames.value if proof.blames else None,
                        files=sorted(str(f.relative_to(out)) for f in files))


def _failed(says: str, blames: Piece | None) -> Proof:
    return Proof(loaded=False, conforms=False, blames=blames,
                 problems=[Problem(code="MF0511", says=says)])


def _write_draft(adaptation_id: str, state: Adaptation, out: Path) -> list[Path]:
    adaptation = row(adaptation_id)
    detail = catalogue.read_module(adaptation.source, adaptation.path)
    good = catalogue.last_good_sync()
    approved = {k: i.value for k, i in state.items.items() if i.status is Status.APPROVED
                and not k.startswith("questions:") and not k.endswith(":none")}
    licences = [lic for tool in detail.module.tools for lic in tool.licence]
    origin = ModuleOrigin(
        source_dir=module_folder(adaptation.source, adaptation.path),
        module_id=f"{adaptation.source}/{adaptation.path}", repo=REPOS[adaptation.source],
        sha=good.commit if good and good.commit else "", licence=licences[0] if licences else "",
        path=f"{PREFIX[adaptation.source]}/{adaptation.path}",
        data_commit=catalogue.test_data_commit() or "",
    )
    deciders = [r.by for i in state.items.values() for r in i.revisions
                if r.actor is Actor.PERSON and r.by]
    provenance = Provenance(
        source="forge",
        drafted_by="ai" if any(r.actor is Actor.AI for i in state.items.values()
                               for r in i.revisions) else "hand",
        approved_by=deciders[-1] if deciders else default_author(),
        approved_at=datetime.now(UTC).date().isoformat(),
    )
    return write_layer(approved, f"{adaptation.source}/{adaptation.path}@{adaptation.version}",
                       provenance, origin, base=settings.registry_root, out=out)


def _finish(adaptation_id: str, proof: Proof) -> None:
    """Record how assembly ended, against the adaptation as it is now: a command that landed
    meanwhile has already sent it back to review, and its decisions stand (review I10)."""
    with db.transaction() as session:
        found = _lock(session, adaptation_id)
        if found.phase != Phase.ASSEMBLING:
            said = "Assembly finished, but the adaptation changed meanwhile: assemble it again."
        elif proof.loaded and proof.conforms:
            found.phase = Phase.ASSEMBLED
            said = "Assembled: the draft loads over the registry and conforms."
        else:
            if proof.blames is not None:
                state = load(adaptation_id)
                _write(session, adaptation_id, state, rules.reopen_piece(state, proof.blames))
            found.phase = Phase.REVIEWING
            opened = f"{proof.blames.value} re-opened" if proof.blames else "nothing re-opened"
            said = f"Assembly failed; {opened}:\n- " + \
                "\n- ".join(f"{p.code}: {p.says}" for p in proof.problems)
    post_message(adaptation_id, role="engine", content=said)


def pending_layers(adaptation_id: str) -> list[Path]:
    """The draft layers of the assembled adaptations this one depends on, stacked beneath it."""
    return [draft_dir(other) for other in row(adaptation_id).depends_on or []
            if draft_dir(other).is_dir()]


async def ask_to_draft(adaptation_id: str, piece: str) -> bool:
    """Queue the AI's draft of `piece`, the next one; `MF0506` for any other."""
    state = load(adaptation_id)
    nxt = rules.next_piece(state)
    if nxt is None or nxt.value != piece:
        raise Refused(coded("MF0506", f"{piece} is not the next piece to draft"
                            + (f" ({nxt} is)" if nxt else " (all are approved)")))
    queued = await jobs.enqueue("draft_forge_piece", adaptation_id, piece, queue=jobs.AI_QUEUE,
                                job_id=f"forge-draft:{adaptation_id}:{piece}")
    if not queued:
        raise Refused(coded("MF0506", f"the AI is already drafting the {piece}"))
    set_phase(adaptation_id, Phase.ASKING if piece == "questions" else Phase.DRAFTING)
    return True


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
        found = session.get(ForgeAdaptation, adaptation_id)
        if found is None:
            raise KeyError(adaptation_id)
        found.abandoned_at = datetime.now(UTC)
    _changed(adaptation_id)
