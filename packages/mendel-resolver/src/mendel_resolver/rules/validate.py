"""Every way a rule table is refused at load. The `MD0300`–`MD0315` band.

Its own module because this is where a rule author's error comes from, and it was ~450 lines
buried under the models it refuses.

Spec §5: everything is refused at load. The argument is always the same — the moment a defect
becomes indistinguishable from an absence, the diagnostic stops being possible. A derivation
with no rows contributes nothing and reads as a fact the registry supplies; a rule naming a role
nothing fills can never apply and reads as a rule somebody wrote; a table with a hole does not
fail but *demotes*, and tier 4 with "no rule matched" beside it reads as an ambiguity rather
than as three branches of a four-branch table.

Two checks run **after the stack is assembled** rather than per file, and both for the same
reason: a decision may read a fact a derivation in another file supplies, and an overlay may
extend an enum with `add_values`. A per-file check would refuse a legitimate rule for the
accident of which file `stack()` reached first.
"""

import re
from collections.abc import Sequence
from pathlib import Path

from comeni_core.declared.contract import ParamDomain
from comeni_core.declared.measurement import MeasurementKind, MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.diagnostics import coded
from comeni_core.plan.tiers import Tier

from mendel_resolver.predicates import tier_of_row
from mendel_resolver.rules.format import (
    _GOAL_FACTS,
    Decision,
    DecisionRow,
    DecisionTarget,
    Effect,
    RuleValidationError,
    _comparison,
)

_ORDERED = {MeasurementKind.INTEGER, MeasurementKind.NUMBER}
"""The measurement kinds a `>=`-style comparison is meaningful over.

Here rather than beside `_OPS` in `format.py` because only the validator asks the question:
an enum compares with equality, `in` or `not`, and refusing `">= 70"` over one is a refusal,
not a shape.
"""


def _computed_over(then: object, measurement_ids: list[str]) -> str | None:
    """The measurement this `then` reads as arithmetic over, or `None` if it is a value.

    `MD0300`. `DecisionRow.then` is emitted **verbatim** — nothing between the rule table and
    `nextflow.config` evaluates it — so `then: "read_length-1"` reached STAR as the literal
    string `read_length-1`, at tier 3, cited to Dobin et al. 2013, and absent from the review
    list. The only thing that ever refused it was `MD0201`, a shell-injection character class
    that permits `-`, and only on the spaced spelling. Audit A118.

    **A substring test is too loose and would be worse than nothing.** `paired` is a declared
    measurement, so `then: "paired-end"` would be refused by one — a legitimate value, killed
    by a check nobody could disable. What makes a string an expression is a measurement
    sitting next to an operator *and a number*, or two measurements combined. That is what is
    tested here, and `test_a118_a_value_that_merely_contains_a_measurement_name_still_loads`
    is the negative that keeps it honest.
    """
    if not isinstance(then, str):
        return None
    named = [m for m in measurement_ids if re.search(rf"\b{re.escape(m)}\b", then)]
    if not named:
        return None
    for measurement in named:
        bounded = rf"\b{re.escape(measurement)}\b"
        if re.search(rf"{bounded}\s*[-+*/]\s*\d", then) or re.search(
            rf"\d\s*[-+*/]\s*{bounded}", then
        ):
            return measurement
    if len(named) > 1 and re.search(r"[-+*/]", then):
        return named[0]
    return None


def _fillers_by_role(registry: Registry) -> dict[str, list[str]]:
    """Which contracts fill each role, across the whole assembled registry.

    Derived rather than declared, because a role's fillers are a fact about the stack and a
    lab's overlay may add one. Computed once per load and threaded, so the answer cannot
    differ between the check that a role is filled and the check that its fillers declare a
    parameter — the two disagreeing is how `MD0308` would refuse a rule that was fine.
    """
    fillers: dict[str, list[str]] = {}
    for contract in registry.all():
        for role in contract.roles:
            fillers.setdefault(role, []).append(contract.id)
    return {role: sorted(ids) for role, ids in fillers.items()}


def _validate_target(
    target: DecisionTarget,
    path: Path,
    *,
    registry: Registry,
    fillers_by_role: dict[str, list[str]],
    seen: dict[str, str],
) -> None:
    """**Structural checks first, justification last.** Order is load-bearing here.

    An earlier arrangement ran the citation check first, so a rule naming a contract that
    fills no role was reported as *"this row needs a cite"* — a diagnostic pointing at the one
    part of the rule that was correct. A refusal has to name the thing that is wrong.
    """
    fillers = fillers_by_role.get(target.of, [])
    if not fillers:
        raise RuleValidationError(
            coded("MD0306", f"{path}, decision {target.key()}\n"
            f"  No contract in this stack fills role {target.of!r}, so this decision can\n"
            f"  never apply.\n"
            f"  Roles that are filled: {', '.join(sorted(fillers_by_role)) or '(none)'}")
        )

    if target.effect is Effect.PARAM:
        if target.name is None:
            raise RuleValidationError(
                coded("MD0307", f"{path}, decision {target.key()}\n"
                f"  A `param` effect decides a named parameter and this one names none.\n"
                f"  Write `decides: {{effect: param, of: {target.of}, name: <parameter>}}`.")
            )
        narrowed = target.when_implementation or fillers
        outside = sorted(set(target.when_implementation) - set(fillers))
        if outside:
            raise RuleValidationError(
                coded("MD0306", f"{path}, decision {target.key()}\n"
                f"  `when_implementation` names {', '.join(outside)}, which do not fill role\n"
                f"  {target.of!r}. Fillers of that role: {', '.join(fillers)}")
            )
        declared_by = {
            contract_id: {p.name for p in registry.get(contract_id).params}
            for contract_id in narrowed
        }
        missing = sorted(c for c, names in declared_by.items() if target.name not in names)
        if missing:
            raise RuleValidationError(
                coded("MD0308", f"{path}, decision {target.key()}\n"
                f"  {target.name!r} is not declared by {', '.join(missing)}, which can fill\n"
                f"  role {target.of!r}. The value would be dead whenever one of those wins.\n"
                f"  Narrow with `when_implementation:`, or decide a parameter they all\n"
                f"  declare.")
            )
    elif target.name is not None:
        raise RuleValidationError(
            coded("MD0307", f"{path}, decision {target.key()}\n"
            f"  A `{target.effect}` effect decides the role itself and carries no `name`.\n"
            f"  Drop `name:`, or make this a `param` effect.")
        )

    if target.key() in seen:
        raise RuleValidationError(
            coded("MD0309", f"{path}, decision {target.key()}\n"
            f"  Two decisions in the same layer both decide {target.key()!r}: this one and\n"
            f"  {seen[target.key()]}.\n"
            f"  A higher layer replaces a whole block by key, so one of these would silently\n"
            f"  displace the other rather than both applying. Audit A119.")
        )
    seen[target.key()] = str(path)


def _domain_of(
    target: DecisionTarget, registry: Registry, fillers_by_role: dict[str, list[str]]
) -> "ParamDomain | None":
    """The declared domain for this param, if **every** implementation agrees on one.

    Every rather than any, and unanimity rather than a merge. `MD0308` has already proved
    each of them declares the parameter; two of them declaring different domains for it is a
    registry defect, and quietly taking the first would decide which contract is right by
    load order. Returning `None` there falls back to the heuristic, which refuses less and
    invents nothing.
    """
    narrowed = target.when_implementation or fillers_by_role[target.of]
    domains = [
        param.domain
        for contract_id in narrowed
        for param in registry.get(contract_id).params
        if param.name == target.name
    ]
    if not domains or any(d is None for d in domains):
        return None
    first = domains[0]
    return first if all(d == first for d in domains) else None


def _validate_rows(
    decision: Decision,
    target: DecisionTarget,
    path: Path,
    *,
    registry: Registry,
    fillers_by_role: dict[str, list[str]],
    measurements: MeasurementRegistry,
) -> None:
    if target.effect is Effect.PARAM:
        domain = _domain_of(target, registry, fillers_by_role)
        for row in decision.rows:
            # A declared domain answers this by type check; `_computed_over` answers it by
            # heuristic. Both emit `MD0300` because both refuse the same thing — a `then` the
            # tool cannot receive — and one concern gets one code.
            if domain is not None:
                refusal = domain.refuse(target.name, row.then)
                if refusal is None:
                    continue
                raise RuleValidationError(
                    coded("MD0300", f"{path}, decision {target.key()}\n"
                    f"  {refusal}.\n"
                    f"  `then` is emitted verbatim — nothing between the rule table and\n"
                    f"  `nextflow.config` evaluates it, so the tool would receive\n"
                    f"  {row.then!r} exactly as written.")
                )
            over = _computed_over(row.then, measurements.ids())
            if over is None:
                continue
            raise RuleValidationError(
                coded("MD0300", f"{path}, decision {target.key()}\n"
                f"  `then: {row.then!r}` reads as an expression over {over!r}, and `then` is\n"
                f"  emitted verbatim — the tool would receive the string {row.then!r}.\n"
                f"  Write one row per range with a literal `then`. If the rule genuinely\n"
                f"  needs arithmetic, that is issue #39 and a format change, not a value.")
            )
    elif target.effect is Effect.IMPLEMENTATION:
        fillers = fillers_by_role[target.of]
        for row in decision.rows:
            contract_id = str(row.then)
            if contract_id not in fillers:
                known = (
                    "it is not in this stack"
                    if contract_id not in registry.contracts
                    else f"it fills {', '.join(registry.get(contract_id).roles) or 'no role'}"
                )
                raise RuleValidationError(
                    coded("MD0306", f"{path}, decision {target.key()}\n"
                    f"  {contract_id!r} does not fill role {target.of!r} — {known}.\n"
                    f"  Contracts that do: {', '.join(fillers)}")
                )
    elif target.effect is Effect.PRESENCE:
        for row in decision.rows:
            if row.then not in ("present", "absent"):
                raise RuleValidationError(
                    coded("MD0307", f"{path}, decision {target.key()}\n"
                    f"  `then: {row.then!r}` — a presence effect says `present` or `absent`\n"
                    f"  and nothing else. It is a claim about whether the step exists, which\n"
                    f"  is why it reads as English rather than as `then: null`.")
                )

    for index, row in enumerate(decision.rows):
        # Tier 2 is "a documented default exists", so its output is value **plus the
        # document**. A row testing no premise positively earns tier 2 by `tier_of_row`, and
        # a `because` alone states the value and asserts the document. A76 and A128 were both
        # that shape — one in a contract default, one in a rule — and this is the rule stated
        # once rather than the pair fixed twice.
        if tier_of_row(row.when) is Tier.CONVENTION and not (row.cite or decision.cite):
            raise RuleValidationError(
                coded("MD0313", f"{path}, decision {target.key()}, row {index}\n"
                f"  This row tests no premise positively, so it exits at tier 2 — a\n"
                f"  documented default. Tier 2 produces `value + citation` and this row has\n"
                f"  neither a row `cite` nor a block one.\n"
                f"  A `because` states the value; a `cite` is the document tier 2 claims.")
            )
        if not (row.because or row.cite or decision.because or decision.cite):
            raise RuleValidationError(
                coded("MD0301", f"{path}, decision {target.key()}, row {index}\n"
                f"  This row justifies nothing — no `because` and no `cite`, on the row or\n"
                f"  on the block. It fires at tier 3, whose review level is *advisory*, which\n"
                f"  means 'the machinery worked, check the premise'. A reader given no\n"
                f"  premise cannot. It also emitted a reason ending in a bare colon.\n"
                f"  Add `because:` saying why this answer, or `cite:` naming the evidence.")
            )

def _sole_premise(rows: Sequence[DecisionRow]) -> str | None:
    """The one fact every non-catch-all row tests, or `None` if there is not exactly one.

    Completeness over a **product** of domains is a different and much larger claim, and a
    check that half-computed it would refuse legitimate tables — which is worse than not
    checking, because the author cannot argue with a refusal nobody can explain. So a
    decision whose rows test two facts, or different facts, is not checked at all, and
    `test_rows_over_several_premises_are_not_checked_for_completeness` says so out loud.
    """
    tested = {fact for row in rows if row.when for fact in row.when}
    if len(tested) != 1:
        return None
    return tested.pop()

    # An earlier version read `if len(tested) != 1 or any(len(row.when) > 1 for row in rows)`.
    # The second clause cannot be true when the first is false: a row with two keys puts two
    # facts in `tested`, so `len(tested) != 1` already catches it. Reverting it changed
    # nothing, which is how it was found — same shape as `stack()`'s `origin[key] !=
    # layer.index` in Plan 1.9. Deleted rather than kept as reassurance, because an
    # unreachable condition reads to the next person as a case somebody thought about.


def _uncovered_interval(rows: Sequence[DecisionRow]) -> str | None:
    """What an ordered domain's rows leave out, or `None` if they cover the line.

    `>= x` and `< x` are complementary **by construction**, so a pair at the same boundary is
    exhaustive with no bound declared anywhere. That is the whole point of checking this way:
    A124 asks for completeness and the obvious fix — demand a catch-all — would demote the
    shipped aligner rule's last branch from tier 3 to tier 2 and take Kim et al. with it.

    Overlaps are legal and are not gaps. `>= 50` beside `< 70` covers the line twice between
    50 and 70, and first-match-wins already settles which row applies; refusing it would be
    enforcing a different property under completeness' name.
    """
    lower: list[float] = []   # `>= x` / `> x`: covers upward from x
    upper: list[float] = []   # `<= x` / `< x`: covers downward from x
    for row in rows:
        if not row.when:
            return None  # a catch-all covers everything that is left
        expected = next(iter(row.when.values()))
        comparison = _comparison(expected)
        if comparison is None:
            return None  # an equality test over an ordered kind: not a partition claim
        symbol, literal = comparison
        (lower if symbol in (">=", ">") else upper).append(literal)
    if not lower and not upper:
        return None
    if not upper:
        return f"everything below {min(lower):g}"
    if not lower:
        return f"everything from {max(upper):g} upwards"
    highest_covered_below, lowest_covered_above = max(upper), min(lower)
    if lowest_covered_above <= highest_covered_below:
        return None
    return f"between {highest_covered_below:g} and {lowest_covered_above:g}"


def _uncovered_values(rows: Sequence[DecisionRow], measurement) -> str | None:
    """Which of an enum's values no row matches, or `None` if the rows cover them all."""
    if any(not row.when for row in rows):
        return None
    covered = {next(iter(row.when.values())) for row in rows}
    missing = [value for value in measurement.values if value not in covered]
    return ", ".join(missing) if missing else None


def _check_exhaustive(
    decision: Decision, where: str, *, measurements: MeasurementRegistry
) -> None:
    """Every value the premise can take is answered by some row. A124.

    Refused rather than warned, because a rule with a hole does not fail — it *demotes*. The
    premise falls through every row, no rule matches, and the decision exits at tier 4 with
    "no rule matched" beside it. A reviewer reads that as an ambiguity the registry has not
    got to yet, when what it means is that somebody wrote three branches of a four-branch
    table and nothing said so.
    """
    fact = _sole_premise(decision.rows)
    if fact is None or fact not in measurements.ids():
        return
    measurement = measurements.get(fact)
    if measurement.kind in _ORDERED:
        gap = _uncovered_interval(decision.rows)
        if gap is None:
            return
        raise RuleValidationError(
            coded("MD0311", f"{where}\n"
            f"  The rows over {fact!r} leave {gap} uncovered, so a profile there matches\n"
            f"  nothing and the decision silently demotes to tier 4.\n"
            f"  Two complementary comparisons at one boundary — `>= 70` and `< 70` — are\n"
            f"  exhaustive without any bound being declared. A catch-all `when: {{}}` also\n"
            f"  works, but exits at tier 2 and needs a `cite:`.")
        )
    if measurement.kind is not MeasurementKind.ENUM:
        return
    missing = _uncovered_values(decision.rows, measurement)
    if measurement.extensible:
        if any(not row.when for row in decision.rows):
            return
        raise RuleValidationError(
            coded("MD0311", f"{where}\n"
            f"  {fact!r} is declared `extensible: true`, so an overlay may add a value and\n"
            f"  coverage today is not coverage tomorrow. Add a catch-all `when: {{}}` row\n"
            f"  with a `cite:` — it exits at tier 2, which is what a default is.")
        )
    if missing:
        raise RuleValidationError(
            coded("MD0311", f"{where}\n"
            f"  No row matches {fact} = {missing}, so a profile carrying one matches nothing\n"
            f"  and the decision silently demotes to tier 4.\n"
            f"  {fact!r} declares {len(measurement.values)} values and is not extensible, so\n"
            f"  covering them all is exhaustive and needs no catch-all.")
        )


def _validate(
    decision: Decision,
    path: Path,
    *,
    registry: Registry,
    fillers_by_role: dict[str, list[str]],
    measurements: MeasurementRegistry,
    seen: dict[str, str],
) -> None:
    # Every target, not only the first. A validator that loops over `decides` incorrectly
    # still passes every single-target test there is, which is why `test_both_targets_of_one
    # _decision_are_validated` exists and why it names that in its docstring.
    for target in decision.targets():
        _validate_target(
            target,
            path,
            registry=registry,
            fillers_by_role=fillers_by_role,
            seen=seen,
        )
        _validate_rows(
            decision,
            target,
            path,
            registry=registry,
            fillers_by_role=fillers_by_role,
            measurements=measurements,
        )


def _check_when(
    rows: Sequence[DecisionRow],
    where: str,
    *,
    measurements: MeasurementRegistry,
    facts: set[str],
) -> None:
    """Every `when` key names a premise something can supply, and reads it sensibly.

    Run **after the stack is assembled** rather than inside `parse`, for the same reason
    `roles.check` runs after the registry is: a derivation and the decision reading it may
    sit in different files, and a check that fires per file would refuse a legitimate rule
    for the accident of which one `stack()` reached first.

    `when` sees more than measurements now — that is A120, and the whole point of the premise
    layer. So the message names all three sources rather than only the one it used to know
    about, which is what made the old diagnostic misleading rather than merely incomplete.
    """
    derived = sorted(facts - set(measurements.ids()) - _GOAL_FACTS)
    for row in rows:
        for fact, expected in row.when.items():
            if fact not in facts:
                raise RuleValidationError(
                    coded("MD0310", f"{where}\n"
                    f"  {fact!r} is not a premise anything supplies, so this row can never\n"
                    f"  fire.\n"
                    f"  Declared measurements: {', '.join(measurements.ids()) or '(none)'}\n"
                    f"  Derived facts: {', '.join(derived) or '(none)'}\n"
                    f"  Goal facts: {', '.join(sorted(_GOAL_FACTS))}")
                )
            if expected in ("absent", "present") or fact not in measurements.ids():
                continue
            measurement = measurements.get(fact)
            if _comparison(expected) is not None and measurement.kind not in _ORDERED:
                raise RuleValidationError(
                    coded("MD0310", f"{where}\n"
                    f"  {fact!r} is an {measurement.kind}, so it can only be compared with\n"
                    f"  equality, `in` or `not` — never {expected!r}.")
                )
