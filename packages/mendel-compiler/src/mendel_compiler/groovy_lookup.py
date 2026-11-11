"""A run-time setting's lookup, written as one Groovy expression over `meta` (#217).

The build recorded the lookup (`comeni_core.plan.at_run.AtRun`): rows tried in order over the
measured fact, each giving a literal or the fact through a derived fact's chain, and a fallback.
Here it becomes an expression a task's `ext.args` closure evaluates against its sample's `meta`:

    (meta.genome_length == null ? 11 : (true ? ((((...)) as long)) : 11))

Generated only from the closed tests and operations of `at_run`, and from literals checked as
substitutable, so nothing outside them reaches Groovy. The arithmetic is the resolver's: `round`
is `Math.rint` (half to even, as Python's `round`), an integer result is truncated toward zero
(as Python's `int`), and `log2` lands on a whole number when it is within 1e-9 of one, as
`math.log2` does for a power of two. Numbers are compared as doubles, since a measured value
arrives through `JsonSlurper` as an Integer, a Long or a BigDecimal, and Groovy's `in` would
tell `70` from `70.0` where Python does not. `tests/emit/test_at_run_agreement.py` runs both over
the table check's cases, parsed from JSON as the pipeline parses them.
"""

import math

from comeni_core.diagnostics import coded
from comeni_core.plan.at_run import (
    AtRun,
    AtRunCondition,
    AtRunFallback,
    AtRunOp,
    AtRunRow,
    AtRunStep,
    AtRunTest,
)
from comeni_core.spell.marks import substitutable


def literal(value: object, where: str) -> str:
    """A value as a Groovy literal, refused (`MD0201`) outside the substitutable class."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(coded("MD0201", f"{where} is {value!r}, which is not a finite number."))
    if isinstance(value, int | float):
        return repr(float(value)) if isinstance(value, float) else str(value)
    if not substitutable(value):
        raise ValueError(coded(
            "MD0201",
            f"{where} is {value!r}, which is outside the substitutable class, so a run-time "
            "setting cannot carry it into Nextflow. Use letters, digits and _ . : + - only, "
            "or a number, or true/false."))
    return f"'{value}'"


def _number(value: object, where: str) -> str:
    return repr(float(value)) if isinstance(value, int | float) else literal(value, where)


def _step(step: AtRunStep, x: str, where: str) -> str:
    by = _number(step.by, where) if step.by is not None else None
    return {
        AtRunOp.ADD: lambda: f"({x} + {by})",
        AtRunOp.SUBTRACT: lambda: f"({x} - {by})",
        AtRunOp.MULTIPLY: lambda: f"({x} * {by})",
        AtRunOp.DIVIDE: lambda: f"({x} / {by})",
        AtRunOp.AT_MOST: lambda: f"Math.min({x}, {by})",
        AtRunOp.AT_LEAST: lambda: f"Math.max({x}, {by})",
        AtRunOp.ROUND: lambda: f"Math.rint({x})",
        AtRunOp.LOG2: lambda: _log2(x),
    }[step.op]()


def _log2(x: str) -> str:
    raw = f"(Math.log({x}) / Math.log(2.0d))"
    return f"(Math.abs({raw} - Math.rint({raw})) < 1e-9 ? Math.rint({raw}) : {raw})"


def transform(steps: list[AtRunStep], var: str, *, integer: bool, where: str = "a lookup") -> str:
    """The chain over `var`, left to right, as the resolver's `_transform` computes it. A chain
    ending in `round` is a whole number either way: Python's `round` gives an int, so the flag
    reads `2`, never `2.0`."""
    if not steps:
        return f"({var} as long)" if integer else var
    value = f"({var} as double)"
    for step in steps:
        value = _step(step, value, where)
    whole = integer or steps[-1].op is AtRunOp.ROUND
    return f"({value} as long)" if whole else value


def _numeric(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _condition(condition: AtRunCondition, where: str) -> str:
    """One condition over `meta.<fact>`. A fact with no value passes only `absent`, as
    `matches` has it: every other test is guarded on a value being there."""
    var = f"meta.{condition.fact}"
    if condition.test is AtRunTest.ABSENT:
        return f"({var} == null)"
    if condition.test is AtRunTest.PRESENT:
        return f"({var} != null)"
    number = f"({var} instanceof Number)"
    if condition.test is AtRunTest.IN:
        if all(_numeric(o) for o in condition.operand):
            listed = ", ".join(_number(o, where) for o in condition.operand)
            return f"({number} && [{listed}].any {{ it == ({var} as double) }})"
        listed = ", ".join(literal(o, where) for o in condition.operand)
        return f"({var} != null && {var} in [{listed}])"
    (operand,) = condition.operand
    if condition.test in (AtRunTest.EQ, AtRunTest.NE) and _numeric(operand):
        equal = f"(({var} as double) == {_number(operand, where)})"
        test = equal if condition.test is AtRunTest.EQ else f"!{equal}"
        return f"({number} && {test})"
    if condition.test in (AtRunTest.EQ, AtRunTest.NE):
        return f"({var} != null && {var} {condition.test.value} {literal(operand, where)})"
    # A comparison on something that is not a number does not match, as `matches` has it.
    return f"({number} && ({var} as double) {condition.test.value} {_number(operand, where)})"


def _row(row: AtRunRow, where: str) -> str:
    """Every condition of the row, and a value for the fact it takes."""
    parts = [_condition(c, where) for c in row.when]
    if row.takes is not None:
        parts.append(f"(meta.{row.takes} != null)")
    return " && ".join(parts) if parts else "true"


def _value(row: AtRunRow, where: str) -> str:
    if row.takes is not None:
        return transform(row.transform, f"meta.{row.takes}", integer=row.integer, where=where)
    return literal(row.then, where)


def _fallback(at_run: AtRun, where: str) -> str:
    if at_run.fallback_is is AtRunFallback.STOP:
        names = [at_run.rule, *(f.measurement for f in at_run.facts)]
        if not all(substitutable(n) for n in names):
            raise ValueError(coded("MD0201", f"{where}: {names!r} cannot be written as Groovy"))
        said = (f"no row of {at_run.rule} applies to its "
                + ", ".join(f.measurement for f in at_run.facts))
        return ("({ -> throw new IllegalStateException('sample ' + meta.id + ': "
                f"{said}') }}())")
    return literal(at_run.fallback, where)


def closure(at_run: AtRun, *, where: str = "a run-time setting") -> str:
    """The lookup as one expression over the sample's `meta`: the first row whose conditions
    all hold gives its value; when none does, the fallback (which may stop the run)."""
    expression = _fallback(at_run, where)
    for row in reversed(at_run.rows):
        expression = f"({_row(row, where)} ? {_value(row, where)} : {expression})"
    return expression
