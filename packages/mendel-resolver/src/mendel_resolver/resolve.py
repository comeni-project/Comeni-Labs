"""The four-tier ladder. Every value exits at exactly one tier and carries it."""

from collections.abc import Sequence

from comeni_core.contract import InputPort
from comeni_core.decision import (
    DecisionRecord,
    ParamAsked,
    ParamDecision,
    SourceAsked,
    SourceDecision,
)
from comeni_core.ir import IREdge, IRNode, PipelineIR, ResolvedValue, Tier
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.tiers import ValueSource
from comeni_core.vocabulary import UnknownTypeError, Vocabulary

from mendel_resolver.goal import Goal
from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver
from mendel_resolver.router import route
from mendel_resolver.rules import RuleTable


def resolve(
    goal: Goal,
    registry: Registry,
    rules: RuleTable,
    measurements: MeasurementRegistry,
    *,
    vocabulary: Vocabulary,
    resolver: AmbiguityResolver | None = None,
    layer_names: Sequence[str] = (),
    prior: Sequence[DecisionRecord] = (),
) -> PipelineIR:
    """`prior` is the evidence behind a `source: HUMAN` claim, and it comes from the caller
    rather than from the resolver. A56: a resolver that says `HUMAN` clears its own tier-4
    review, so the claim has to be checkable against something the resolver did not write.

    Empty is the safe default — an unbacked `HUMAN` is demoted and keeps its flag — which is
    the direction A2's rule wants: the verb that forgets to pass this over-flags rather than
    under-flags. `mendel upgrade` is the one verb that has records to pass.
    """
    # A29. `Annotated[str, "type-id"]` says somebody named this; it does not say the name
    # is of a declared type. `router._have_satisfies` only *compares*, so a `have` entry
    # that satisfies nothing was never looked up and never rejected — and a patient name
    # and a filesystem path reached the publication payload as `type_id`, with a sentence of
    # clinical notes as a `required_states` key.
    #
    # Keyword and **required**, like `measurements` and for the same reason A2 gives: an
    # optional guard is the guard the next verb forgets. `mendel upgrade` is the verb that
    # matters here, because its goal comes from a stranger's bundle rather than from a file
    # the operator wrote.
    _declared_types(goal, vocabulary)
    # A56. What a *person* actually answered, keyed by decision. Built from the caller's
    # records, so a resolver claiming `HUMAN` cannot also supply the proof of it.
    backed = {
        record.key: record.human_override
        for record in prior
        if getattr(record, "human_override", None) is not None
    }
    # Invariant 15 was enforced in `mendel build`'s own re-route through
    # `MeasurementRegistry.profile()` — an application-layer step, which is not a property
    # of anything. `mendel upgrade` takes its goal from a bundle rather than a file, so the
    # one verb that reads something a stranger wrote was the one verb with no check, and a
    # bundle carrying `sample_name: PATIENT-00417` upgraded to exit 0 with the string in
    # the new IR. A guard in a caller is a guard the next caller forgets.
    #
    # Required rather than defaulted, deliberately: an optional guard is the same guard
    # one keyword away from being forgotten again. Audit 2026-08-06, A2.
    for measured in goal.profile.measurements:
        measurements.check(measured.measurement, measured.value)

    resolver = resolver or FlagOnlyResolver()
    plan = route(goal, registry, rules, resolver)
    ir = PipelineIR(
        profile=goal.profile,
        registry_layers=list(layer_names),
        # Read off the loaded data rather than passed in: a displacement is a fact each
        # loader discovered, and asking the caller to forward it is asking them to forget.
        # A published pipeline whose overlay quietly rerouted it is unauditable.
        #
        # All four kinds, in loader order (`layers.Layers.displaced` is the same list). This
        # read measurements+contracts alone for a plan and a half, so an overlay `vocabularies/`
        # or `rules/` block reached the published artifact recording nothing (A51) — A23/A24
        # gave those kinds a `Displacement`, but `resolve()` never collected it. Each kind now
        # carries its own list, so completeness is a property of the arguments, not of the
        # caller remembering to forward a fifth thing.
        displaced=[
            *measurements.displaced,
            *vocabulary.displaced,
            *registry.displaced,
            *rules.displaced,
        ],
    )
    # Every output emitted so far, in order. Keyed on type_id alone this was a dict, so the
    # last producer of a type won and SAMTOOLS_INDEX's `.bai` was handed to featureCounts —
    # valid Nextflow, no flag, and `-stub-run` cannot catch it because nf-core stubs never
    # read their inputs. A consumer must be fed a source that satisfies its required states.
    produced: list[tuple[str, str, str, frozenset[str]]] = []

    for step in plan.steps:
        contract = registry.get(step.contract_id)
        node = IRNode(
            id=step.node_id,
            contract_id=contract.id,
            selection=ResolvedValue(
                value=contract.id,
                tier=step.selection_tier,
                source=step.selection_source,
                reason=step.selection_reason,
                from_layer=step.from_layer,
                displaced_layer=step.displaced_layer,
            ),
        )

        for param in contract.params:
            node.set_param(param.name, _resolve_param(
                node_id=node.id,
                param_name=param.name,
                tier_hint=param.tier_hint,
                default=param.default,
                goal=goal,
                rules=rules,
                resolver=resolver,
                backed=backed,
                decisions=ir.decisions,
            ))

        for port in contract.consumes:
            source = _source_for(produced, port, node.id, ir.decisions, resolver)
            if source is not None:
                from_node, from_port, type_id, states = source
                ir.edges.append(
                    IREdge(
                        from_node=from_node,
                        from_port=from_port,
                        to_node=node.id,
                        to_port=port.name,
                        # The type the *source* emits, which for a single-alternative port
                        # is the port's own type and for an `accepts` port is whichever
                        # alternative actually matched.
                        type_id=type_id,
                        states=states,
                    )
                )

        for port in contract.produces:
            produced.append((node.id, port.name, port.type_id, port.state))

        ir.nodes.append(node)

    # Already resolved and recorded, by `route()`, where the answer could still change the
    # selection. This loop used to call `resolver.resolve()` itself — after `ir.nodes` and
    # `ir.edges` were built — so the answer went into a record and nowhere else, and asking
    # a second time is a second chance to disagree with the pipeline that exists. With a
    # model behind the port it is also a second charge. Audit 2026-08-06, A8.
    ir.decisions.extend(plan.decisions)

    return ir


def _source_for(
    produced: list[tuple[str, str, str, frozenset[str]]],
    port: InputPort,
    node_id: str,
    decisions: list[DecisionRecord],
    resolver: AmbiguityResolver,
) -> tuple[str, str, str, frozenset[str]] | None:
    """Pick an upstream output that actually satisfies this port.

    Matching on `type_id` alone is what wired an index file into featureCounts. A source
    qualifies only if its emitted states are a superset of the port's required states —
    the same test `Registry.producers_of` uses, applied to what the pipeline has actually
    built rather than to what the registry could build.

    Among qualifying sources the one with the **smallest surplus** wins — fewest states
    beyond those asked for — which is the same rule `router.py` uses when ranking producers,
    and for the same reason: asking for a coordinate-sorted BAM should get a coordinate-sorted
    BAM, not whatever the pipeline most recently refined it into. Ties break on emission
    order, latest first.

    When more than one source is equally good that is a genuine choice, so it is recorded at
    tier 4 rather than taken silently — invariant 8 applied inside the graph rather than at
    its edges.

    A port may declare several alternatives; they are tried in declaration order and the
    first with any qualifying source wins, matching how the router picked which one to
    route. `prefer` then breaks ties *within* that alternative — it never promotes a later
    alternative over an earlier one, because alternative order is the author saying which
    kind of input they would rather have.
    """
    for alternative in port.alternatives():
        qualifying = [
            source
            for source in produced
            if source[2] == alternative.type_id and alternative.states <= source[3]
        ]
        if qualifying:
            required = alternative.states
            break
    else:
        return None

    def surplus(source: tuple[str, str, str, frozenset[str]]) -> int:
        return len(source[3] - required)

    best = min(surplus(source) for source in qualifying)
    equally_good = [source for source in qualifying if surplus(source) == best]
    if port.prefer and len(equally_good) > 1:
        preferred = [source for source in equally_good if port.prefer <= source[3]]
        equally_good = preferred or equally_good
    chosen = equally_good[-1]
    if len(equally_good) > 1:
        ambiguity = SourceAsked(
            node_id=node_id,
            subject=f"source:{port.name}",
            candidates=sorted(f"{n}.{p}" for n, p, _, _ in equally_good),
            type_id=chosen[2],
            required=sorted(required),
        )
        resolution = resolver.resolve(ambiguity)
        # The answer selects. This used to compute `equally_good[-1]`, call the resolver,
        # and then record `chosen=f"{chosen[0]}.{chosen[1]}"` — overwriting the resolver's
        # answer in the very statement that recorded it, so a published bundle could
        # contradict its own pipeline with no mutation at all. Audit 2026-08-06, A8.
        #
        # A non-candidate answer falls back rather than being trusted, exactly as
        # `router._choose` and `ReplayResolver._still_applies` do.
        chosen = next(
            (s for s in equally_good if f"{s[0]}.{s[1]}" == resolution.chosen),
            equally_good[-1],
        )
        decisions.append(
            SourceDecision(
                key=ambiguity.key(),
                subject=ambiguity.subject,
                candidates=ambiguity.candidates,
                # What was wired, not what was asked for.
                chosen=f"{chosen[0]}.{chosen[1]}",
                reason=resolution.reason,
                confidence=resolution.confidence,
                resolved_by=resolution.resolved_by,
            )
        )
    return chosen


def _resolve_param(
    *,
    node_id: str,
    param_name: str,
    tier_hint: int | None,
    default: object,
    goal: Goal,
    rules: RuleTable,
    resolver: AmbiguityResolver,
    decisions: list[DecisionRecord],
    backed: dict[str, object],
) -> ResolvedValue:
    # Tier 1 — the goal states it outright. No choice exists.
    override = next((o for o in goal.constraints.params if o.name == param_name), None)
    if override is not None:
        return ResolvedValue(
            value=override.value,
            tier=Tier.STRUCTURAL,
            source=ValueSource.GOAL,
            reason=f"specified in the goal as {param_name}",
        )

    # Tier 3 — a declared rule matches the measured profile.
    pin = rules.value_for(param_name, goal.profile)
    if pin is not None:
        return ResolvedValue(
            value=pin.value,
            tier=Tier.DATA_PROFILED,
            reason=f"rule {pin.decision.decides.key()}: {pin.because()}",
            # Provenance arrives *with* the value rather than beside it. It was two
            # lookups on the table a caller had to remember to make, which is how the
            # other consumer of the same table forgot both. Audit A15, A22.
            from_layer=pin.from_layer,
            displaced_layer=pin.displaced_layer,
        )

    # Tier 2 — a documented default exists for this context.
    if default is not None:
        return ResolvedValue(
            value=default,
            tier=Tier.CONVENTION,
            reason=f"contract default for {param_name}",
        )

    # Tier 4 — nothing decided it. Ask the port, record it, flag it.
    ambiguity = ParamAsked(
        node_id=node_id,
        subject=param_name,
        # Tier 2 already returned when a default existed, so there is exactly one
        # candidate and it is None. Real alternatives arrive with the rule-tables
        # spec, which gives a parameter a declared domain to draw them from.
        candidates=[None],
        tier_hint=tier_hint,
    )
    resolution = resolver.resolve(ambiguity)
    # **This site trusts the answer; the other two do not, and the asymmetry is deliberate.**
    # `router._choose` and `_source_for` fall back when a resolver names something that is
    # not a candidate, because there the candidates are a closed set drawn from the registry
    # — a non-candidate answer is either forged or stale, and neither is worth acting on.
    # A parameter has no declared domain yet: its candidate list is literally `[None]`, so
    # "not a candidate" would mean "any answer at all", and falling back would make tier 4
    # unable to answer anything. Plan 2 Task 11 gives a `Param` its legal values, and this
    # site becomes symmetric with the other two on the day it does. A33.
    # A54 said the decision must carry the evidence behind a `source: HUMAN`, and that is
    # still right. A56 is that the evidence was taken *from the claim*: `human_override` was
    # written as `resolution.chosen` whenever the resolver said `HUMAN`, so a resolver both
    # cleared its own tier-4 review and produced the proof `MD0220` checks against.
    #
    # `HUMAN` is unlike `confidence` and `reason`, which are claims a resolver is entitled to
    # make about its own work. This one asserts that *somebody else* — a person — answered,
    # and it is what moves the value out of `needs_review()`. So it is honoured only where a
    # record the caller supplied says a person really did answer this question, with this
    # value. `ReplayResolver` replaying a real override satisfies that; a model asserting it
    # does not. Invariant 6 is what would otherwise break, and Plan 2 wires a model here.
    #
    # A false claim is **demoted, not refused**. The property invariant 6 asks for is that
    # tier 4 stays flagged, and demoting restores exactly that. Raising would let a broken or
    # hostile adapter halt a laboratory's build instead — a denial of service in exchange for
    # a guarantee demotion already gives.
    override = backed.get(ambiguity.key())
    honoured = resolution.source is ValueSource.HUMAN and override == resolution.chosen
    decisions.append(
        ParamDecision(
            key=ambiguity.key(),
            subject=param_name,
            candidates=ambiguity.candidates,
            chosen=resolution.chosen,
            reason=resolution.reason,
            confidence=resolution.confidence,
            resolved_by=resolution.resolved_by,
            human_override=resolution.chosen if honoured else None,
        )
    )
    # **Tier 4 stays tier 4 when a human answers it.** Collapsing an override to tier 1
    # would read as "no choice existed", which is what a *goal pin* means and is exactly
    # what this did not happen. Resolution met a real ambiguity and could not settle it;
    # somebody settled it afterwards, and a reviewer reading a curated pipeline needs to
    # see that it contains a question rather than that it contains none.
    #
    # What clears is the review, not the tier: `needs_review()` skips a value whose source
    # is HUMAN and `overrides()` lists it instead. Invariant 6 says tier 4 is always
    # *flagged*; it does not say the flag can never be answered.
    return ResolvedValue(
        value=resolution.chosen,
        tier=Tier.AMBIGUOUS,
        # Not `resolution.source`: see the note above. An unbacked `HUMAN` becomes `RESOLVER`,
        # which is what keeps the value in `needs_review()`.
        source=ValueSource.HUMAN if honoured else ValueSource.RESOLVER,
        reason=resolution.reason,
    )


def _declared_types(goal: Goal, vocabulary: Vocabulary) -> None:
    """Every type a goal names must be one some layer declared.

    Closing A29 is a side effect of doing the obvious thing — a closed vocabulary rather
    than another blocklist. An undeclared type in a goal was already a user error worth a
    clear message; nothing had ever asked.
    """
    named = (
        [held.type_id for held in goal.have]
        + list(goal.want)
        + [required.type_id for required in goal.constraints.required_states]
    )
    for type_id in named:
        if type_id not in vocabulary.types:
            raise UnknownTypeError(
                f"{type_id!r} is not a declared type.\n"
                f"  Declared: {', '.join(sorted(vocabulary.types)) or '(none)'}\n"
                f"  A goal names types, not files: declare one in "
                f"<layer>/vocabularies/<type_id>.yml, or correct the goal."
            )
    for required in goal.constraints.required_states:
        # States too: `required_states` was where a sentence of clinical notes reached a
        # bundle as a *key*, and a state that no type declares is a goal asking for
        # something no contract can satisfy.
        vocabulary.validate(required.type_id, required.states)

