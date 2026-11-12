"""A setting decided at run time, from a fact the pipeline measures (#217).

A rule can need a fact nobody knew before the build: a genome's length when nobody stated it.
When a pipeline measurer can reach that fact, the build adds the step that measures it and
compiles the rule into the pipeline as a lookup over the fact: every row listed here, before the
run, with the value each one gives and the value used when the measurement comes back
undetermined or no row matches. No model runs at run time, and the same goal gives the same
pipeline.

These are the build's record of that lookup. The compiler writes them as Groovy from the closed
operations below and nothing else; the resolver evaluates the same rows on the same cases, so the
two can be compared (`tests/execution/test_at_run_agreement.py`).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.spell.marks import (
    ContractId,
    Line,
    MeasurementId,
    NfIdentifier,
    NodeId,
    ParamValue,
    PortName,
    TypeId,
)


class AtRunTest(StrEnum):
    """What a row's condition asks of one fact. A fact with no value (undetermined, or a
    samplesheet cell left blank) passes only `absent`."""

    PRESENT = "present"
    """The fact has a value."""
    ABSENT = "absent"
    """The fact has none."""
    EQ = "=="
    NE = "!="
    IN = "in"
    GE = ">="
    GT = ">"
    LE = "<="
    LT = "<"


class AtRunOp(StrEnum):
    """One step of a derived fact's chain: the closed arithmetic of `derives:` (#461)."""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    LOG2 = "log2"
    AT_MOST = "at_most"
    AT_LEAST = "at_least"
    ROUND = "round"


class AtRunFallback(StrEnum):
    """What a run-time setting is when the lookup gives nothing."""

    VALUE = "value"
    TOOL = "tool"
    """Left unset: the tool uses its own."""
    QUESTION = "question"
    """A question still open."""
    STOP = "stop"
    """The run stops and names the sample: a person's answer when no value suits (#466)."""


class AtRunSource(StrEnum):
    """Where each sample's value of a fact comes from in the run (#466)."""

    CELL = "cell"
    """The samplesheet: a person said it differs between samples and nothing measures it."""
    MEASURED = "measured"
    """A step the build added measures it on every sample."""
    CELL_OR_MEASURED = "cell_or_measured"
    """The samplesheet where the cell is filled in; measured where it is blank or `auto`."""


class AtRunFact(BaseModel):
    """One fact a lookup reads, and how it reaches the sample's `meta`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: MeasurementId
    meta_key: NfIdentifier
    source: AtRunSource
    measured_by: ContractId | None = Field(default=None, exclude_if=lambda by: by is None)
    """The generated step that measures it, when a measurement is among its sources."""


class AtRunCondition(BaseModel):
    """One condition of a row on one fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fact: MeasurementId
    test: AtRunTest
    operand: list[ParamValue] = Field(default_factory=list, exclude_if=lambda o: not o)
    """One value for a comparison, several for `in`, none for `present` and `absent`."""


class AtRunStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    op: AtRunOp
    by: float | None = Field(default=None, exclude_if=lambda by: by is None)


class AtRunRow(BaseModel):
    """One row, with every fact known before the build already substituted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    when: list[AtRunCondition] = Field(default_factory=list, exclude_if=lambda w: not w)
    """Every condition holds for the row to match; none is a row that always matches."""
    then: ParamValue = None
    """The literal the row gives, when it gives one."""
    takes: MeasurementId | None = Field(default=None, exclude_if=lambda taken: taken is None)
    """The fact the row gives, through `transform` (`then: {fact: ...}`). A sample whose value
    of it is missing skips the row."""
    transform: list[AtRunStep] = Field(default_factory=list, exclude_if=lambda t: not t)
    """For `takes`: the derived fact's chain over that fact, left to right."""
    integer: bool = Field(default=False, exclude_if=lambda integer: not integer)
    """For `takes`: the result is a whole number, truncated as the resolver truncates an
    `integer` fact whose chain does not round it."""


class AtRun(BaseModel):
    """The lookup a setting is compiled into, and where its fact comes from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facts: list[AtRunFact]
    """Every fact the rows read, sorted by measurement, each on the sample's `meta`."""
    rule: Line
    """The decision compiled: `param:index_building.sa_index_nbases`."""
    rows: list[AtRunRow]
    """Tried in order; the first that matches decides."""
    fallback: ParamValue
    """The value when no row matches, a fact being undetermined included: what the setting
    would have been without the rule."""
    fallback_reason: Line
    fallback_is: "AtRunFallback" = Field(default="value",
                                         exclude_if=lambda kind: kind == "value")
    """What the fallback is: a value (a default or a person's answer), the tool's own (an
    omittable setting left unset), a stop naming the sample, or a question still open."""

    def fact(self, measurement: str) -> AtRunFact:
        return next(f for f in self.facts if f.measurement == measurement)


class MetaAtRun(BaseModel):
    """A measured fact joined into an input channel's `meta`, for a run-time setting to read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: MeasurementId
    meta_key: NfIdentifier
    type_id: TypeId
    """The input the fact describes, whose channel's `meta` carries it."""
    measured_at: NodeId
    """The step that measures it."""
    measured_port: PortName
    """That step's output carrying the fact."""


class Confirm(BaseModel):
    """An estimate a build decision rested on, measured again over all the data in the run.

    A fact the server read from an upload's head (`coverage: head`) chose a tool or a setting;
    the pipeline measures it in full. After the run, the two are compared: the same value is
    confirmed, a different one is a disagreement naming every decision listed here (#465)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: MeasurementId
    estimate: ParamValue | list[ParamValue]
    measured_at: NodeId
    """The step that measures it in full."""
    used_by: list[Line]
    """Sorted: `selection:<step>` for a tool chosen on it, `setting:<step>.<name>` for a
    setting decided from it."""


_ORDERED_TESTS = {">=": AtRunTest.GE, ">": AtRunTest.GT, "<=": AtRunTest.LE, "<": AtRunTest.LT,
                  "==": AtRunTest.EQ, "!=": AtRunTest.NE}


def condition_of(fact: str, expected) -> AtRunCondition:
    """A `when` entry on one fact, in the closed tests: `absent`, `present`, `{not: x}`,
    `{in: [...]}`, `">= 70"`, or a value for equality. The rules' `when` and a contract's
    `fact.` conditions read the same way (#466)."""
    if expected == "absent":
        return AtRunCondition(fact=fact, test=AtRunTest.ABSENT)
    if expected == "present":
        return AtRunCondition(fact=fact, test=AtRunTest.PRESENT)
    if isinstance(expected, dict):
        if "not" in expected:
            return AtRunCondition(fact=fact, test=AtRunTest.NE, operand=[expected["not"]])
        return AtRunCondition(fact=fact, test=AtRunTest.IN, operand=list(expected["in"]))
    if isinstance(expected, str):
        symbol, _, literal = expected.partition(" ")
        if symbol in _ORDERED_TESTS:
            try:
                return AtRunCondition(fact=fact, test=_ORDERED_TESTS[symbol],
                                      operand=[float(literal)])
            except ValueError:
                pass
    return AtRunCondition(fact=fact, test=AtRunTest.EQ, operand=[expected])


class SampleRule(BaseModel):
    """A tool's rule each sample's facts settle (#466): when every condition holds for a
    sample, the run stops before the step runs, naming the sample and the rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    when: list[AtRunCondition]
    says: Line
