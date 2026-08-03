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
from comeni_core.marks import ParamValue
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


class RuleTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[Decision] = Field(default_factory=list)

    @classmethod
    def load(
        cls,
        layers: Path | Sequence[Path],
        *,
        registry: Registry,
        vocabulary: Vocabulary,
        measurements: MeasurementRegistry,
    ) -> "RuleTable":
        if isinstance(layers, Path):
            layers = [layers]
        by_target: dict[str, Decision] = {}
        for layer in layers:
            if not layer.exists():
                continue
            seen_here: set[str] = set()
            paths = [layer] if layer.is_file() else sorted(layer.glob("*.yml"))
            for path in paths:
                data = yaml.safe_load(path.read_text()) or {}
                for raw in data.get("decisions", []):
                    decision = Decision.model_validate(raw)
                    key = decision.decides.key()
                    if key in seen_here:
                        raise RuleValidationError(
                            f"{path}: {key} is decided twice in one layer. Two blocks for one "
                            f"target is a mistake; shadowing happens between layers."
                        )
                    seen_here.add(key)
                    _validate(decision, path, registry, vocabulary, measurements)
                    # A higher layer replaces the whole block, not row by row: a reviewer
                    # should read one block and see the entire effective decision.
                    by_target[key] = decision
        return cls(decisions=[by_target[k] for k in sorted(by_target)])

    def _for(
        self, key: str, profile: DataProfile
    ) -> tuple[ParamValue, Decision, DecisionRow] | None:
        for decision in self.decisions:
            if decision.decides.key() != key:
                continue
            for row in decision.rows:
                if row.matches(profile):
                    return row.then, decision, row
        return None

    def value_for(
        self, param: str, profile: DataProfile
    ) -> tuple[ParamValue, Decision, DecisionRow] | None:
        return self._for(f"param:{param}", profile)

    def producer_for(
        self, type_id: str, profile: DataProfile
    ) -> tuple[ParamValue, Decision, DecisionRow] | None:
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
