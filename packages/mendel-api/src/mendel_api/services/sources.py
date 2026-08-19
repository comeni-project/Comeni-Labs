"""What each registered source can read, and what has been done with each tool.

**One read, three joins.** Discovery says what exists, the registry says what has landed, and
the workspace says what is open. They are one question — *what can I start?* — so they are one
request; a screen firing three and joining them in the browser would put the join in the place
least able to keep it right.

**No path crosses the boundary.** `settings` owns where the registry, the source and the
workspace live, which is why the forge's own transport is not what a browser calls: its request
models carry `source_root` and `workspace_root`, and a caller choosing those is a second answer
to a question `settings.py` answers once. Spec §3.1.
"""

from enum import StrEnum

from mendel_forge import ops
from mendel_resolver import layers
from pydantic import BaseModel

from mendel_api.settings import settings


class State(StrEnum):
    UNDRAFTED = "undrafted"
    """Neither drafted nor landed — this is what you can start."""
    DRAFTED = "drafted"
    """A draft in the workspace is about this tool. Answer it in the queue."""
    LANDED = "landed"
    """A contract with this module key is in the registry.

    **Outranks `drafted`**: a contract in the registry is what a pipeline resolves to, whatever
    else happens to be open in a workspace beside it."""

    @property
    def rank(self) -> int:
        """What needs doing first, the same argument as the queue and the contracts list.

        **Declared rather than derived from the member order**, as `Band.rank` and `Impact.rank`
        are: this is a `StrEnum`, so `sorted()` would compare the strings and answer
        drafted, landed, undrafted — alphabetical order reading as priority.
        """
        return {State.UNDRAFTED: 1, State.DRAFTED: 2, State.LANDED: 3}[self]


class ToolRow(BaseModel):
    ref: str
    """`nf-core:samtools/faidx` — a `ToolRef`, as the source spells it."""
    state: State
    contract_id: str | None = None
    """Set when landed, so the row can link to the module page."""
    draft: str | None = None
    """Set when drafted, so the row can link to the work that is open."""


class Catalogue(BaseModel):
    rows: list[ToolRow]
    counts: dict[str, int]
    """State -> how many, over everything discoverable rather than the filtered view — the same
    argument as the contracts list's facets: a count of what is shown reads 3 in the facet you
    are standing in and 0 in every other."""
    sources: list[str]


def _module_key(ref: str) -> str:
    """`nf-core:samtools/faidx` -> `nf-core/samtools/faidx`, which is a contract id minus its
    version — invariant 11's module key, and the thing displacement is decided on.

    `partition`-style single replacement, because only the source separator is a colon; a tool
    ident may not contain one, but saying so in the call is cheaper than trusting it.
    """
    return ref.replace(":", "/", 1)


def _drafts() -> dict[str, str]:
    """Module key -> draft name, read from each draft's `filled["id"]`.

    **Not from the draft's name.** A draft called `mydraft` for `samtools/faidx` is about that
    tool; the name is a label the person chose, and `MF0008` only requires it be a directory.

    `setdefault` keeps the first: two drafts of one tool at two versions is legitimate (that is
    what a version bump looks like), and the row links to one of them rather than pretending
    there is only one.
    """
    found: dict[str, str] = {}
    for name in ops.list_(ops.ListRequest(workspace_root=settings.workspace_root)).names:
        shown = ops.show(
            ops.ShowRequest(
                name=name,
                registry_root=settings.registry_root,
                source_root=settings.source_root,
                workspace_root=settings.workspace_root,
            )
        )
        declared = shown.filled.get("id")
        if declared is not None:
            found.setdefault(str(declared.value).partition("@")[0], name)
    return found


def catalogue(*, state: State | None = None) -> Catalogue:
    refs = ops.discover(ops.DiscoverRequest(source_root=settings.source_root)).refs
    landed = {
        contract.id.partition("@")[0]: contract.id
        for contract in layers.load(settings.registry_root).registry.all()
    }
    drafted = _drafts()

    rows: list[ToolRow] = []
    for ref in refs:
        key = _module_key(ref)
        if key in landed:
            rows.append(ToolRow(ref=ref, state=State.LANDED, contract_id=landed[key]))
        elif key in drafted:
            rows.append(ToolRow(ref=ref, state=State.DRAFTED, draft=drafted[key]))
        else:
            rows.append(ToolRow(ref=ref, state=State.UNDRAFTED))

    counts = {member.value: 0 for member in State}
    for row in rows:
        counts[row.state.value] += 1

    if state is not None:
        rows = [r for r in rows if r.state is state]
    rows.sort(key=lambda r: (r.state.rank, r.ref))
    return Catalogue(rows=rows, counts=counts, sources=ops.sources_().names)


def draft(*, ref: str, name: str, version: str) -> ops.DraftResult:
    """Start a draft. **The three paths come from settings and never from the caller.**"""
    return ops.draft(
        ops.DraftRequest(
            ref=ref,
            name=name,
            version=version,
            registry_root=settings.registry_root,
            source_root=settings.source_root,
            workspace_root=settings.workspace_root,
        )
    )
