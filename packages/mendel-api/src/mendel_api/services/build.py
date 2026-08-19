"""A resolved pipeline, laid out, ready for a canvas.

**Composes what phases 0 and 1 built and adds nothing of its own.** `orchestrate.build` resolves
without touching disk; `layout.of` places the nodes deterministically. This service exists to put
them together and to say what the provenance bar shows.

**The canvas opens on a goal, not on a stored pipeline.** Nothing persists one, and 3C is not the
phase to add a table: `pipeline.yml` is already the save file — the artifact on disk *is* the
payload — and inventing a second home for it to make a screen easier is a decision that should
wait until something needs it. A goal goes in, a pipeline comes back, nothing is written.

**Cached on the goal, because a resolve is not free.** ~0.4s cold against this registry, and the
operator's stated floor is half a second for anything done in a browser. The key is the goal's
JSON plus the registry digest, so editing either invalidates it and there is no hand-written
expiry to get wrong — the same shape `services/registry.py` uses.
"""

from functools import lru_cache

from comeni_core import yaml_strict
from comeni_core.artifact.digest import digest_of_directory
from mendel_compiler import layout, orchestrate
from mendel_resolver.goal import Goal
from pydantic import BaseModel

from mendel_api.services import registry
from mendel_api.settings import settings

# The five-module RNA-seq spine. **The screen has to open on something** and nothing can author a
# goal until the prompt door exists, which is after #69 — so until then this is what a person
# sees first, and it is a real build rather than a fixture.
#
# Its path is `settings.example_goal` and not a constant here: a bare relative path resolves
# against the process's working directory, which is the repository root under pytest and `/app`
# in a container. That difference is a 500 that no test in this file could have caught.


class Point(BaseModel):
    x: int
    y: int


class PlacedNode(BaseModel):
    id: str
    rank: int
    order: int
    x: int
    y: int
    width: int
    height: int
    tier: int


class PlacedWire(BaseModel):
    from_node: str
    from_port: str
    to_node: str
    to_port: str
    type_id: str
    points: list[Point]
    label_at: Point


class Placement(BaseModel):
    nodes: list[PlacedNode]
    wires: list[PlacedWire]
    width: int
    height: int


class SettingView(BaseModel):
    """One resolved parameter, as the settings card needs it.

    **Read-only in 3C**, and the field is absent rather than disabled: nothing persists an edit,
    and a box that looks typeable and discards what you type is worse than a value that says it
    is a record. The design's editable field arrives with somewhere to put the answer.
    """

    name: str
    value: str | None
    """Rendered, not raw — `None` is a value that was never settled and shows as `—`."""
    via: str
    tier: int
    reason: str
    axis_reason: str
    """Why this parameter is being decided at all, as distinct from why it got this answer.
    Plan 1.14 split them because one field was answering both, which is how the registry came to
    cite the STAR paper as the reason HISAT2 was chosen."""


class PortView(BaseModel):
    """One port of a step, as the canvas draws it.

    **A port is a dot** — `dashboard.md` §3, which records that a five-shape family code was
    removed because *an encoding that needs its legend on screen at all times is a lookup rather
    than an encoding*. Two channels survive because each is binary and each means something a
    reader acts on: **hollow** when a required input is unmet, **doubled** when it accepts many.
    The type is text, on hover.
    """

    name: str
    type_id: str
    side: str
    """`in` or `out`."""
    met: bool
    """False when nothing in this pipeline feeds it — the hollow dot. Always true for an
    output, which cannot be unmet."""


class ModuleView(BaseModel):
    """A contract the left panel offers, for dragging onto the canvas.

    **Every landed contract, not only the ones in this pipeline.** The first cut of the builder
    listed the pipeline's own steps, which is a table of contents rather than a picker — you
    cannot drag a module in from a list that only contains what is already there.

    **There is no description, and the registry has nowhere to put one.** `ModuleContract` has no
    `summary` field and `priority_because` is empty on all twelve shipped contracts, so the card
    shows what a contract actually knows: its roles, what it needs, what it makes, and its
    container. The prose the design's card shows would need a registry schema change — issue #78.
    """

    contract_id: str
    tool: str
    process: str
    roles: list[str]
    needs: list[str]
    makes: list[str]
    container: str


class StepView(BaseModel):
    """One step, as a canvas needs it — **not the whole `Step`.**

    A `Step` carries its module digest, its container and its include path, none of which a node
    on a canvas draws. Sending them anyway would make the payload three times the size for a
    screen that shows a name and a tier.
    """

    id: str
    process: str
    contract_id: str
    tier: int
    reason: str
    ports: list[PortView]
    """**Every port, not only the connected ones.** A wire is drawn from the layout; a port is
    drawn on the node whether anything reaches it or not — an unmet input is exactly the thing a
    reader needs to see, and it has no wire by definition."""
    settings: list[SettingView]
    """**The parameters themselves, not a count.** A node shows `N settings` from `len()`; the
    card needs the rows, and a second request to fetch them would make opening a card a network
    round trip for data the build already had in hand."""


class BuiltPipeline(BaseModel):
    steps: list[StepView]
    layout: Placement
    provenance: dict[str, int]
    """Tier → how many steps exited at it. **Keyed by string** because JSON object keys are
    strings and a client that has to parse `"3"` back to `3` will do it once, whereas one that
    trusts an integer key silently gets a string anyway."""
    settled_share: float
    """The share of steps that exited at tier 1 or 2 — *settled without judgement*.

    **Tier 3 is not in it.** A rule matched measured data, which `CLAUDE.md` calls yellow for a
    reason: the machinery worked, check the premise. Counting it as settled would make the
    headline the one dishonest number on the screen.
    """
    needs_review: list[str]
    """Step ids that exited at tier 4. Invariant 6 — flagged always."""


def _view(built: orchestrate.Built) -> BuiltPipeline:
    placed = layout.of(built.ir)
    by_id = {step.id: step for step in built.pipeline.steps}
    # **An input is met by an edge OR by an entry channel**, and getting that wrong is worse
    # than not drawing ports at all. `star_align`'s `gtf` has no incoming edge — the annotation
    # arrives from `params.gtf` — so checking edges alone drew a hollow *unmet* dot on a
    # perfectly satisfied input, on the one encoding that exists to flag real problems. A
    # false alarm on it costs more than the signal is worth.
    fed = {(edge.to_node, edge.to_port) for edge in built.ir.edges}
    entered = {channel.type_id for channel in built.pipeline.channels}

    def ports_of(node_id: str) -> list[PortView]:
        step = by_id.get(node_id)
        if step is None:
            return []
        contract = built.layers.registry.get(step.module.contract_id)
        return [
            PortView(
                name=port.name,
                type_id=port.type_id,
                side="in",
                met=(node_id, port.name) in fed or port.type_id in entered,
            )
            for port in contract.consumes
        ] + [
            PortView(name=port.name, type_id=port.type_id, side="out", met=True)
            for port in contract.produces
        ]

    steps = [
        StepView(
            id=node.id,
            process=by_id[node.id].process if node.id in by_id else node.id,
            contract_id=by_id[node.id].module.contract_id if node.id in by_id else "",
            tier=node.tier,
            reason=by_id[node.id].why.reason if node.id in by_id else "",
            ports=ports_of(node.id),
            settings=[
                SettingView(
                    name=setting.name,
                    value=None if setting.value is None else str(setting.value),
                    via=str(setting.via),
                    tier=int(setting.why.tier),
                    reason=setting.why.reason,
                    axis_reason=setting.why.axis_reason,
                )
                for setting in (by_id[node.id].settings if node.id in by_id else [])
            ],
        )
        for node in placed.nodes
    ]

    # **Every decision, step and setting.** The bar counted steps only and reported *0 needing
    # your decision* on a pipeline whose `seq_platform` exits at tier 4 — understating on the one
    # element that carries the product's claim, which is the failure
    # `test_a_tier_three_choice_is_not_counted_as_settled` guards from the other side.
    #
    # `dashboard.html` counts parameters (`n.params.forEach(p => c[p.t]++)`) and not the module
    # choice. Both are counted here, because both carry a tier and both can be tier 4 —
    # `CLAUDE.md`: *module choices carry a tier too, and `needs_review()` lists a tier-4 one by
    # node rather than only as a record a reviewer would have to join by hand.*
    provenance: dict[str, int] = {}
    for step in steps:
        provenance[str(step.tier)] = provenance.get(str(step.tier), 0) + 1
        for setting in step.settings:
            provenance[str(setting.tier)] = provenance.get(str(setting.tier), 0) + 1
    decisions = sum(provenance.values())
    settled = sum(n for tier, n in provenance.items() if tier in {"1", "2"})

    return BuiltPipeline(
        steps=steps,
        layout=Placement(
            nodes=[PlacedNode(**vars(n)) for n in placed.nodes],
            wires=[
                PlacedWire(
                    from_node=w.from_node,
                    from_port=w.from_port,
                    to_node=w.to_node,
                    to_port=w.to_port,
                    type_id=w.type_id,
                    points=[Point(x=p.x, y=p.y) for p in w.points],
                    label_at=Point(x=w.label_at.x, y=w.label_at.y),
                )
                for w in placed.wires
            ],
            width=placed.width,
            height=placed.height,
        ),
        provenance=provenance,
        settled_share=(settled / decisions) if decisions else 0.0,
        needs_review=[
            step.id
            for step in steps
            if step.tier == 4 or any(setting.tier == 4 for setting in step.settings)
        ],
    )


@lru_cache(maxsize=8)
def _built(goal_json: str, registry_digest: str) -> BuiltPipeline:
    """Both halves of the key matter: a changed goal is a different pipeline, and a changed
    registry can resolve the same goal differently. Leaving the digest out is how a cache
    outlives the thing it was computed from."""
    return _view(
        orchestrate.build(
            Goal.model_validate_json(goal_json),
            registry_root=settings.registry_root,
            vendor_root=settings.source_root,
        )
    )


def of(goal: Goal) -> BuiltPipeline:
    return _built(goal.model_dump_json(), str(digest_of_directory(settings.registry_root)))


def modules() -> list[ModuleView]:
    """Every landed contract, for the picker.

    Reads the same cached stack every other service does, so offering the whole registry costs
    nothing a build was not already paying.
    """
    stack = registry.stack()
    return sorted(
        (
            ModuleView(
                contract_id=contract.id,
                tool=contract.id.partition("@")[0].partition("/")[2] or contract.id,
                process=contract.nf_process,
                roles=list(contract.roles),
                needs=[port.type_id for port in contract.consumes],
                makes=[port.type_id for port in contract.produces],
                container=contract.container,
            )
            for contract in stack.registry.all()
        ),
        key=lambda module: (module.roles[0] if module.roles else "", module.tool),
    )


def example() -> BuiltPipeline:
    """The spine, from the goal committed in `examples/`."""
    return of(Goal.model_validate(yaml_strict.load(settings.example_goal)))
