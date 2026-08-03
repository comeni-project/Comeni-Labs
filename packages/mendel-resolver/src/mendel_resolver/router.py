"""Backward chaining from wanted types to available ones, inserting producers.

Ties are ambiguity, never a coin flip. Depth is bounded, and a contract may not be
used to satisfy its own input.

Every selection carries a tier, which is what `RouteStep.selection_tier` is for:

- **structural** — nothing else can produce what was asked. Either one candidate exists,
  or one satisfies the requested states with no surplus while the rest overshoot. Asking
  for a coordinate-sorted BAM leaves the sorter as the only honest answer.
- **data-profiled** — a declared rule pinned this contract against the measured profile.
- **convention** — several candidates were equally good and the registry's `priority`
  broke it. That is a documented default, which is exactly what tier 2 means.
- **ambiguous** — nothing distinguished them. Invariant 8: demote, record, flag.
"""

from comeni_core.contract import ModuleContract
from comeni_core.decision import Ambiguity
from comeni_core.ir import Tier
from comeni_core.marks import ParamValue
from comeni_core.registry import Registry
from pydantic import BaseModel, Field

from mendel_resolver.goal import Goal
from mendel_resolver.rules import RuleTable


class UnroutableError(ValueError):
    """Raised when no chain of contracts can reach a wanted type."""


class UnroutablePinError(UnroutableError):
    """Raised when a rule pins a contract whose own inputs cannot be reached.

    Falling back to the next-ranked candidate would mean the rule said one thing and the
    pipeline did another, silently — the failure this product exists to remove.
    """


class RouteStep(BaseModel):
    contract_id: str
    node_id: str
    satisfies: str
    selection_tier: Tier = Tier.STRUCTURAL
    selection_reason: str = "the only contract that produces this"


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


def route(
    goal: Goal, registry: Registry, rules: RuleTable | None = None, max_depth: int = 10
) -> RoutePlan:
    plan = RoutePlan()
    emitted: set[str] = set()
    required_states = goal.constraints.required_states

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

        chosen, tier, reason, pinned_by = _choose(type_id, states, candidates, goal, rules, plan)

        for port in chosen.consumes:
            try:
                satisfy(port.type_id, port.state_required, depth + 1, visiting | {chosen.id})
            except UnroutablePinError:
                raise
            except UnroutableError as exc:
                if pinned_by is None:
                    raise
                raise UnroutablePinError(
                    f"a rule pins {chosen.id} to produce {type_id}, but its inputs are "
                    f"unreachable from this goal ({exc}). Rule condition: {pinned_by}"
                ) from exc
        if chosen.id not in emitted:
            emitted.add(chosen.id)
            plan.steps.append(
                RouteStep(
                    contract_id=chosen.id,
                    node_id=_node_id(chosen),
                    satisfies=type_id,
                    selection_tier=tier,
                    selection_reason=reason,
                )
            )

    for wanted in goal.want:
        satisfy(wanted, frozenset(required_states.get(wanted, [])), 0, frozenset())
    return plan


def _choose(
    type_id: str,
    states: frozenset[str],
    candidates: list[ModuleContract],
    goal: Goal,
    rules: RuleTable | None,
    plan: RoutePlan,
) -> tuple[ModuleContract, Tier, str, dict[str, ParamValue] | None]:
    """Which contract produces `type_id` here, at which tier, and why."""
    pinned = rules.producer_for(type_id, goal.profile) if rules else None
    if pinned is not None:
        contract_id, decision, row = pinned
        match = [c for c in candidates if c.id == contract_id]
        if match:
            because = row.cite or decision.cite or row.because or decision.because or ""
            return (
                match[0],
                Tier.DATA_PROFILED,
                f"rule {decision.decides.key()} matched {row.when}: {because}",
                row.when,
            )
        # The pinned contract is not a candidate *here*. Load-time validation already
        # proved it exists and produces this type, so the only way to arrive is that it
        # cannot produce the requested *states* — this site is asking for something the
        # rule was not about. `alignment.bam[coordinate_sorted]` has exactly one producer,
        # the sorter; the aligner rule applies one level down, on the sorter's own input,
        # where the aligners genuinely compete. Raising here instead would make every
        # state-refining step in the spine unroutable the moment a producer rule exists.

    def rank(contract: ModuleContract) -> tuple[int, int, str]:
        return (_surplus(contract, type_id, states), -contract.priority, contract.id)

    ordered = sorted(candidates, key=rank)
    best = rank(ordered[0])
    if len(ordered) == 1:
        return ordered[0], Tier.STRUCTURAL, "the only contract that produces this", None
    if best[0] < rank(ordered[1])[0]:
        return (
            ordered[0],
            Tier.STRUCTURAL,
            f"the only contract producing {type_id} with exactly the required states",
            None,
        )
    if best[:2] < rank(ordered[1])[:2]:
        return (
            ordered[0],
            Tier.CONVENTION,
            f"registry priority {ordered[0].priority}, over "
            f"{', '.join(c.id for c in ordered[1:])}",
            None,
        )

    plan.ambiguities.append(
        Ambiguity(
            node_id=_node_id(ordered[0]),
            subject=f"producer:{type_id}",
            candidates=sorted(c.id for c in ordered),
            context={"states": sorted(states)},
        )
    )
    return (
        ordered[0],
        Tier.AMBIGUOUS,
        f"nothing distinguishes {', '.join(c.id for c in ordered)}; chosen by id order",
        None,
    )
