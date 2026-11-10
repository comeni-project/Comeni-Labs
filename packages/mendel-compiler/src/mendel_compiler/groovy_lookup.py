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
from comeni_core.plan.at_run import AtRun, AtRunOp, AtRunRow, AtRunStep, AtRunTest
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


def _condition(row: AtRunRow, var: str, where: str) -> str:
    if row.test is AtRunTest.ANY:
        return "true"
    number = f"({var} instanceof Number)"
    if row.test is AtRunTest.IN:
        if all(_numeric(o) for o in row.operand):
            listed = ", ".join(_number(o, where) for o in row.operand)
            return f"({number} && [{listed}].any {{ it == ({var} as double) }})"
        return f"({var} in [{', '.join(literal(o, where) for o in row.operand)}])"
    (operand,) = row.operand
    if row.test in (AtRunTest.EQ, AtRunTest.NE) and _numeric(operand):
        equal = f"({number} && ({var} as double) == {_number(operand, where)})"
        return equal if row.test is AtRunTest.EQ else f"!{equal}"
    if row.test in (AtRunTest.EQ, AtRunTest.NE):
        return f"({var} {row.test.value} {literal(operand, where)})"
    # A comparison on something that is not a number does not match, as `matches` has it.
    return f"({number} && ({var} as double) {row.test.value} {_number(operand, where)})"


def _value(row: AtRunRow, var: str, where: str) -> str:
    if row.takes_fact:
        return transform(row.transform, var, integer=row.integer, where=where)
    return literal(row.then, where)


def closure(at_run: AtRun, *, where: str = "a run-time setting") -> str:
    """The lookup as one expression over `meta.<key>`: the fallback when the fact is null
    (undetermined) or no row matches, else the first matching row's value."""
    var = f"meta.{at_run.meta_key}"
    fallback = literal(at_run.fallback, where)
    expression = fallback
    for row in reversed(at_run.rows):
        expression = f"({_condition(row, var, where)} ? {_value(row, var, where)} : {expression})"
    return f"({var} == null ? {fallback} : {expression})"
