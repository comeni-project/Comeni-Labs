"""Who may do what to an adaptation, and what follows (spec §2).

The AI may propose writing, changing or removing anything; only a person's decision makes it
count. A person's own edits count at once. Changing an approved item re-opens what depends on
it; a re-opened item keeps its value and needs approval again.
"""

from comeni_core.diagnostics import coded
from comeni_flow.interpret import Refused

from mendel_forge.forging.model import (
    DECISIONS,
    KEY,
    PIECES,
    PROPOSALS,
    Actor,
    Adaptation,
    Command,
    Item,
    Move,
    Piece,
    Revision,
    Status,
    piece_of,
)

DEPENDS: dict[Piece, frozenset[Piece]] = {
    Piece.QUESTIONS: frozenset({Piece.CONTRACT}),
    Piece.CONTRACT: frozenset({Piece.PARAMETERS, Piece.VOCABULARY, Piece.RULES, Piece.TESTS}),
    Piece.PARAMETERS: frozenset({Piece.RULES, Piece.TESTS}),
    Piece.VOCABULARY: frozenset({Piece.RULES}),
    Piece.RULES: frozenset({Piece.TESTS}),
    Piece.TESTS: frozenset(),
}
"""Declared, not inferred: which pieces an approved change upstream re-opens (transitively)."""

_SETTLED = frozenset({Status.APPROVED, Status.REMOVED})
_OPEN_TO_DECIDE = frozenset({Status.PROPOSED, Status.REOPENED})


def apply(state: Adaptation, command: Command) -> Adaptation:
    """The adaptation after `command`, or `Refused`. Never mutates `state`."""
    move, actor = command.move, command.actor
    if not KEY.match(command.item):
        raise Refused(coded("MF0506", f"{command.item!r} is not an item key: "
                            "<piece>:<kind>[:<name>], letters, digits, '.', '_' and '-' only"))
    if command.item == "tests:none":
        raise Refused(coded("MF0506", "a tool needs at least one test: nothing publishes untested"))
    if move in DECISIONS and actor is not Actor.PERSON:
        raise Refused(coded("MF0505", f"{actor} may not {move}: only a person decides"))
    if move in PROPOSALS and actor is Actor.PERSON:
        raise Refused(coded("MF0506", f"a person does not {move}; write or change it instead"))
    piece = piece_of(command.item)
    if actor is not Actor.REGISTRY and command.item not in state.items:
        # Order governs what is created; deciding on a proposal that exists is always open.
        # A re-forge seeds every piece from the registry's contract at once, as proposals.
        _in_reach(state, piece, move)
    item = state.items.get(command.item)
    if item is not None and actor is Actor.PERSON and command.expected is None:
        raise Refused(coded("MF0506", f"{command.item} exists: say which revision you decided on"))
    if item is not None and command.expected is not None and command.expected != item.current.n:
        raise Refused(coded(
            "MF0506",
            f"{command.item} is at revision {item.current.n}, not {command.expected}: "
            "it changed since you looked",
        ))
    status = _next_status(item, command)
    value = command.value
    if move is Move.REJECT and item is not None and item.was_approved:
        # "No, keep it": refusing a change to something decided restores what was decided.
        status, value = (Status.APPROVED, item.decided)
    revision = Revision(
        n=item.current.n + 1 if item else 1, move=move, actor=actor, value=value,
        because=command.because, invocation=command.invocation, by=command.by,
    )
    updated = Item(
        key=command.item, piece=piece,
        revisions=(*(item.revisions if item else ()), revision), status=status,
    )
    items = {**state.items, command.item: updated}
    state = state.model_copy(update={"items": items})
    if item is not None and item.was_approved and _changes_what_counts(item, command, status):
        state = reopen(state, piece)
    return state


def _in_reach(state: Adaptation, piece: Piece, move: Move) -> None:
    """Strict order: nothing is drafted, added or written past the first unfinished piece."""
    reach = next_piece(state)
    limit = PIECES.index(reach) if reach is not None else len(PIECES) - 1
    if PIECES.index(piece) > limit:
        raise Refused(coded("MF0506", f"{piece} comes after {reach}, which is not approved yet"))


def _next_status(item: Item | None, command: Command) -> Status:
    move = command.move
    if item is None:
        if move in {Move.DRAFT, Move.ADD}:
            return Status.PROPOSED
        if move in {Move.WRITE, Move.ANSWER}:
            return Status.APPROVED
        raise Refused(coded("MF0506", f"{command.item} does not exist yet, so it cannot {move}"))
    if item.status is Status.REMOVED and move is not Move.WRITE:
        raise Refused(coded("MF0506", f"{command.item} was removed; write it again to restore it"))
    if move in {Move.REVISE, Move.PROPOSE_REMOVAL}:
        return Status.PROPOSED
    if move in {Move.DRAFT, Move.ADD}:
        raise Refused(coded("MF0506", f"{command.item} exists already: revise it instead"))
    if move in {Move.WRITE, Move.ANSWER, Move.CHANGE}:
        return Status.APPROVED
    if move is Move.REMOVE:
        return Status.REMOVED
    if move not in {Move.APPROVE, Move.REJECT} or item.status not in _OPEN_TO_DECIDE:
        raise Refused(coded("MF0506", f"{command.item} is {item.status}: nothing to {move}"))
    if move is Move.REJECT:
        return Status.REJECTED
    if item.piece is Piece.QUESTIONS:
        raise Refused(coded("MF0506", f"{command.item} is a question: answer it"))
    proposing = next(r for r in reversed(item.revisions) if r.move in PROPOSALS or
                     r.move in {Move.WRITE, Move.CHANGE, Move.ANSWER})
    return Status.REMOVED if proposing.move is Move.PROPOSE_REMOVAL else Status.APPROVED


def _changes_what_counts(item: Item, command: Command, status: Status) -> bool:
    """A decision that replaces or removes a value that counted."""
    if command.move in {Move.CHANGE, Move.REMOVE, Move.WRITE, Move.ANSWER}:
        return True
    reapproved = item.status is Status.REOPENED
    return command.move is Move.APPROVE and status in _SETTLED and not reapproved


def reopen(state: Adaptation, piece: Piece) -> Adaptation:
    """Mark approved items of every piece downstream of `piece` re-opened; values kept."""
    downstream: set[Piece] = set()
    frontier = set(DEPENDS[piece])
    while frontier:
        nxt = frontier.pop()
        if nxt not in downstream:
            downstream.add(nxt)
            frontier |= DEPENDS[nxt]
    items = {
        key: item.model_copy(update={"status": Status.REOPENED})
        if item.piece in downstream and item.status is Status.APPROVED else item
        for key, item in state.items.items()
    }
    return state.model_copy(update={"items": items})


def reopen_piece(state: Adaptation, piece: Piece) -> Adaptation:
    """Re-open `piece` itself and everything downstream: what an assembly failure blames."""
    items = {
        key: item.model_copy(update={"status": Status.REOPENED})
        if item.piece is piece and item.status is Status.APPROVED else item
        for key, item in state.items.items()
    }
    return reopen(state.model_copy(update={"items": items}), piece)


def next_piece(state: Adaptation) -> Piece | None:
    """The first piece not finished: no items yet, or any item not approved or removed. The
    contract also needs its `contract:process`, ports alone cannot be assembled, and tests need
    one that stands."""
    for piece in PIECES:
        items = [i for i in state.items.values() if i.piece is piece]
        if not items or any(i.status not in _SETTLED for i in items):
            return piece
        process = state.items.get("contract:process")
        if piece is Piece.CONTRACT and (process is None or process.status is not Status.APPROVED):
            return piece
        if piece is Piece.TESTS and not any(i.status is Status.APPROVED for i in items):
            return piece
    return None


def ready_to_assemble(state: Adaptation) -> bool:
    return next_piece(state) is None
