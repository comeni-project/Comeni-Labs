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
from comeni_core.goal.premise import PremiseRecord
from pydantic import BaseModel, ConfigDict, Field

from mendel_resolver.predicates import matches, tier_of_row
from mendel_resolver.rules.format import (
    _GOAL_FACTS,
    Decision,
    DecisionRow,
    Derivation,
    Effect,
    Fired,
    Pin,
    RuleValidationError,
)
from mendel_resolver.rules.validate import (
    _check_exhaustive,
    _check_when,
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
    """Decision key -> the layer whose block is in force. Audit A15.

    Deliberately *not* a field on `Decision`. A `Decision` is parsed straight out of a
    layer's YAML, so a provenance field there would be a provenance field a layer can
    write for itself — a rule file claiming `from_layer: comeni-registry-examples` while
    sitting in an overlay. Provenance must be recorded by the loader, which knows, rather
    than by the file, which can lie. Same reasoning that keeps `layer_of` off
    `ModuleContract`.
    """

    displaced_layer: dict[str, str] = Field(default_factory=dict)
    """Decision key -> the *lowest* layer whose block this one replaced, if any.

    `by_target[key] = decision` replaced a whole block and recorded nothing, so a tier-3
    parameter decided by a lab's overlay was indistinguishable from one decided by the
    public registry. Invariant 11 says all four kinds of declared data stack; only
    contracts were being watched. Audit A15.

    This is the *per-node* record — what `IRNode.selection.displaced_layer` reads. It is not
    the same thing as `displaced`, below: this one answers "which layer decided this key",
    keyed for lookup during resolution; that one is the full `Displacement` a reader audits.
    """

    displaced: list[Displacement] = Field(default_factory=list)
    """The rules kind's contribution to `PipelineIR.displaced`, one shape for all four kinds.

    `RuleTable` kept only `displaced_layer` — a key→name dict for per-node lookup — so when
    `resolve()` assembled `PipelineIR.displaced` off its arguments, rules had no full
    `Displacement` to contribute and a rule overlay reached the published artifact recording
    nothing (A51). The other three kinds already carried this; now the fourth does too, so
    the loader-level list `resolve()` reads is complete without the caller threading anything.
    """

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
            # Per file, because `MD0309` is about two decisions **in the same layer**: an
            # overlay replacing a block by key is legal and is the whole of invariant 11.
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
        return table

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

        Which is A119 again, arriving through the feature added to express one choice on two
        tools. Recorded here rather than fixed by abandoning the composite key, because half a
        replacement is the worse failure: it would leave a base layer's other target in force
        under a justification the overlay never wrote.
        """
        decided_by: dict[str, str] = {}
        for decision in self.decisions:
            for target in decision.targets():
                if target.key() in decided_by:
                    raise RuleValidationError(
                        f"MD0309: two decisions both land on {target.key()!r} — "
                        f"{decided_by[target.key()]!r} and {decision.key()!r}.\n"
                        f"  Only one of them will fire, and which one is not something a\n"
                        f"  reader of either file can work out. Merge them, or narrow one\n"
                        f"  with `when_implementation:`."
                    )
                decided_by[target.key()] = decision.key()

    def _for(self, key: str, premises: "dict[str, object]") -> Pin | None:
        for decision in self.decisions:
            # `key()` is the composite; a two-target decision answers for either of them.
            if key not in {target.key() for target in decision.targets()}:
                continue
            for row in decision.rows:
                if matches(row.when, premises):
                    return Pin(
                        value=row.then,
                        from_layer=self.layer_of.get(decision.key(), ""),
                        displaced_layer=self.displaced_layer.get(decision.key()),
                        decision=decision,
                        row=row,
                        premise=_premises_read(row, premises),
                    )
        return None

    def effects_for(self, premises: "dict[str, object]") -> list["Fired"]:
        """Every effect the table produces against these premises, in key order.

        One `Fired` per *target*, so a decision landing on two tools produces two effects
        carrying one premise and one citation — which is what makes it one choice rather than
        two that happen to agree.
        """
        fired: list[Fired] = []
        for decision in self.decisions:
            row = next((r for r in decision.rows if matches(r.when, premises)), None)
            if row is None:
                continue
            pin = Pin(
                value=row.then,
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
                        value=row.then,
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

        Takes the node's roles rather than the parameter alone, which is A123's fix at the
        point of use: `star_ignore_sjdbgtf` decided for role `alignment` reaches STAR and
        does not reach a sorter that happens to declare a parameter of the same name.

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
    for fact in row.when:
        premise = premises.get(fact)
        if premise is None:
            continue
        read.append(
            PremiseRecord(id=premise.id, value=premise.value, origin=premise.origin)
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


