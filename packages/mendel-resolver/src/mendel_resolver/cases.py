"""A rule's cases, and which of them its rows leave uncovered or overlap (#461, #466).

One value per interval and boundary the rows can tell apart, per fact: what `check_table`
tries at load, and what the build checks a run-time lookup against. A measurement in the run
can also come back without a value, so `cases` adds *undetermined* for each fact.
"""

import math
from collections.abc import Mapping, Sequence
from itertools import product

from comeni_core.declared.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.diagnostics import coded
from comeni_core.logic.when import matches

from mendel_resolver.rules.format import Decision, DecisionRow, _comparison

ORDERED = {MeasurementKind.INTEGER, MeasurementKind.NUMBER}


class _Undetermined:
    """A fact a measurement could not decide: no condition on it holds."""

    def __repr__(self) -> str:
        return "undetermined"


UNDETERMINED = _Undetermined()


CASE_BOUND = 4096
"""The most cases `check_table` tries; beyond it the table is refused (MD0324), so a clean check
always means every case was tried."""

class _Other:
    """A value an extensible enum may gain from an overlay, which no row can name today: it
    equals nothing a row names, so `{not: x}` and `present` match it and equality does not."""

    def __repr__(self) -> str:
        return "a value an overlay adds"


_OTHER = _Other()


class _Seen:
    __slots__ = ("value",)

    def __init__(self, value: object) -> None:
        self.value = value


def _points(fact: str, rows: Sequence[DecisionRow], measurements: MeasurementRegistry,
            derived: dict[str, MeasurementKind]) -> list[object] | None:
    """One value per case the rows can tell apart, or `None` when the fact cannot be enumerated
    (a goal fact, say), so the table is not checked."""
    kind = measurements.get(fact).kind if fact in measurements.ids() else derived.get(fact)
    tested = [row.when[fact] for row in rows if fact in row.when]
    if kind is MeasurementKind.BOOLEAN:
        return [True, False]
    if kind is MeasurementKind.ENUM and fact in measurements.ids():
        measurement = measurements.get(fact)
        return [*measurement.values, *([_OTHER] if measurement.extensible else [])]
    if kind in ORDERED:
        cuts: set[float] = set()
        for expected in tested:
            comparison = _comparison(expected)
            if comparison is not None:
                cuts.add(comparison[1])
                continue
            # `{in: [...]}` and `{not: x}` cut the line at each value they name.
            named = (expected.get("in", []) if isinstance(expected, dict) and "in" in expected
                     else [expected.get("not")] if isinstance(expected, dict) else [expected])
            cuts |= {float(v) for v in named
                     if isinstance(v, int | float) and not isinstance(v, bool)}
        if not cuts:
            return [1]
        ordered = sorted(cuts)
        # Each cut, a point between neighbouring cuts, and one beyond each end: every interval
        # the comparisons define is tried once, and every boundary on both sides. An integer
        # fact has no point between adjacent integers, so none is invented there.
        if kind is MeasurementKind.INTEGER:
            between = [math.floor(a) + 1 for a, b in zip(ordered, ordered[1:], strict=False)
                       if math.floor(a) + 1 < b]
            ends = [math.ceil(ordered[0]) - 1, math.floor(ordered[-1]) + 1]
        else:
            between = [(a + b) / 2 for a, b in zip(ordered, ordered[1:], strict=False)]
            ends = [ordered[0] - 1, ordered[-1] + 1]
        return sorted({*ordered, *between, *ends})
    return None



def cases(facts: Sequence[str], rows: Sequence[DecisionRow], measurements: MeasurementRegistry,
          derived: Mapping[str, MeasurementKind], *, bound: int = CASE_BOUND
          ) -> list[dict[str, object]] | None:
    """Every combination of one point per fact, with `UNDETERMINED` among each fact's points, in
    a fixed order; `None` when a fact cannot be enumerated. Refused (`MD0324`) above `bound`."""
    points = [_points(fact, rows, measurements, dict(derived)) for fact in facts]
    if any(p is None for p in points):
        return None
    points = [[*p, UNDETERMINED] for p in points]
    count = math.prod(len(p) for p in points)
    if count > bound:
        raise ValueError(coded("MD0324", f"the rows tell {count} cases apart over "
                               f"{', '.join(facts)}, above {bound}: fewer boundaries or facts, "
                               "or split the decision"))
    return [dict(zip(facts, case, strict=True)) for case in product(*points)]


def _seen(case: Mapping[str, object], known: Mapping[str, object]) -> dict[str, object]:
    seen = {f: _Seen(v) for f, v in case.items() if v is not UNDETERMINED}
    return {**known, **seen}


def _hits(decision: Decision, case: Mapping[str, object], known: Mapping[str, object]
          ) -> list[int]:
    seen = _seen(case, known)
    return [n for n, row in enumerate(decision.rows) if matches(row.when, seen)]


def uncovered(decision: Decision, unknown: Sequence[str], known: Mapping[str, object],
              measurements: MeasurementRegistry, derived: Mapping[str, MeasurementKind]
              ) -> list[dict[str, object]]:
    """The cases over `unknown` no row matches, with `known` facts substituted."""
    found = cases(sorted(unknown), decision.rows, measurements, derived)
    return [c for c in found or [] if not _hits(decision, c, known)]


def overlapping(decision: Decision, unknown: Sequence[str], known: Mapping[str, object],
                measurements: MeasurementRegistry, derived: Mapping[str, MeasurementKind]
                ) -> list[tuple[int, int, dict[str, object]]]:
    """Each pair of rows that match one case, as `(first, second, case)`."""
    found = []
    for case in cases(sorted(unknown), decision.rows, measurements, derived) or []:
        hits = _hits(decision, case, known)
        found += [(a, b, case) for i, a in enumerate(hits) for b in hits[i + 1:]]
    return found
