"""One contract, the module it describes, and everything that points at it.

**Read-only, and the shape says so** — there is no verb here that writes. Contracts change
through the queue or through drift resolution, both of which record *why*; a free-text edit
surface has nowhere to put a reason, and every value carrying one is the product claim.
"""

from mendel_compiler import conformance
from mendel_compiler.modulespec import ModuleSpec
from mendel_resolver import layers
from pydantic import BaseModel

from mendel_api.settings import settings


class Port(BaseModel):
    name: str
    type_id: str


class ModulePage(BaseModel):
    id: str
    roles: list[str]
    container: str | None
    consumes: list[Port]
    produces: list[Port]

    source_path: str | None
    """`None` when no module source could be found — which is what `unverifiable` means."""
    emits_total: int | None
    """How many channels the module emits. `None` when the source is unreadable — **not 0**,
    which would be a claim about a module nobody opened."""
    emits_declared: int | None
    """How many of them this contract declares. A contract may legitimately model a subset."""

    rules_aiming: list[str]
    inputs_from: list[str]
    outputs_feed: list[str]
    competes_with: list[str]
    pipeline_pins: None = None
    """**Always `None`, and present on purpose.** Nothing stores pipelines, so the design's
    fourth row cannot be answered. Reporting `0` would say *no pipeline uses this*, which is
    a different and unverified claim; omitting the field would let a reader think it was
    forgotten."""


def contracts_with_role(role: str) -> list[str]:
    stack = layers.load([settings.registry_root])
    return sorted(c.id for c in stack.registry.all() if role in c.roles)


def read(id: str) -> ModulePage:
    stack = layers.load([settings.registry_root])
    contract = next((c for c in stack.registry.all() if c.id == id), None)
    if contract is None:
        raise ValueError(f"{id!r} is not in this registry")

    path = conformance.module_path(contract, settings.source_root)
    spec = ModuleSpec.parse(path) if path.exists() else None

    roles = set(contract.roles)
    consumed = {c.type_id for c in contract.consumes}
    produced = {p.type_id for p in contract.produces}

    others = [c for c in stack.registry.all() if c.id != id]

    return ModulePage(
        id=contract.id,
        roles=sorted(contract.roles),
        container=contract.container,
        consumes=[Port(name=c.name, type_id=c.type_id) for c in contract.consumes],
        produces=[Port(name=p.name, type_id=p.type_id) for p in contract.produces],
        source_path=str(path) if spec is not None else None,
        emits_total=len(spec.emits) if spec is not None else None,
        emits_declared=(
            len({p.name for p in contract.produces} & set(spec.emits))
            if spec is not None
            else None
        ),
        rules_aiming=sorted(
            {
                d.decides.of
                for d in stack.rules.decisions
                if d.decides.of in roles
            }
        ),
        inputs_from=sorted(
            c.id for c in others if any(p.type_id in consumed for p in c.produces)
        ),
        outputs_feed=sorted(
            c.id for c in others if any(p.type_id in produced for p in c.consumes)
        ),
        competes_with=sorted(c.id for c in others if roles & set(c.roles)),
    )
