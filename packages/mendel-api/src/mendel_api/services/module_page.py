"""One contract, the module it describes, and everything that points at it.

Served as an imported tool's page (`GET /registry/tools/{id}`, forge part 1): every value and
every reason on it is the registry's own, and nothing the registry does not hold is drawn.

**Read-only, and the shape says so** — there is no verb here that writes. Contracts change
through the queue or through drift resolution, both of which record *why*; a free-text edit
surface has nowhere to put a reason, and every value carrying one is the product claim.
"""

from typing import Any

from comeni_core.declared.contract import ContractExtArgs
from comeni_core.declared.module import key_of
from mendel_compiler import conformance
from mendel_compiler.modulespec import ModuleSpec
from pydantic import BaseModel

from mendel_api.services import catalogue, registry
from mendel_api.services.catalogue import ModuleDetail


class Port(BaseModel):
    name: str
    type_id: str
    states_required: list[str] = []
    states_conventional: list[str] = []
    """Kept by default but not required — `trimmed` reads for STAR."""
    conventional_because: str | None = None
    states_made: list[str] = []
    """For an output: the states what it makes is in."""


class ParamView(BaseModel):
    name: str
    default: Any = None
    asks_person: bool
    """Tier 4 with no default: the builder asks the person."""
    via: str
    key: str | None
    template: str | None
    domain: dict[str, Any] | None
    because: str | None


class RuleRow(BaseModel):
    when: dict[str, str]
    then: str | None
    because: str | None
    cite: str | None


class RuleView(BaseModel):
    """One decision of a role this tool fills. A rule belongs to a role, not a tool."""

    role: str
    effect: str
    because: str | None
    cite: str | None
    rows: list[RuleRow]


class Upstream(BaseModel):
    repo: str
    sha: str
    path: str


class TestView(BaseModel):
    __test__ = False  # pytest: a name, not a test class

    name: str
    feeds: list[str]
    """The input ports its files reach."""
    expects: list[str]
    """The patterns its outputs must match."""


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

    name: str | None = None
    description: str | None = None
    """From the tool's `tool.yml`, its own words."""
    params: list[ParamView] = []
    ext_args: str | None = None
    ext_args_because: str | None = None
    priority: int = 0
    priority_because: str | None = None
    rules: list[RuleView] = []
    tests: list[TestView] = []
    upstream: Upstream | None = None
    licence: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    registry_at: str = ""
    """What the builder loads (`git describe`, else the layer digest); a release in part 5."""
    catalogue: ModuleDetail | None = None
    """The upstream module's catalogue entry, `None` before the first sync."""
    pipeline_pins: None = None
    """**Always `None`, and present on purpose.** Nothing stores pipelines, so the design's
    fourth row cannot be answered. Reporting `0` would say *no pipeline uses this*, which is
    a different and unverified claim; omitting the field would let a reader think it was
    forgotten."""


def contracts_with_role(role: str) -> list[str]:
    stack = registry.stack()
    return sorted(c.id for c in stack.registry.all() if role in c.roles)


def read(id: str) -> ModulePage:
    """`KeyError` when no contract has that id."""
    stack = registry.stack()
    contract = next((c for c in stack.registry.all() if c.id == id), None)
    if contract is None:
        raise KeyError(id)

    path = conformance.module_path(contract, stack.modules)
    spec = ModuleSpec.parse(path) if path is not None and path.exists() else None

    roles = set(contract.roles)
    consumed = {c.type_id for c in contract.consumes}
    produced = {p.type_id for p in contract.produces}

    others = [c for c in stack.registry.all() if c.id != id]
    key = key_of(contract.nf_include)
    module = stack.modules.get(key)
    tool = _tool_of(key, stack.tools.tools)
    decisions = [
        (target, decision)
        for decision in stack.rules.decisions
        for target in _targets(decision)
        if target.of in roles
    ]
    ext = contract.ext_args
    ext = ext if isinstance(ext, ContractExtArgs) else ContractExtArgs(template=ext)
    upstream = module.upstream if module is not None else None

    return ModulePage(
        id=contract.id,
        roles=sorted(contract.roles),
        container=contract.container,
        consumes=[
            Port(name=c.name, type_id=c.type_id, states_required=sorted(c.state_required),
                 states_conventional=sorted(c.state_required_conventional),
                 conventional_because=c.state_conventional_because or None)
            for c in contract.consumes
        ],
        produces=[
            Port(name=p.name, type_id=p.type_id, states_made=sorted(p.state))
            for p in contract.produces
        ],
        source_path=str(path) if spec is not None else None,
        emits_total=len(spec.emits) if spec is not None else None,
        emits_declared=(
            len({p.name for p in contract.produces} & set(spec.emits))
            if spec is not None
            else None
        ),
        rules_aiming=sorted({target.of for target, _ in decisions}),
        inputs_from=sorted(
            c.id for c in others if any(p.type_id in consumed for p in c.produces)
        ),
        outputs_feed=sorted(
            c.id for c in others if any(p.type_id in produced for p in c.consumes)
        ),
        competes_with=sorted(c.id for c in others if roles & set(c.roles)),
        name=tool.name if tool else None,
        description=tool.description.strip() if tool else None,
        params=[
            ParamView(
                name=param.name, default=param.default,
                asks_person=param.tier_hint == 4 and param.default is None,
                via=str(param.via), key=param.key, template=param.template,
                domain=param.domain.model_dump(mode="json") if param.domain else None,
                because=param.because.strip() or None,
            )
            for param in contract.params
        ],
        ext_args=ext.template or None,
        ext_args_because=ext.because.strip() or None,
        priority=contract.priority,
        priority_because=contract.priority_because.strip() or None,
        rules=[_rule(target.of, target.effect, decision) for target, decision in decisions],
        tests=[TestView(name=test.name, feeds=sorted(test.inputs),
                        expects=[e.pattern for e in test.expect])
               for test in stack.tests.get(id, [])],
        upstream=Upstream(repo=upstream.repo, sha=upstream.sha, path=upstream.path)
        if upstream else None,
        licence=module.licence if module is not None else None,
        approved_by=contract.provenance.approved_by,
        approved_at=contract.provenance.approved_at,
        registry_at=registry.registry_label(),
        catalogue=_catalogue(upstream.path if upstream else None),
    )


def _targets(decision) -> list:
    return decision.decides if isinstance(decision.decides, list) else [decision.decides]


def _rule(role: str, effect, decision) -> RuleView:
    return RuleView(
        role=role, effect=str(effect), because=decision.because, cite=decision.cite,
        rows=[
            RuleRow(when={name: str(test) for name, test in row.when.items()},
                    then=None if row.then is None else str(row.then),
                    because=row.because.strip() if row.because else None, cite=row.cite)
            for row in decision.rows
        ],
    )


def _tool_of(key: str, tools: dict):
    """The tool a module belongs to: the longest tool id its key starts with."""
    owners = [tid for tid in tools if key == tid or key.startswith(tid + "/")]
    return tools[max(owners, key=len)] if owners else None


def _catalogue(upstream_path: str | None) -> ModuleDetail | None:
    prefix = "modules/nf-core/"
    if upstream_path is None or not upstream_path.startswith(prefix):
        return None
    try:
        return catalogue.detail_for(upstream_path.removeprefix(prefix))
    except Exception:  # the catalogue's database is optional to a page about the registry
        return None
