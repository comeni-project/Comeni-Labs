"""What a tier-3 rule *is*. The two layers' models, and nothing that loads or refuses one.

Split from `rules.py` for issue #41: that file was 1,170 lines answering three questions, and
this is the first — a reader here is asking what they may write in a `rules/` file, not how it
is stacked or why theirs was refused.

The format is grouped: one block per decision, rows underneath. The three strandedness rules
used to be three entries repeating their subject and citation; a reviewer should read the
justification once and then read the branches — and grouping is also what lets them notice a
*missing* branch, which flat rules actively hide.

`_comparison` lives here rather than in `validate.py` even though the validator is its heaviest
caller: the load-time check and the runtime matcher must agree on what counts as a comparison,
and two copies of that predicate is how a rule passes validation and then fails to fire. It sits
with the models because that agreement is a property of the format.
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
    """What a decision changes. Spec §4.1.

    Three, because a rule about *whether a step exists* and a rule about *which tool fills
    it* are different claims and the shipped format could only spell the first as the second:
    `producer_of: fastq.reads` with `then: null` was the way to say "do not trim". That reads
    as a null pointer rather than as a sentence about a pipeline.
    """

    PRESENCE = "presence"
    PARAM = "param"
    IMPLEMENTATION = "implementation"


class DecisionTarget(BaseModel):
    """What a decision decides — an effect on a **role**, never on a type. Spec §4.1.

    A119 and A123 are one defect from two sides. The old target admitted `{param: X}` and
    `{producer_of: T}`, so a rule about duplicate handling and a rule about which aligner to
    use both keyed on `alignment.bam`, and `Policy.REPLACE` resolved that collision by
    deleting one of them — silently, at exit 0. Keying on `(effect, role[, name])` is what
    makes the two rules different keys rather than the same one.
    """

    model_config = ConfigDict(extra="forbid")

    effect: Effect
    of: RoleName
    name: str | None = None
    """The parameter, for a `param` effect. Meaningless for the other two."""

    when_implementation: list[ContractId] = Field(default_factory=list)
    """Narrow a `param` effect to the implementations that declare it.

    `star_ignore_sjdbgtf` is STAR's alone, so a rule deciding it for the whole `alignment`
    role sets a value that is dead whenever HISAT2 wins — issue #10's deadness, arriving
    through the rule format rather than through a contract. Naming the implementations is the
    author saying which ones the value is *for*, and `MD0308` is what makes them say it.
    """

    def key(self) -> str:
        return f"{self.effect}:{self.of}" + (f":{self.name}" if self.name else "")


Predicate = ParamValue | dict[str, ParamValue | list[ParamValue]]
"""What a `when` may test a premise against: a value, a comparison string, `absent`,
`present`, or a mapping predicate — `{not: x}`, `{in: [x, y]}`.

The mapping arm was missing until the twenty-rule corpus was wired in, and its absence is
the reason A121 was only **half** closed by Task 3: `predicates.matches` implements `not` and
`in`, and `DecisionRow.when` was typed `dict[str, ParamValue]`, so a rule using either was
refused by pydantic before the evaluator ever saw it. An evaluator handling a case the model
cannot represent is the same defect as a model permitting a case the evaluator ignores, and
neither shows up until somebody writes the rule.
"""


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
    """A row that matched, and everything a caller needs without consulting the table again.

    A22's shape: `RuleTable` recorded provenance correctly and the one caller that had to
    remember to read it did not. The answer carries its own evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect: Effect
    role: RoleName
    name: str | None = None
    value: ParamValue = None
    tier: Tier = Tier.DATA_PROFILED
    because: str = ""
    cite: str = ""
    axis_because: str = ""
    """The block's justification — the methodology, kept apart from the row's choice.

    One field carried both and printed the axis citation as the row's reason, so the shipped
    registry said HISAT2 was chosen because of the paper describing STAR. A79, A107.
    """

    def key(self) -> str:
        return f"{self.effect}:{self.role}" + (f":{self.name}" if self.name else "")


class Aggregate(BaseModel):
    """Reduce a per-sample measurement to one value. Spec §3.2.

    `over` is `cohort` and nothing else, and it is written out rather than assumed because
    the cohort-versus-sample question is the one the shipped format could not even ask —
    `read_length: ">= 70"` against a cohort of three has no defined meaning, and the format
    gave a rule author no way to say which they meant.
    """

    model_config = ConfigDict(extra="forbid")

    measurement: MeasurementId
    over: Literal["cohort"]
    using: Literal["max", "min", "mean"]


class Transform(BaseModel):
    """One named arithmetic step. Issue #39, without an expression language.

    `then: "read_length-1"` loaded, resolved at tier 3 with a citation, and reached STAR as
    that literal string (A118); `MD0300` made the refusal honest and left the rule unwritable.
    A chain of these expresses it, and the shape is the argument: **a named unary operation
    with a literal operand** is readable in YAML, checkable at load, printable as prose, and
    has nowhere to grow into a solver. There is no parser, no precedence, and no way to
    reference a second fact — the one thing a general expression language would buy and the
    thing that turns a rule table into a program.

    `spec §7.1` asks for arithmetic and `docs/design/rule-tables-and-port-logic.md` §13.2 asks
    for it not to reintroduce a solver. Left-to-right named steps is what satisfies both.
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
    """A fact the registry works out, rather than one a tool measured. Spec §3.1.

    A derivation naming a **declared measurement** is a fallback: it may fill a gap and may
    never overwrite. That asymmetry is the whole of it. R15 — *"infer strandedness where
    nothing measured it"* — is unwritable in the shipped format because `when` can only read
    a measurement that is present, so the row validates and can never fire (A122); and a
    version that could fire without the asymmetry would be worse, because it would resolve a
    pipeline against a default while the profile printed beside it named the measured value.

    `kind` is declared rather than inferred from `then`, for the same reason a measurement
    declares one: it says what the fact may hold before any row has produced a value, which
    is what Task 10's type check over `then` will read.
    """

    model_config = ConfigDict(extra="forbid")

    fact: MeasurementId
    kind: MeasurementKind
    rows: list[DecisionRow] = Field(default_factory=list)
    aggregate: Aggregate | None = None
    source: MeasurementId | None = None
    """The fact a `transform` chain starts from."""

    transform: list[Transform] = Field(default_factory=list)
    """A chain of named arithmetic steps over `source`. Issue #39; see `Transform`."""

    because: str | None = None
    cite: str | None = None

    @model_validator(mode="after")
    def _can_fire(self) -> "Derivation":
        """Exactly one of `rows`, `aggregate` and `transform`, and never none.

        A derivation that can produce nothing is A122's own shape, one layer down: it loads
        clean, contributes nothing, and reads to a reviewer as a fact the registry supplies.
        Refused at load rather than reported at resolution, because by resolution the fact is
        simply absent and nothing can tell an empty derivation from one that was never
        written. Spec §5.

        Both is refused rather than ordered, because an order here would be a rule nobody
        reading the file could see — invariant 8's argument, one layer down again.
        """
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
    premise: list[PremiseRecord] = Field(default_factory=list)
    """The facts this row actually read, in `when` order.

    On the `Pin` rather than looked up by the caller, for the reason A22 gives about every
    other field here: a fact the caller must remember to fetch is a fact one of them will
    not. `reason_line` needs it and so does `Why`.
    """

    def because(self) -> str:
        """Why **this row** won — the specific choice, never the axis.

        Was `row.cite or decision.cite or row.because or decision.because`, under a docstring
        that said *"row before block"*. Two bugs in one line, and each was found by a
        different reviewer from a different direction:

        - **The precedence was cite-first, not row-first** (A107). A `cite` shadowed a
          `because`, so the registry's only plain-English explanation of its only tier-3
          decision never reached the artifact. A reader got a DOI where a sentence belonged.
        - **A block `cite` answers a different question** (A79). It justifies the decision
          *axis* — "read length determines which aligner is appropriate", for which Dobin et
          al. is a fair citation — and it was printed as the reason for a *row*. So the
          shipped registry said HISAT2 was chosen because of the paper describing STAR,
          reachable by changing one number in `examples/rnaseq-goal.yml`.

        The second is why this is not a reordering. The field was answering two questions, so
        it becomes two: this one, and `axis_because` below.

        **A citation and a sentence are joined, never chosen between.** Preferring one was the
        A107 half of this bug, and writing `row.because or row.cite` here would have repeated
        it exactly one level down — the sentence would have shadowed the row's own paper
        instead of the reverse. A reader wants the claim and the evidence for it.
        """
        return _joined(self.row.because, self.row.cite)

    def reason_line(self, matched: object = None) -> str:
        """`rule <key>[ where <premises>][: <row justification>]`, with no dangling colon.

        **`matched` is ignored and kept for callers.** It used to be the raw `when` mapping,
        and the shipped artifact read

            reason: 'rule producer_of:alignment.bam matched {''read_length'': ''>= 70''}: …'

        — a Python dict repr embedded in YAML with doubled quotes, reporting the *predicate*
        and never the value. A reader learned the rule tested `>= 70` and never learned that
        `read_length` was 150, or that anything had measured it. The premise is the one thing
        tier 3 asks a reviewer to check, and spec §6.1 says no structured value is a reader's
        only account of itself.

        On `Pin` rather than in `resolve`, because `router` needs it too and importing
        `resolve` from `router` is a cycle — and because every input it formats is already
        here. A row may be justified entirely by its block (a one-row rule often is) and
        `MD0301` allows that, but `rule param:strandedness: ` with nothing after the colon
        reads as a truncation rather than as an absence, which is half of what A78 was.
        """
        head = f"rule {self.decision.key()}"
        if self.premise:
            head = f"{head} where " + "; ".join(record.prose() for record in self.premise)
        because = self.because()
        return f"{head}: {because}" if because else head

    def axis_because(self) -> str:
        """Why this decision is made this way **at all** — the block's justification.

        Kept separate rather than concatenated, because a reader wants to know both and to be
        able to tell which is which: the axis is the methodology, the row is the choice made
        under it. A79, A107.
        """
        return _joined(self.decision.because, self.decision.cite)


