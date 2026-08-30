"""What could sit on the other end of a wire, in the order the resolver would consider them.

**The picker's list is the index's; the picker's ORDER is the router's.** Filtering — *what fits
this port* — is already answerable in the browser from `GET /api/pipeline/compatibility`, which
carries `emits`, `requires` and `satisfies` keyed by `contract_id#port`. What the browser cannot
know is which of six candidates the resolver would reach for first, and **that ordering is the
whole reason the picker is worth having**: it is the difference between a filtered list and an
answer.

`n-bport` on the redesign canvas: *`producers_of` already ranks by `(surplus, -priority, id)`, so
the reason is real — SAMTOOLS_SORT is first because it is the only producer of the state
FEATURECOUNTS asks for.* That sentence is meant to be **computed**. A picker that ordered
alphabetically and printed a hand-written reason beside it would be a `why:`-less value wearing a
UI costume, which is the exact failure the product exists to prevent.

**No new rule.** `_rank` is `router.py`'s key, imported rather than retyped — the tuple is the
thing that must not exist twice.

**It resolves nothing.** A registry query, on the `lru_cache`d stack, so the 2026-08-19 audit's
finding (every registry-touching screen cost ~250ms warm) does not arrive again on a popover that
opens under somebody's cursor.
"""

from pydantic import BaseModel, ConfigDict

from mendel_api.services import registry


class Candidate(BaseModel):
    """One contract that could go here, and why it is where it is in the list."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    port: str
    """The port on THIS candidate that would carry the wire."""
    process: str
    tool: str
    surplus: int
    """How many states this contract produces beyond what the asking port needs.

    **Zero is the closest match**, and it is the first term of the resolver's own ordering.
    `router.py`: matching on superset is right semantics for *"get me a BAM"*, and ranking by
    surplus is what stops it silently meaning *"get me a sorted BAM"*.
    """
    priority: int
    why: str
    """Composed from the numbers above, never written. See the module docstring."""


class Candidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[Candidate] = []
    total: int = 0
    """How many contracts the registry holds, so the picker can say *6 of N*.

    **The registry's count, not a catalogue's.** Issue #77: discovery reads vendored modules only,
    so a catalogue total would be aspirational — this is the number of contracts that actually
    exist to choose between, which is the honest denominator for a filtered list.
    """


def _tool(contract_id: str) -> str:
    """`nf-core/star/align@1.11.0` -> `star/align`. The same derivation `services/build.py`
    uses for `ModuleView.tool`; a contract carries no tool field of its own."""
    return contract_id.partition("@")[0].partition("/")[2] or contract_id


def _reason(first: bool, alone: bool, surplus: int, type_id: str, states: frozenset[str]) -> str:
    """Why this row sits where it does — from the ordering's own terms.

    Deliberately narrow. It says what the arithmetic said and stops; anything richer would be a
    sentence about a tool rather than a fact about the ordering, and #78 records that there is no
    prose to draw on.
    """
    asked = type_id + (f"[{', '.join(sorted(states))}]" if states else "")
    if alone:
        return f"the only producer of {asked}"
    if surplus == 0:
        return f"produces {asked} with nothing surplus"
    plural = "state" if surplus == 1 else "states"
    return f"produces {asked} plus {surplus} surplus {plural}"


def producing(type_id: str, states: frozenset[str]) -> Candidates:
    """Contracts that could feed an input asking for `type_id[states]`.

    The order is `producers_of` filtered through the router's own rank key, so the first row is
    the one `resolve()` would have taken.
    """
    from mendel_resolver.router import _surplus

    stack = registry.stack()
    found = stack.registry.producers_of(type_id, states)

    def rank(contract) -> tuple[int, int, str]:
        return (_surplus(contract, type_id, states), -contract.priority, contract.id)

    ordered = sorted(found, key=rank)
    alone = len(ordered) == 1

    rows: list[Candidate] = []
    for contract in ordered:
        surplus = _surplus(contract, type_id, states)
        port = next(
            (out.name for out in contract.produces if out.type_id == type_id),
            contract.produces[0].name if contract.produces else "",
        )
        rows.append(
            Candidate(
                contract_id=contract.id,
                port=port,
                process=contract.nf_process,
                tool=_tool(contract.id),
                surplus=surplus,
                priority=contract.priority,
                why=_reason(not rows, alone, surplus, type_id, states),
            )
        )
    return Candidates(candidates=rows, total=len(stack.registry.contracts))


def consuming(type_id: str, states: frozenset[str]) -> Candidates:
    """Contracts with an input that would accept `type_id[states]`.

    **The other direction, and it has no resolver ordering**, because the resolver never asks it:
    routing walks backwards from what is wanted. So this is ordered by how *specifically* each
    input asks — an input that names the states you have is a closer fit than one that would take
    anything — and then by id, which is stable.

    Saying that here rather than borrowing `producers_of`'s sentence matters: the two directions
    are not symmetrical, and a picker that claimed the resolver's authority for both would be
    claiming it for one it does not have.
    """
    stack = registry.stack()
    rows: list[Candidate] = []
    for contract in stack.registry.all():
        for inp in contract.consumes:
            for alternative in inp.alternatives():
                if alternative.type_id != type_id:
                    continue
                if not alternative.states <= states:
                    continue
                asked = len(alternative.states)
                rows.append(
                    Candidate(
                        contract_id=contract.id,
                        port=inp.name,
                        process=contract.nf_process,
                        tool=_tool(contract.id),
                        surplus=len(states) - asked,
                        priority=contract.priority,
                        why=(
                            f"takes {type_id}"
                            + (f"[{', '.join(sorted(alternative.states))}]"
                               if alternative.states else " in any state")
                        ),
                    )
                )
                break
    # **Ascending, and the first version sorted the other way.** `surplus` here is how much
    # LOOSER the input is than what you have: an input naming `[trimmed]` scores 0 against
    # trimmed reads, one that takes anything scores 1. The closest fit is the smallest number,
    # and `-row.surplus` put the vaguest candidate first — the opposite of what the docstring
    # above promises. Caught by printing the real registry's answer and reading it.
    rows.sort(key=lambda row: (row.surplus, row.contract_id))
    return Candidates(candidates=rows, total=len(stack.registry.contracts))
