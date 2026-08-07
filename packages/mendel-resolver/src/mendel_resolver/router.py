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

from collections.abc import Callable

from comeni_core.contract import InputPort, ModuleContract
from comeni_core.decision import DecisionRecord, ProducerAsked, ProducerDecision
from comeni_core.ir import Tier
from comeni_core.marks import ParamValue
from comeni_core.registry import Registry
from pydantic import BaseModel, Field

from mendel_resolver.goal import Goal
from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver
from mendel_resolver.rules import Pin, RuleTable


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
    from_layer: str | None
    """Which layer this selection came from. **No default.**

    A22: `_choose` could resolve a contract by an overlay's *rule* and then build the step
    from `registry.layer_of`, which names the layer the contract was found in — so the
    artifact asserted the base layer had decided. The fix that lasts is not remembering to
    read the pin: it is that a `RouteStep` cannot be constructed without answering this.
    `None` is still a legal answer (a single-layer build), but it has to be given."""

    displaced_layer: str | None = None
    """Which lower layer this beat, if any. Audit A5, A15, A22."""


class RoutePlan(BaseModel):
    steps: list[RouteStep] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    """Ambiguities met while routing, already resolved and recorded.

    Records rather than bare `Ambiguity`s, because the resolver is now asked *here* — at
    the point the choice is made and can still affect it. It used to be asked afterwards,
    in `resolve()`, once `ir.nodes` and `ir.edges` were built, so its answer could only be
    written down. A record made anywhere but where the decision is taken can disagree with
    the decision. Audit 2026-08-06, A8.
    """


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


def _layer_name(registry: Registry, contract_id: str) -> str | None:
    """The name of the layer a contract came from, for a record a human reads."""
    at = registry.layer_of.get(contract_id)
    if at is None or at >= len(registry.layer_order):
        return None
    return registry.layer_order[at]


def _displaced_layer(
    registry: Registry, chosen: ModuleContract, candidates: list[ModuleContract]
) -> str | None:
    """The lowest layer that offered a candidate this winner beat, if any.

    **Displacement, not origin.** A layer supplying a module no lower layer had is a lab
    using the system as designed, and reporting it would put a notice beside every module
    an overlay contributes — burying the one that rerouted the pipeline. Invariant 11 is
    about an overlay *changing* what the base registry would have done.

    Reads `candidates` after the cycle filter, so a contract excluded from contention did
    not lose to anything and is not counted as displaced.
    """
    order = registry.layer_order
    winner_at = registry.layer_of.get(chosen.id)
    if winner_at is None or winner_at >= len(order):
        return None

    # Indexes throughout. This compared *names* — `order.index(layer_of[id])` — so two
    # layers sharing a name resolved to the lower one's position and a real reroute went
    # unreported. A25: identity is position.
    beaten = [
        at
        for candidate in candidates
        if candidate.id != chosen.id
        and (at := registry.layer_of.get(candidate.id)) is not None
        and at < winner_at
    ]
    return order[min(beaten)] if beaten else None


def route(
    goal: Goal,
    registry: Registry,
    rules: RuleTable | None = None,
    resolver: AmbiguityResolver | None = None,
    max_depth: int = 10,
) -> RoutePlan:
    plan = RoutePlan()
    resolver = resolver or FlagOnlyResolver()
    emitted: set[str] = set()

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

        chosen, tier, reason, pinned_by, pin = _choose(
            type_id, states, candidates, goal, rules, resolver, plan
        )

        for port in chosen.consumes:
            try:
                _satisfy_port(port, satisfy, depth + 1, visiting | {chosen.id})
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
                    # A rule that fired decided this, so the rule's layer is the answer —
                    # not the layer the winning contract happens to sit in. Those differ
                    # whenever an overlay reroutes to a base-layer module, which is A22's
                    # exact shape and the case the IR used to describe backwards.
                    from_layer=(
                        pin.from_layer if pin else _layer_name(registry, chosen.id)
                    ),
                    displaced_layer=(
                        pin.displaced_layer
                        if pin
                        else _displaced_layer(registry, chosen, candidates)
                    ),
                )
            )

    for wanted in goal.want:
        satisfy(wanted, goal.constraints.states_for(wanted), 0, frozenset())
    return plan


def _satisfy_port(
    port: InputPort,
    satisfy: Callable[[str, frozenset[str], int, frozenset[str]], None],
    depth: int,
    visiting: frozenset[str],
) -> None:
    """Try each alternative in declaration order and take the first that routes.

    Order is the author's statement of preference between kinds of input — "a BAM, or
    failing that a CRAM" — so it is first-match-wins, exactly like decision-table rows.
    A port with no `accepts` has one alternative and this is the old behaviour verbatim.
    """
    alternatives = port.alternatives()
    failures = []
    for alternative in alternatives:
        try:
            satisfy(alternative.type_id, alternative.states, depth, visiting)
            return
        except UnroutableError as exc:
            if len(alternatives) == 1:
                # One alternative, so its own message is the whole truth. Wrapping it
                # would stack "no alternative for port 'reads'" once per level of a
                # recursive route, which buries the fact at the bottom.
                raise
            failures.append(str(exc))
    raise UnroutableError(
        f"no alternative for port {port.name!r} can be routed: " + "; ".join(failures)
    )


def _choose(
    type_id: str,
    states: frozenset[str],
    candidates: list[ModuleContract],
    goal: Goal,
    rules: RuleTable | None,
    resolver: AmbiguityResolver,
    plan: RoutePlan,
) -> tuple[ModuleContract, Tier, str, dict[str, ParamValue] | None, Pin | None]:
    """Which contract produces `type_id` here, at which tier, why, and on whose say-so."""
    pinned = rules.producer_for(type_id, goal.profile) if rules else None
    if pinned is not None:
        match = [c for c in candidates if c.id == pinned.value]
        if match:
            return (
                match[0],
                Tier.DATA_PROFILED,
                f"rule {pinned.decision.decides.key()} matched {pinned.row.when}: "
                f"{pinned.because()}",
                pinned.row.when,
                pinned,
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
        return ordered[0], Tier.STRUCTURAL, "the only contract that produces this", None, None
    if best[0] < rank(ordered[1])[0]:
        return (
            ordered[0],
            Tier.STRUCTURAL,
            f"the only contract producing {type_id} with exactly the required states",
            None,
            None,
        )
    if best[:2] < rank(ordered[1])[:2]:
        return (
            ordered[0],
            Tier.CONVENTION,
            f"registry priority {ordered[0].priority}, over "
            f"{', '.join(c.id for c in ordered[1:])}",
            None,
            None,
        )

    ambiguity = ProducerAsked(
        node_id=_node_id(ordered[0]),
        subject=f"producer:{type_id}",
        candidates=sorted(c.id for c in ordered),
        states=sorted(states),
    )
    resolution = resolver.resolve(ambiguity)
    # The answer must *select*, not merely be recorded. Until 2026-08-06 this returned
    # `ordered[0]` and the resolver was consulted afterwards, at the bottom of `resolve()`,
    # purely to fill in a DecisionRecord — so a replayed or human-overridden module choice
    # was accepted, written into the published bundle, and discarded. Nothing was wrong in
    # output, because the only shipped resolver returns the candidate this code already
    # picked; that agreement is exactly what hid it. Audit A8.
    #
    # Falling back to `ordered[0]` when the answer is not a candidate keeps the same
    # posture `ReplayResolver._still_applies` already takes towards a record whose options
    # have moved: a forged or stale answer is not trusted, it is ignored.
    chosen = next((c for c in ordered if c.id == resolution.chosen), ordered[0])
    plan.decisions.append(
        ProducerDecision(
            key=ambiguity.key(),
            subject=ambiguity.subject,
            candidates=ambiguity.candidates,
            # What was built, not what was asked for. Recording `resolution.chosen` here
            # would let the record drift from the pipeline again the moment the fallback
            # above fires, which is the defect one level down.
            chosen=chosen.id,
            reason=resolution.reason,
            confidence=resolution.confidence,
            resolved_by=resolution.resolved_by,
        )
    )
    # What actually happened, not what happens by default. It read "chosen by id order"
    # unconditionally — true when the fallback fires, and false when a resolver answered,
    # which is the case a reviewer most needs described correctly: the record said the
    # machine shrugged when a person had decided. A33.
    how = (
        f"chosen by id order ({resolution.resolved_by} did not name a candidate)"
        if chosen.id != resolution.chosen
        else f"chosen by {resolution.resolved_by}: {resolution.reason}"
    )
    return (
        chosen,
        Tier.AMBIGUOUS,
        f"nothing distinguishes {', '.join(c.id for c in ordered)}; {how}",
        None,
        None,
    )
