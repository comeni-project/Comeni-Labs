"""Backward chaining from wanted types to available ones, inserting producers.

Ties are ambiguity, never a coin flip. Depth is bounded, and a contract may not be
used to satisfy its own input.
"""

from comeni_core.contract import ModuleContract
from comeni_core.decision import Ambiguity
from comeni_core.registry import Registry
from pydantic import BaseModel, Field

from mendel_resolver.goal import Goal


class UnroutableError(ValueError):
    """Raised when no chain of contracts can reach a wanted type."""


class RouteStep(BaseModel):
    contract_id: str
    node_id: str
    satisfies: str


class RoutePlan(BaseModel):
    steps: list[RouteStep] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)


def _node_id(contract: ModuleContract) -> str:
    return contract.nf_process.lower()


def _have_satisfies(goal: Goal, type_id: str, states: frozenset[str]) -> bool:
    return any(held.type_id == type_id and states <= held.states for held in goal.have)


def _surplus(contract: ModuleContract, type_id: str, states: frozenset[str]) -> int:
    """How many states this producer adds beyond what was asked for.

    `producers_of` matches on superset, which is the right semantics for a
    requirement: asking for `coordinate_sorted` should accept a producer that also
    indexes. But when nothing is required, every producer of the type matches, and
    the aligner and the sorter become indistinguishable. Preferring the smallest
    surplus means "get me a BAM" gets an aligner rather than an aligner plus a sort
    nobody asked for.
    """
    return min(
        len(port.state - states)
        for port in contract.produces
        if port.type_id == type_id and states <= port.state
    )


def route(goal: Goal, registry: Registry, max_depth: int = 10) -> RoutePlan:
    plan = RoutePlan()
    emitted: set[str] = set()
    required_states: dict[str, list[str]] = goal.constraints.get("required_states", {})

    def satisfy(type_id: str, states: frozenset[str], depth: int, visiting: frozenset[str]) -> None:
        if depth > max_depth:
            raise UnroutableError(f"exceeded depth {max_depth} satisfying {type_id}")
        if _have_satisfies(goal, type_id, states):
            return

        # A contract cannot satisfy its own input. SAMTOOLS_SORT consumes alignment.bam
        # and produces alignment.bam; without this it selects itself forever.
        candidates = [c for c in registry.producers_of(type_id, states) if c.id not in visiting]
        if not candidates:
            raise UnroutableError(f"nothing produces {type_id} with states {sorted(states)}")

        def rank(contract: ModuleContract) -> tuple[int, int, str]:
            return (_surplus(contract, type_id, states), -contract.priority, contract.id)

        candidates.sort(key=rank)
        if len(candidates) > 1 and rank(candidates[0])[:2] == rank(candidates[1])[:2]:
            plan.ambiguities.append(
                Ambiguity(
                    node_id=_node_id(candidates[0]),
                    subject=f"producer:{type_id}",
                    candidates=sorted(c.id for c in candidates),
                    context={"states": sorted(states)},
                )
            )

        chosen = candidates[0]
        for port in chosen.consumes:
            satisfy(port.type_id, port.state_required, depth + 1, visiting | {chosen.id})
        if chosen.id not in emitted:
            emitted.add(chosen.id)
            plan.steps.append(
                RouteStep(contract_id=chosen.id, node_id=_node_id(chosen), satisfies=type_id)
            )

    for wanted in goal.want:
        satisfy(wanted, frozenset(required_states.get(wanted, [])), 0, frozenset())
    return plan
