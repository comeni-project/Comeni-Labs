"""Tier 3: declared decision tables matched against measured data.

A miss is not an escalation to a model. It is a demotion to tier 4.

The format is grouped: one block per decision, rows underneath. The three strandedness
rules used to be three entries repeating their subject and citation; a reviewer should read
the justification once and then read the branches — and grouping is also what lets them
notice a *missing* branch, which flat rules actively hide.

Every table is validated against the registry, the vocabulary and the measurements at load.
That is the load-bearing part: `subject` used to be an unvalidated free string, and two of
the five rules shipped in `examples/` had never once executed.
"""

import operator
from collections.abc import Sequence
from pathlib import Path

import yaml
from comeni_core.layered import (
    DeclaredKind,
    Kind,
    Layer,
    Policy,
    Stacked,
    layers_of,
    stack,
)
from comeni_core.marks import LayerName, ParamValue
from comeni_core.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.profile import DataProfile
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from pydantic import BaseModel, ConfigDict, Field

_OPS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}

_ORDERED = {MeasurementKind.INTEGER, MeasurementKind.NUMBER}


class RuleValidationError(ValueError):
    """Raised when a rule table cannot fire against the registry it was loaded with."""


def _comparison(expected: ParamValue) -> tuple[str, float] | None:
    """`">= 70"` as (symbol, literal), or None if this is an equality test.

    Written as one function because the load-time validator and the runtime matcher must
    agree on what counts as a comparison. Two copies of this predicate is how a rule
    passes validation and then fails to fire.
    """
    if not isinstance(expected, str):
        return None
    symbol, _, literal = expected.partition(" ")
    if symbol not in _OPS:
        return None
    try:
        return symbol, float(literal)
    except ValueError as exc:
        raise RuleValidationError(
            f"{expected!r} looks like a comparison but {literal!r} is not a number. "
            f"Write it as `\"{symbol} 70\"`, with a space."
        ) from exc


class DecisionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    param: str | None = None
    producer_of: str | None = None

    def key(self) -> str:
        return f"param:{self.param}" if self.param else f"producer_of:{self.producer_of}"


class DecisionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    when: dict[str, ParamValue] = Field(default_factory=dict)
    then: ParamValue = None
    because: str | None = None
    cite: str | None = None

    def matches(self, profile: DataProfile) -> bool:
        for measurement_id, expected in self.when.items():
            actual = profile.get(measurement_id)
            if actual is None:
                return False
            comparison = _comparison(expected)
            if comparison is not None:
                symbol, literal = comparison
                if not _OPS[symbol](actual, literal):
                    return False
            elif actual != expected:
                return False
        return True


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decides: DecisionTarget
    rows: list[DecisionRow] = Field(default_factory=list)
    because: str | None = None
    cite: str | None = None


class Pin(BaseModel):
    """A rule fired, and everything that follows from it — including where it came from.

    A22: `RuleTable` recorded `layer_of` and `displaced_layer` correctly, and
    `router._choose` never read them, so a rule-pinned reroute produced an IR asserting
    the *base* layer had decided. Recording a fact is not enough if consulting it is
    optional, so the fact travels with the answer rather than beside it. The caller cannot
    take the value without being handed the provenance in the same object.
    """

    model_config = ConfigDict(extra="forbid")

    value: ParamValue
    """The pinned contract id, or the parameter value. `then`, resolved."""
    from_layer: LayerName
    """The layer whose *rule block* decided. Not where the chosen contract was found —
    those differ, and the difference is the whole of A22."""
    displaced_layer: LayerName | None = None
    decision: Decision
    row: DecisionRow

    def because(self) -> str:
        """The most specific justification available, row before block."""
        return (
            self.row.cite
            or self.decision.cite
            or self.row.because
            or self.decision.because
            or ""
        )


class RuleTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[Decision] = Field(default_factory=list)

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

        def parse(path: Path) -> list[Decision]:
            data = yaml.safe_load(path.read_text()) or {}
            found = []
            for raw in data.get("decisions", []):
                decision = Decision.model_validate(raw)
                _validate(decision, path, registry, vocabulary, measurements)
                found.append(decision)
            return found

        return Kind(
            DeclaredKind.RULES,
            parse=parse,
            key=lambda decision: decision.decides.key(),
            policy=Policy.REPLACE,
        )

    @classmethod
    def of(cls, stacked: Stacked[str, Decision], layers: Sequence[Layer]) -> "RuleTable":
        name_of = {layer.index: layer.name for layer in layers}
        return cls(
            decisions=[stacked.entries[key] for key in sorted(stacked.entries)],
            layer_of={key: name_of[at] for key, at in stacked.origin.items()},
            displaced_layer={
                record.key: record.displaced_layer for record in stacked.displaced
            },
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
        return cls.of(
            stack(as_layers, cls.kind(registry, vocabulary, measurements)), as_layers
        )

    def _for(self, key: str, profile: DataProfile) -> Pin | None:
        for decision in self.decisions:
            if decision.decides.key() != key:
                continue
            for row in decision.rows:
                if row.matches(profile):
                    return Pin(
                        value=row.then,
                        from_layer=self.layer_of.get(key, ""),
                        displaced_layer=self.displaced_layer.get(key),
                        decision=decision,
                        row=row,
                    )
        return None

    def value_for(self, param: str, profile: DataProfile) -> Pin | None:
        return self._for(f"param:{param}", profile)

    def producer_for(self, type_id: str, profile: DataProfile) -> Pin | None:
        return self._for(f"producer_of:{type_id}", profile)


def _validate(
    decision: Decision,
    path: Path,
    registry: Registry,
    vocabulary: Vocabulary,
    measurements: MeasurementRegistry,
) -> None:
    target = decision.decides
    if bool(target.param) == bool(target.producer_of):
        raise RuleValidationError(f"{path}: a decision decides exactly one of param, producer_of")

    if target.param:
        declared = sorted({p.name for c in registry.all() for p in c.params})
        if target.param not in declared:
            raise RuleValidationError(
                f"{path}, decision {target.key()}\n"
                f"  No contract in the registry declares a parameter named {target.param!r}.\n"
                f"  Parameters that do exist: {', '.join(declared) or '(none)'}"
            )
    else:
        if target.producer_of not in vocabulary.types:
            raise RuleValidationError(
                f"{path}: {target.producer_of!r} is not a declared type.\n"
                f"  Types that do exist: {', '.join(sorted(vocabulary.types))}"
            )
        for row in decision.rows:
            contract_id = str(row.then)
            if contract_id not in registry.contracts:
                raise RuleValidationError(
                    f"{path}: {contract_id!r} is not in the registry, so this row can never "
                    f"be applied. A rule table is only valid against a registry that can "
                    f"satisfy it."
                )
            produced = {p.type_id for p in registry.get(contract_id).produces}
            if target.producer_of not in produced:
                raise RuleValidationError(
                    f"{path}: {contract_id!r} does not produce {target.producer_of!r}"
                )

    for row in decision.rows:
        for measurement_id, expected in row.when.items():
            try:
                # Raises naming what *is* declared, which is the half of the message an
                # author actually needs. Re-raised as a rule error so a bad table is one
                # kind of failure to the caller rather than two.
                measurement = measurements.get(measurement_id)
            except KeyError as exc:
                raise RuleValidationError(
                    f"{path}, decision {target.key()}\n  {exc.args[0]}"
                ) from exc
            if _comparison(expected) is not None and measurement.kind not in _ORDERED:
                raise RuleValidationError(
                    f"{path}: {measurement_id!r} is an {measurement.kind}, so it can only be "
                    f"compared with equality, not {expected!r}"
                )
