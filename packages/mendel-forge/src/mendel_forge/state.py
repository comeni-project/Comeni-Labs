"""A catalogue module's state against the registry an installation loads.

**Computed on read, never stored** (forge part 1 spec, §3): the registry changes without a sync
(a submodule bump, an edited layer), and a stored state would go stale silently.

Pure: it reads a loaded `Layers` and returns values.
"""

from dataclasses import dataclass
from enum import StrEnum

from comeni_core.declared.module import key_of
from comeni_vendor.ops import PREFIX
from mendel_resolver.layers import Layers


class State(StrEnum):
    IMPORTED = "imported"
    UPDATE = "update_available"
    NOT_IMPORTED = "not_imported"
    UNKNOWN = "unknown"
    GONE = "gone_upstream"
    IN_REVIEW = "in_review"
    """A forge pull request is open for it."""
    MERGED = "merged_not_released"
    """Merged into the registry, and not in the release this installation loads."""


BEST_ORDER: tuple[State, ...] = (
    State.UPDATE, State.IMPORTED, State.UNKNOWN, State.GONE, State.NOT_IMPORTED,
)
"""*Best match* with no search: what the registry already holds first."""


@dataclass(frozen=True)
class Held:
    """One registry module bound by its contract, keyed by where it came from upstream."""

    module_id: str
    contract_id: str
    version: str
    upstream_path: str


def held(stack: Layers, source: str = "nf-core") -> dict[str, Held]:
    """Every module of `source` the registry holds, by upstream path (`star/align`).

    Every module has a contract since #410 (`MD0025`), so a version is always there to compare.
    """
    prefix = PREFIX[source] + "/"
    contracts = sorted(stack.registry.all(), key=lambda contract: contract.id)
    bound = {key_of(contract.nf_include): contract for contract in contracts}
    found = {}
    for key, module in stack.modules.items():
        upstream = module.upstream
        contract = bound.get(key)
        if upstream is None or contract is None or not upstream.path.startswith(prefix):
            continue
        path = upstream.path.removeprefix(prefix)
        found[path] = Held(module_id=key, contract_id=contract.id,
                           version=contract.id.rsplit("@", 1)[1], upstream_path=path)
    return found


def state_of(path: str, tool_version: str | None, held: dict[str, Held]) -> State:
    here = held.get(path)
    if here is None:
        return State.NOT_IMPORTED
    if tool_version is None:
        return State.UNKNOWN
    return State.IMPORTED if tool_version == here.version else State.UPDATE


def gone(held: dict[str, Held], upstream_paths: set[str]) -> list[Held]:
    """Registry modules whose upstream path no longer exists: listed, never dropped."""
    return [here for path, here in sorted(held.items()) if path not in upstream_paths]
