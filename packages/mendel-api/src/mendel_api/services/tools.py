"""One tool, at whatever stage of its life it has reached.

**`Sources` and `Contracts` were the same query twice.** A tool moves undrafted -> drafted ->
landed, and *is it still true* is a question you can only ask of the last stage. Two screens with
two facet rails made that one journey look like two subjects — and both files carried the same
`Facets` docstring, written independently, which is the clearest possible sign nobody had noticed.

**The join is a union, not a lookup.** `sources.catalogue()` walks what a source can *discover*,
so building this by iterating that list would silently drop a contract whose module is not in
`vendor/` — hand-written, or removed upstream. Those are the rows a person most needs, because
they are the ones nothing can re-read. `test_a_landed_contract_appears_even_if_no_source_can_
discover_it` holds it.

**Nothing is loaded twice.** `sources.catalogue()`, `contracts.listing()` and `registry.stack()`
are each cached on the registry digest (Plan 3A phase 7), so composing three services costs one
load. Audit A138 records where that stops being true — see `attention.py`, which has the same
property and the same warning.
"""

from pydantic import BaseModel

from mendel_api.services import contracts, queue, registry, sources
from mendel_api.services.contracts import Status
from mendel_api.services.sources import State


class BoardRow(BaseModel):
    """One tool. **Named for what a person reads, not for how it is keyed.**"""

    ref: str
    """`nf-core:samtools/faidx` — a `ToolRef`, as the source spells it."""
    tool: str
    """`samtools/faidx`. The namespace is in `ref` and repeating it in every row is noise."""
    state: State
    status: Status | None = None
    """**`None` unless landed**, and never folded into a fourth state.

    An undrafted tool has not been checked against anything, so it has no status — reporting
    `matching` there would be the same class of falsehood as folding `unverifiable` into
    `matching`, which `contracts.Status` already refuses one checker over.
    """
    consumes: list[str] = []
    """Type ids. **This is the field the old contracts row omitted** while spending 180px on
    `roles` — what a tool takes and gives is what tells you whether it is the one you want."""
    produces: list[str] = []
    open_questions: int = 0
    contract_id: str | None = None
    draft: str | None = None


class Board(BaseModel):
    rows: list[BoardRow]
    counts: dict[str, int]
    """State -> how many, **over everything** rather than the filtered view. A facet counting
    only what is shown reads 12 in the one you are standing in and 0 in every other."""
    status_counts: dict[str, int]
    known: int | None = None
    """How many tools exist to be drafted, across every source — **`None` until something can
    honestly answer it**.

    Discovery reads `vendor/modules/` and sees thirteen tools, which is not the size of the known
    world but the size of what somebody already vendored
    ([#77](https://github.com/comeni-project/Comeni-Labs/issues/77)). Rendering that `13` as a
    catalogue total is a claim; rendering `—` is the truth. Expected near 1,600 once #77 closes —
    ~1,400 nf-core plus ~200 pegi3s — so the board is shaped for a number it cannot yet print.
    """
    sources: list[str]

    # **No `checked_at` here, deliberately.** *When was this last checked* is already answered by
    # `GET /health/registry`, which reads `SourceCheck.ran_at` — what the nightly worker wrote —
    # and that is a different fact from `checked.result()`, which is a check computed now. A
    # board field would have had to pick one and would have made the page and the health strip
    # able to disagree about the same sentence. The page reads both endpoints; both are O(1) and
    # cached on the registry digest.


def board(*, state: str | None = None, against: str | None = None) -> Board:
    """Every tool, at whatever stage it has reached."""
    catalogue = sources.catalogue()
    listing = contracts.listing()
    stack = registry.stack()

    # **How much work is open on this tool, so the row can say it.** The old sources row said
    # `answer it in the queue` with no number, which is an instruction rather than information —
    # a draft with one question left and a draft with eleven read identically.
    open_by_draft: dict[str, int] = {}
    for question in queue.read().questions:
        for draft_name in question.asked_by:
            open_by_draft[draft_name] = open_by_draft.get(draft_name, 0) + 1

    ports = {
        contract.id: (
            [port.type_id for port in contract.consumes],
            [port.type_id for port in contract.produces],
        )
        for contract in stack.registry.all()
    }
    status_of = {row.id: row.status for row in listing.rows}
    seen_from_source = {_key(row.ref): row for row in catalogue.rows}

    rows: list[BoardRow] = []
    for row in catalogue.rows:
        consumes, produces = ports.get(row.contract_id or "", ([], []))
        rows.append(
            BoardRow(
                ref=row.ref,
                tool=row.ref.partition(":")[2],
                state=row.state,
                status=status_of.get(row.contract_id or "") if row.contract_id else None,
                consumes=consumes,
                produces=produces,
                open_questions=open_by_draft.get(row.draft or "", 0),
                contract_id=row.contract_id,
                draft=row.draft,
            )
        )

    # The union half: a landed contract no source can discover still belongs on the board.
    for contract in stack.registry.all():
        key = contract.id.partition("@")[0]
        if key in seen_from_source:
            continue
        consumes, produces = ports[contract.id]
        rows.append(
            BoardRow(
                ref=key.replace("/", ":", 1),
                tool=key.partition("/")[2],
                state=State.LANDED,
                status=status_of.get(contract.id),
                consumes=consumes,
                produces=produces,
                contract_id=contract.id,
            )
        )

    counts = {member.value: 0 for member in State}
    status_counts = {member.value: 0 for member in Status}
    for row in rows:
        counts[row.state.value] += 1
        if row.status is not None:
            status_counts[row.status.value] += 1

    if state is not None:
        rows = [row for row in rows if row.state.value == state]
    if against is not None:
        rows = [row for row in rows if row.status is not None and row.status.value == against]

    # Worst first, then what needs starting, then alphabetically — the same consequence order
    # the queue and the contracts list already use.
    rows.sort(key=lambda row: (row.status.rank if row.status else 9, row.state.rank, row.tool))

    return Board(
        rows=rows,
        counts=counts,
        status_counts=status_counts,
        known=None,
        sources=catalogue.sources,
    )


def _key(ref: str) -> str:
    """`nf-core:samtools/faidx` -> `nf-core/samtools/faidx`, invariant 11's module key."""
    return ref.replace(":", "/", 1)
