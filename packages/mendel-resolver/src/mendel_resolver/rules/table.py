"""Loading, stacking and querying a rule table.

Split from the models because they answer different questions: `format.py` says what a rule
*is*, and this says how the ones on disk become the ones in force.

`Policy.REPLACE` applies **per key**, and the key space is namespaced — `derive:<fact>`,
`presence:<role>`, `implementation:<role>`, `param:<role>:<name>` — which is what lets both
layers live in one `rules/` directory without a second `DeclaredKind`. A higher layer replaces
a whole block rather than merging rows, because a reviewer should read one block and see the
entire effective decision.

A multi-target decision keys on the *whole set* it decides, so it replaces as a unit. That
leaves a gap a per-key check cannot see — a second decision naming one of those targets is a
different key — and `_no_target_is_decided_twice` closes it after assembly.
"""

from collections.abc import Sequence
from pathlib import Path

from comeni_core import yaml_strict
from comeni_core.declared.layered import (
    DeclaredKind,
    Displacement,
    Kind,
    Layer,
    Policy,
    Stacked,
    layers_of,
    stack,
)
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from comeni_core.diagnostics import coded
from comeni_core.goal.premise import PremiseRecord
from comeni_core.logic.when import matches, tier_of_row
from comeni_core.plan.tiers import Tier
from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.rules.format import (
    _GOAL_FACTS,
    Decision,
    DecisionRow,
    Derivation,
    Effect,
    FactRef,
    Fired,
    Pin,
    RuleValidationError,
)
from mendel_resolver.rules.validate import (
    _check_exhaustive,
    _check_when,
    _domain_of,
    _fact_fits,
    _fillers_by_role,
    _validate,
)


def _key_of(entry: "Derivation | Decision") -> str:
    """One key space for both layers, namespaced. Spec §2.1.

    `stack()` has one key space per kind and `Policy.REPLACE` applies **per key**, so an
    overlay replacing a derivation leaves the decision beside it untouched — which is what
    lets both live in `rules/` without a second `DeclaredKind`.
    """
    if isinstance(entry, Derivation):
        return f"derive:{entry.fact}"
    return entry.key()


class RuleTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[Decision] = Field(default_factory=list)
    derivations: list[Derivation] = Field(default_factory=list)
    """The premise layer's half of `rules/`, in key order. Read by `build_premises`."""

    layer_of: dict[str, str] = Field(default_factory=dict)
    """Decision key to the layer whose block is in force, assigned by the loader."""

    displaced_layer: dict[str, str] = Field(default_factory=dict)
    """Decision key to the lowest layer replaced by its effective block, if any.

    This lookup feeds per-node provenance; :attr:`displaced` retains full audit records.
    """

    displaced: list[Displacement] = Field(default_factory=list)
    """Full rule displacement records included in ``PipelineIR.displaced``."""

    @staticmethod
    def kind(
        registry: Registry,
        vocabulary: Vocabulary,
        measurements: MeasurementRegistry,
    ) -> Kind[str, Decision]:
        """How rule blocks are found, keyed and stacked.

        Keyed on the decision's *target*, not the file: a laboratory naming its overlay
        `aligner.yml` where the base says `rnaseq.yml` is still replacing that block, and
        keying on filenames would have let both fire with row order deciding.

        A higher layer replaces the whole block, not row by row — a reviewer should read
        one block and see the entire effective decision.
        """

        fillers_by_role = _fillers_by_role(registry)

        def parse(path: Path) -> list[Derivation | Decision]:
            data = yaml_strict.load(path) or {}
            found: list[Derivation | Decision] = [
                Derivation.model_validate(raw) for raw in data.get("derives", [])
            ]
            # Check duplicates within one file; later layers may replace a block by key.
            seen: dict[str, str] = {}
            for raw in data.get("decisions", []):
                decision = Decision.model_validate(raw)
                _validate(
                    decision,
                    path,
                    registry=registry,
                    fillers_by_role=fillers_by_role,
                    measurements=measurements,
                    seen=seen,
                )
                found.append(decision)
            return found

        return Kind(
            DeclaredKind.RULES,
            parse=parse,
            key=_key_of,
            policy=Policy.REPLACE,
        )

    @classmethod
    def of(
        cls, stacked: "Stacked[str, Derivation | Decision]", layers: Sequence[Layer]
    ) -> "RuleTable":
        name_of = {layer.index: layer.name for layer in layers}
        entries = [stacked.entries[key] for key in sorted(stacked.entries)]
        return cls(
            decisions=[e for e in entries if isinstance(e, Decision)],
            derivations=[e for e in entries if isinstance(e, Derivation)],
            layer_of={key: name_of[at] for key, at in stacked.origin.items()},
            displaced_layer={
                record.key: record.displaced_layer for record in stacked.displaced
            },
            displaced=list(stacked.displaced),
        )

    @classmethod
    def load(
        cls,
        layers: Path | Sequence[Path],
        *,
        registry: Registry,
        vocabulary: Vocabulary,
        measurements: MeasurementRegistry,
    ) -> "RuleTable":
        """Load rule blocks across a layer stack. **Layer roots, not `rules/`.**

        The `names` argument is gone with the rest: a `Layer` carries its own name, so
        there is no longer a fact the caller has to forward on the loader's behalf.
        """
        as_layers = layers_of(layers)
        table = cls.of(
            stack(as_layers, cls.kind(registry, vocabulary, measurements)), as_layers
        )
        # After the stack, not inside `parse` — a decision may read a fact a derivation in
        # another file supplies, and a per-file check would refuse a legitimate rule for the
        # accident of which one `stack()` reached first. Same reason `roles.check` runs after
        # the registry is assembled rather than inside `Registry.kind`'s parse.
        table.check_premise_names(measurements)
        table.check_fact_kinds(registry, measurements)
        return table

    def check_fact_kinds(self, registry: Registry, measurements: MeasurementRegistry) -> None:
        """A derived fact a setting takes (`then: {fact:}`) fits that setting's domain (#461).
        After the stack, where every derivation is known; a measured one is checked per file."""
        kinds = {d.fact: d.kind for d in self.derivations}
        fillers = _fillers_by_role(registry)
        for decision in self.decisions:
            for target in decision.targets():
                if target.effect is not Effect.PARAM:
                    continue
                for row in decision.rows:
                    if isinstance(row.then, FactRef) and row.then.fact in kinds:
                        _fact_fits(row.then, _domain_of(target, registry, fillers), target,
                                   Path("rules"), measurements,
                                   kind=kinds[row.then.fact])

    def check_premise_names(self, measurements: MeasurementRegistry) -> None:
        """Every `when` key across the table names a premise something supplies.

        After assembly, not during parse — see `_check_when`. Called by `layers.load`, which
        is the one place that has finished stacking.
        """
        facts = set(measurements.ids()) | set(_GOAL_FACTS)
        facts |= {derivation.fact for derivation in self.derivations}
        for derivation in self.derivations:
            _check_when(
                derivation.rows,
                f"derivation {derivation.fact!r}",
                measurements=measurements,
                facts=facts,
            )
        self._no_target_is_decided_twice()
        for decision in self.decisions:
            where = f"decision {decision.key()}"
            _check_when(
                decision.rows, where, measurements=measurements, facts=facts
            )
            for row in decision.rows:
                if isinstance(row.then, FactRef) and row.then.fact not in facts:
                    raise RuleValidationError(coded(
                        "MD0310", f"{where}\n  `then` takes the value of {row.then.fact!r}, "
                        "which no measurement or derivation supplies, so this row can never "
                        "fire."))
            # After the stack, like everything else here: `add_values` lets an overlay extend
            # an enum, so a table exhaustive against the base layer alone is not exhaustive
            # against the stack it will actually run under. Checking per file would pass it.
            _check_exhaustive(decision, where, measurements=measurements)

    def _no_target_is_decided_twice(self) -> None:
        """No two decisions in the assembled table land on the same target.

        The gap a composite stacking key opens. A multi-target decision replaces as a whole,
        so its `stack()` key is the whole set — which means a second decision naming only one
        of those targets is a *different* key, stacks happily beside it, and both fire on that
        target. `MD0309`'s per-file check cannot see it and `stack()`'s per-layer check cannot
        see it either, because to both of them these are two different keys.

        The composite key remains necessary so a multi-target decision is replaced as a unit;
        this post-assembly check prevents another block from independently claiming one target.
        """
        decided_by: dict[str, str] = {}
        for decision in self.decisions:
            for target in decision.targets():
                if target.key() in decided_by:
                    raise RuleValidationError(
                        coded("MD0309", f"two decisions both land on {target.key()!r} — "
                        f"{decided_by[target.key()]!r} and {decision.key()!r}.\n"
                        f"  Only one of them will fire, and which one is not something a\n"
                        f"  reader of either file can work out. Merge them, or narrow one\n"
                        f"  with `when_implementation:`.")
                    )
                decided_by[target.key()] = decision.key()

    def _matching(self, key: str, premises: "dict[str, object]") -> tuple[str, list[Pin]]:
        """The decision's hit policy, and every row that fires for `key` here, in row order."""
        for decision in self.decisions:
            # `key()` is the composite; a two-target decision answers for either of them.
            if key not in {target.key() for target in decision.targets()}:
                continue
            pins = []
            for row in decision.rows:
                gives, value = row.value(premises)
                if gives and matches(row.when, premises):
                    pins.append(Pin(
                        value=value,
                        from_layer=self.layer_of.get(decision.key(), ""),
                        displaced_layer=self.displaced_layer.get(decision.key()),
                        decision=decision,
                        row=row,
                        premise=_premises_read(row, premises),
                    ))
                    if decision.hit == "first":
                        break
            return decision.hit, pins
        return "first", []

    def _for(self, key: str, premises: "dict[str, object]") -> Pin | None:
        hit, pins = self._matching(key, premises)
        if hit == "unique" and len(pins) > 1:
            return None  # a tie: `ties_for` names it, and the resolver asks
        return pins[0] if pins else None

    def ties_for(self, roles: Sequence[str], param: str, premises: "dict[str, object]", *,
                 implementation: str | None = None) -> list[Pin]:
        """Under `hit: unique`, the rows that all match for `param` here, when more than one
        does; otherwise none. A tie is a question for tier 4, never settled by row order."""
        for role in roles:
            hit, pins = self._matching(f"{Effect.PARAM}:{role}:{param}", premises)
            pins = [p for p in pins if _applies_to(p, implementation)]
            if hit == "unique" and len(pins) > 1:
                return pins
        return []

    def effects_for(self, premises: "dict[str, object]") -> list["Fired"]:
        """Every effect the table produces against these premises, in key order.

        One `Fired` per *target*, so a decision landing on two tools produces two effects
        carrying one premise and one citation — which is what makes it one choice rather than
        two that happen to agree.
        """
        fired: list[Fired] = []
        for decision in self.decisions:
            fired_rows = [r for r in decision.rows
                          if r.value(premises)[0] and matches(r.when, premises)]
            if not fired_rows:
                continue
            if decision.hit == "unique" and len(fired_rows) > 1:
                # A tie is shown as the question it becomes, never as no effect (#461).
                numbers = [str(decision.rows.index(r) + 1) for r in fired_rows]
                fired.extend(Fired(effect=t.effect, role=t.of, name=t.name, value=None,
                                   tier=Tier.AMBIGUOUS,
                                   because=f"rows {', '.join(numbers)} both match: a person "
                                           "is asked")
                             for t in decision.targets())
                continue
            row = fired_rows[0]
            value = row.value(premises)[1]
            pin = Pin(
                value=value,
                from_layer=self.layer_of.get(decision.key(), ""),
                displaced_layer=self.displaced_layer.get(decision.key()),
                decision=decision,
                row=row,
            )
            for target in decision.targets():
                fired.append(
                    Fired(
                        effect=target.effect,
                        role=target.of,
                        name=target.name,
                        value=value,
                        tier=tier_of_row(row.when),
                        because=pin.because(),
                        cite=row.cite or decision.cite or "",
                        axis_because=pin.axis_because(),
                    )
                )
        return sorted(fired, key=lambda f: f.key())

    def value_for(
        self,
        roles: Sequence[str],
        param: str,
        premises: "dict[str, object]",
        *,
        implementation: str | None = None,
    ) -> Pin | None:
        """The decided value for `param` on a node filling any of `roles`.

        Takes the node's roles as well as the parameter so a role-specific setting does not
        reach another role that happens to declare the same parameter name.

        Roles are tried in the order the contract declares them, so a contract filling two
        roles decided differently resolves by its own declaration rather than by dictionary
        order. A contract filling two roles that both decide one parameter is a registry
        defect; it is not refused here because the refusal belongs at load, where the message
        can name both decisions.
        """
        for role in roles:
            pin = self._for(f"{Effect.PARAM}:{role}:{param}", premises)
            if pin is not None and _applies_to(pin, implementation):
                return pin
        return None

    def implementation_for(self, role: str, premises: "dict[str, object]") -> Pin | None:
        return self._for(f"{Effect.IMPLEMENTATION}:{role}", premises)

    def unapplied_implementation(
        self, roles: Sequence[str], premises: "dict[str, object]"
    ) -> "tuple[Decision, list[str]] | None":
        """The first decision choosing an implementation for one of `roles` that no row of
        answers, and the premises its rows read that nobody knows.

        A rule that exists but cannot apply is a rule miss, not an absent rule. The router asks
        the person instead of falling through to priority and reports the missing premises.
        """
        for role in roles:
            key = f"{Effect.IMPLEMENTATION}:{role}"
            for decision in self.decisions:
                if key not in {target.key() for target in decision.targets()}:
                    continue
                if any(matches(row.when, premises) for row in decision.rows):
                    continue
                unknown = sorted(
                    {fact for row in decision.rows for fact in row.when if fact not in premises}
                )
                return decision, unknown
        return None

    def presence_for(self, role: str, premises: "dict[str, object]") -> Pin | None:
        return self._for(f"{Effect.PRESENCE}:{role}", premises)


def _premises_read(row: DecisionRow, premises: "dict[str, object]") -> list[PremiseRecord]:
    """The facts this row consulted, in `when` order and with their values.

    In `when` order rather than sorted, because that is the order the rule author wrote and a
    reader comparing the sentence against the table should meet them the same way.

    A key testing `absent` has no premise to record and contributes nothing: there is no
    value, and *"read_length is None, not measured"* would be a sentence about a fact that
    does not exist. Its absence is already what the row says.
    """
    read: list[PremiseRecord] = []
    taken = [row.then.fact] if isinstance(row.then, FactRef) else []
    named = list(dict.fromkeys([*row.when, *taken]))  # once each, in the order written
    for fact in named:
        premise = premises.get(fact)
        if premise is None:
            continue
        read.append(
            PremiseRecord(
                id=premise.id,
                value=premise.value,
                origin=premise.origin,
                by=premise.by,
                pieces=premise.pieces,
            )
        )
    return read


def _applies_to(pin: Pin, contract_id: str | None) -> bool:
    """Whether a narrowed `param` decision reaches this implementation.

    `when_implementation` is checked here as well as at load, and the two checks answer
    different questions: load asks *could this value ever be dead*, and this asks *is it dead
    right now*. Only the second knows which contract won.
    """
    narrowed = pin.decision.decides.when_implementation
    return not narrowed or contract_id is None or contract_id in narrowed
