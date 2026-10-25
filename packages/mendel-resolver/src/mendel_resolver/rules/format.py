"""Pydantic models and shared predicates for the tier-3 rule-file format.

Decision blocks group ordered rows under one target and axis justification. Derivations either
match rows, aggregate a cohort measurement, or transform one source fact. The comparison parser
is shared by load-time validation and runtime matching so both interpret rule text identically.
"""

import operator
from enum import StrEnum
from typing import Literal

from comeni_core.declared.measurement import MeasurementKind
from comeni_core.diagnostics import coded
from comeni_core.goal.premise import PremiseRecord
from comeni_core.goal.profile import DataProfile
from comeni_core.plan.tiers import Tier
from comeni_core.spell.marks import ContractId, LayerName, MeasurementId, ParamValue, RoleName
from pydantic import BaseModel, ConfigDict, Field, model_validator

_OPS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}



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


_GOAL_FACTS = frozenset({"required_states"})
"""Premises the goal supplies rather than any measurement. Kept beside the rule validator
because this is the list a `when` key is checked against; `premises.py` is where they are
built. Two places, one fact — which is why the name is shared rather than the literal."""


class Effect(StrEnum):
    """Whether a decision changes step presence, implementation, or a parameter."""

    PRESENCE = "presence"
    PARAM = "param"
    IMPLEMENTATION = "implementation"


class DecisionTarget(BaseModel):
    """An effect on a role, optionally narrowed to a named parameter and implementations."""

    model_config = ConfigDict(extra="forbid")

    effect: Effect
    of: RoleName
    name: str | None = None
    """The parameter, for a `param` effect. Meaningless for the other two."""

    when_implementation: list[ContractId] = Field(default_factory=list)
    """Narrow a `param` effect to the implementations that declare it.

    This prevents a tool-specific parameter from being applied when another implementation fills
    the same role.
    """

    def key(self) -> str:
        return f"{self.effect}:{self.of}" + (f":{self.name}" if self.name else "")


Predicate = ParamValue | dict[str, ParamValue | list[ParamValue]]
"""A literal, comparison, presence test, negation, or membership predicate in ``when``."""


class DecisionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    when: dict[str, Predicate] = Field(default_factory=dict)
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

    decides: DecisionTarget | list[DecisionTarget]
    rows: list[DecisionRow] = Field(default_factory=list)
    because: str | None = None
    cite: str | None = None

    def targets(self) -> list[DecisionTarget]:
        """A decision landing on two tools is **one** choice with one premise and one citation.

        Spec §4.2. `star_ignore_sjdbgtf` depends on how the index was built: supplying splice
        junctions at index time and ignoring them at align time is a single call about where
        the annotation is used, spelled as two flags on two tools.

        Modelling it as two decisions would make the second read the first, and decisions
        reading decisions is what this format refuses — it buys evaluation order, the
        possibility of a cycle, and the loss of `build_premises`' single pass. One block also
        means a reviewer reads the justification once, which is why the format is grouped at
        all.
        """
        return self.decides if isinstance(self.decides, list) else [self.decides]

    def key(self) -> str:
        """One `stack()` key for the whole decision, because it replaces as a whole.

        An overlay replacing a two-target decision has to decide the same two things: half a
        replacement would leave the base's other half in force under a justification the
        overlay never wrote. That the composite key lets a *different* decision land on one of
        those targets is a real gap and is closed after assembly — see
        `_no_target_is_decided_twice`, and the test that reaches it.
        """
        return "+".join(sorted(target.key() for target in self.targets()))


class Fired(BaseModel):
    """A matched row with its value, tier, justification, and layer evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect: Effect
    role: RoleName
    name: str | None = None
    value: ParamValue = None
    tier: Tier = Tier.DATA_PROFILED
    because: str = ""
    cite: str = ""
    axis_because: str = ""
    """The block-level methodology, kept separate from the row-specific choice."""

    def key(self) -> str:
        return f"{self.effect}:{self.role}" + (f":{self.name}" if self.name else "")


class Aggregate(BaseModel):
    """Reduce a per-sample measurement across a cohort using a named operation."""

    model_config = ConfigDict(extra="forbid")

    measurement: MeasurementId
    over: Literal["cohort"]
    using: Literal["max", "min", "mean"]


class Transform(BaseModel):
    """One named arithmetic operation in a left-to-right derivation chain.

    Every operation except ``log2`` requires a literal operand. The closed operation set avoids
    expression parsing, precedence, and references to additional facts.
    """

    model_config = ConfigDict(extra="forbid")

    op: Literal["add", "subtract", "multiply", "divide", "log2", "at_most", "at_least"]
    by: float | None = None
    """The operand. Required by every op but `log2`, which takes none."""

    @model_validator(mode="after")
    def _operand_matches_the_op(self) -> "Transform":
        needs = self.op != "log2"
        if needs and self.by is None:
            raise ValueError(coded("MD0304", f"`{self.op}` needs a `by:`"))
        if not needs and self.by is not None:
            raise ValueError(coded("MD0304", f"`{self.op}` takes no `by:`, and one was given"))
        if self.op == "divide" and self.by == 0:
            raise ValueError(coded("MD0304", "`divide` by zero"))
        return self


class Derivation(BaseModel):
    """A typed fact computed by rows, a cohort aggregate, or a transform chain.

    A derivation that names an existing measurement is a fallback and never overwrites measured
    evidence. Exactly one computation form is required.
    """

    model_config = ConfigDict(extra="forbid")

    fact: MeasurementId
    kind: MeasurementKind
    rows: list[DecisionRow] = Field(default_factory=list)
    aggregate: Aggregate | None = None
    source: MeasurementId | None = None
    """The fact a `transform` chain starts from."""

    transform: list[Transform] = Field(default_factory=list)
    """A chain of named arithmetic steps over `source`; see :class:`Transform`."""

    because: str | None = None
    cite: str | None = None

    @model_validator(mode="after")
    def _can_fire(self) -> "Derivation":
        """Require exactly one computation form and a source iff transforms are present."""
        declared = [
            name
            for name, present in (
                ("rows", bool(self.rows)),
                ("aggregate", self.aggregate is not None),
                ("transform", bool(self.transform)),
            )
            if present
        ]
        if len(declared) != 1:
            has = f"{', '.join(declared)}" if declared else "none of them"
            raise ValueError(
                coded(
                    "MD0304",
                    f"derivation {self.fact!r} declares {has}, and needs exactly one of "
                    f"`rows`, `aggregate` and `transform`. A derivation that can produce nothing "
                f"still reads as a fact the registry supplies; one that could produce two "
                f"would resolve by a precedence no reader of the file can see.")
            )
        if bool(self.transform) != (self.source is not None):
            raise ValueError(
                coded("MD0304", f"derivation {self.fact!r} declares "
                f"{'a `transform` with no `source`' if self.transform else 'a `source` with no '
                 '`transform`'}. A chain with nothing to chain from computes nothing and reads "
                f"as a fact the registry supplies.")
            )
        return self


def _joined(*parts: str | None) -> str:
    """A sentence and its citation, in one line, without `one.; Kim et al.`

    The trailing stop is dropped from every part but the last, because a rule author writes
    prose that ends in a full stop and a citation that does not, and the two meet here rather
    than in the file either of them was written in.
    """
    kept = [part.strip() for part in parts if part and part.strip()]
    return "; ".join(
        part.rstrip(".") if index < len(kept) - 1 else part
        for index, part in enumerate(kept)
    )


class Pin(BaseModel):
    """A pinned value carrying its decision, matched row, premises, and layer provenance."""

    model_config = ConfigDict(extra="forbid")

    value: ParamValue
    """The pinned contract id, or the parameter value. `then`, resolved."""
    from_layer: LayerName
    """The layer whose rule block decided, not the layer containing the chosen contract."""
    displaced_layer: LayerName | None = None
    decision: Decision
    row: DecisionRow
    premise: list[PremiseRecord] = Field(default_factory=list)
    """The facts this row actually read, retained in ``when`` order."""

    def because(self) -> str:
        """Join the matched row's explanation and citation without using axis-level prose."""
        return _joined(self.row.because, self.row.cite)

    def reason_line(self, matched: object = None) -> str:
        """Render the rule key, consulted premise prose, and optional row justification.

        ``matched`` remains accepted for caller compatibility but is ignored; structured
        predicate text is not substituted for the actual premise values.
        """
        head = f"rule {self.decision.key()}"
        if self.premise:
            head = f"{head} where " + "; ".join(record.prose() for record in self.premise)
        because = self.because()
        return f"{head}: {because}" if because else head

    def axis_because(self) -> str:
        """Join the block-level methodology and citation, separate from row justification."""
        return _joined(self.decision.because, self.decision.cite)
