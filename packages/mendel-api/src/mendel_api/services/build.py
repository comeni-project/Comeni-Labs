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
    settings: int
    """How many parameters this step has, so a node can offer *N settings* without the card."""


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

    steps = [
        StepView(
            id=node.id,
            process=by_id[node.id].process if node.id in by_id else node.id,
            contract_id=by_id[node.id].module.contract_id if node.id in by_id else "",
            tier=node.tier,
            reason=by_id[node.id].why.reason if node.id in by_id else "",
            settings=len(by_id[node.id].settings) if node.id in by_id else 0,
        )
        for node in placed.nodes
    ]

    provenance: dict[str, int] = {}
    for step in steps:
        provenance[str(step.tier)] = provenance.get(str(step.tier), 0) + 1
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
        settled_share=(settled / len(steps)) if steps else 0.0,
        needs_review=[step.id for step in steps if step.tier == 4],
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


def example() -> BuiltPipeline:
    """The spine, from the goal committed in `examples/`."""
    return of(Goal.model_validate(yaml_strict.load(settings.example_goal)))
