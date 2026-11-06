"""What a contract allows for one setup (#460): missing, forbidden, produced, and why.

A **setup** is which inputs are connected and which params hold which values. Constraints are
facts about the tool; this module only reads them. Choosing what to connect is a decision (a
person's, a model's flagged, or a rule's, #461) and is never made here.

An input whose presence is only known per run (an optional pipeline input that each run may
leave empty) is **unknown**. The verdict then considers every combination of the unknown
inputs. A row violated in all of them cannot be avoided, so it is a build-time refusal; a row
violated in some is left for the run to settle, and its sentence is in `holds_at_run_time`.
"""

from collections.abc import Iterator
from itertools import combinations, product
from math import prod
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.declared.contract import ConstraintRow, GroupKind, ModuleContract, Param
from comeni_core.declared.measurement import MeasurementKind
from comeni_core.diagnostics import coded
from comeni_core.logic.when import PRESENT, matches


class Setup(BaseModel):
    model_config = ConfigDict(frozen=True)

    given: frozenset[str] = frozenset()
    """The inputs connected."""
    params: dict[str, Any] = Field(default_factory=dict)
    """Each param's resolved value. A missing key, or `None`, is no value."""
    unknown: frozenset[str] = frozenset()
    """Inputs each run may supply or leave empty."""


class Verdict(BaseModel):
    missing: list[str] = Field(default_factory=list)
    """Inputs or params that must be given and are not; `one of a, b` for an unmet group."""
    forbidden: list[str] = Field(default_factory=list)
    produced: list[str] = Field(default_factory=list)
    """Outputs written in every run this setup allows."""
    sentences: list[str] = Field(default_factory=list)
    """One per row whose condition holds, in declaration order."""
    holds_at_run_time: list[str] = Field(default_factory=list)
    """Rows that only the run can settle, because they depend on an unknown input."""


class _Value(NamedTuple):
    value: Any


def _key(contract: ModuleContract, name: str) -> str:
    return f"param.{name}" if name in {p.name for p in contract.params} else f"given.{name}"


def rows_of(contract: ModuleContract) -> list[ConstraintRow]:
    """The explicit rows, then each group as rows. `one_of` and `any_of` also need one member
    given; that part is not a row (a row cannot say *one of*), and `evaluate` checks it."""
    rows = list(contract.constraints)
    for group in contract.groups:
        if group.kind is GroupKind.ALL_OR_NONE:
            for member in group.members:
                rows.append(ConstraintRow(
                    when={_key(contract, member): PRESENT, **group.when},
                    requires=[m for m in group.members if m != member], because=group.because))
        elif group.kind is GroupKind.ONE_OF:
            for first, second in combinations(group.members, 2):
                rows.append(ConstraintRow(
                    when={_key(contract, first): PRESENT, **group.when},
                    forbids=[second], because=group.because))
    return rows


def _subject(row: ConstraintRow) -> str:
    names = [key.partition(".")[2] for key in row.when]
    return names[0] if names else ""


def sentence(row: ConstraintRow) -> str:
    """The row as a person reads it. Exact copy is part of the design (#460, §2)."""
    subject = _subject(row)
    if row.requires:
        needed = ", ".join(row.requires)
        if not subject:
            return f"`{needed}` is required ({row.because})"
        return f"`{subject}` is used only with `{needed}` ({row.because})"
    banned = ", ".join(row.forbids)
    if not subject:
        return f"`{banned}` cannot be used ({row.because})"
    return f"`{subject}` cannot be used with `{banned}` ({row.because})"


def _worlds(setup: Setup) -> Iterator[frozenset[str]]:
    unknown = sorted(setup.unknown)
    for size in range(len(unknown) + 1):
        for chosen in combinations(unknown, size):
            yield setup.given | frozenset(chosen)


def _facts(given: frozenset[str], params: dict[str, Any]) -> dict[str, _Value]:
    facts = {f"given.{port}": _Value(True) for port in given}
    facts.update({f"param.{name}": _Value(v) for name, v in params.items() if v is not None})
    return facts


def _has(name: str, given: frozenset[str], params: dict[str, Any]) -> bool:
    return name in given or params.get(name) is not None


def evaluate(contract: ModuleContract, setup: Setup) -> Verdict:
    worlds = list(_worlds(setup))
    verdict = Verdict()

    def add(target: list[str], items: list[str]) -> None:
        target.extend(i for i in items if i not in target)

    add(verdict.missing, [p.name for p in contract.consumes
                          if p.required and p.name not in setup.given])
    for row in rows_of(contract):
        broken = []
        applies = False
        for given in worlds:
            if not matches(row.when, _facts(given, setup.params)):
                broken.append(False)
                continue
            applies = True
            lacking = [n for n in row.requires if not _has(n, given, setup.params)]
            present = [n for n in row.forbids if _has(n, given, setup.params)]
            broken.append(bool(lacking or present))
        if not applies:
            continue
        said = sentence(row)
        add(verdict.sentences, [said])
        if all(broken):
            add(verdict.missing,
                [n for n in row.requires if not _has(n, setup.given, setup.params)])
            add(verdict.forbidden, [n for n in row.forbids if _has(n, setup.given, setup.params)])
        elif any(broken):
            add(verdict.holds_at_run_time, [said])
    for group in contract.groups:
        if group.kind is GroupKind.ALL_OR_NONE:
            continue
        if not matches(group.when, _facts(setup.given, setup.params)):
            continue
        if not any(_has(m, setup.given | setup.unknown, setup.params) for m in group.members):
            add(verdict.missing, [f"one of {', '.join(group.members)}"])
    for output in contract.produces:
        when = output.produced_when
        if when is None or all(matches(when, _facts(g, setup.params)) for g in worlds):
            verdict.produced.append(output.name)
    return verdict


SETUP_BOUND = 4096
"""The most setups `check_constraints` tries. Beyond it the contract is refused (MD0607), so a
check never reports clean over cases it did not try."""


def _literals(expected: Any) -> list[Any]:
    """The values a condition compares against: `{in: [...]}`, `{not: x}`, `"< 70"`, or a
    plain value."""
    if isinstance(expected, dict):
        if "in" in expected:
            return list(expected["in"])
        return [expected.get("not")]
    if isinstance(expected, str):
        symbol, _, literal = expected.partition(" ")
        if symbol in {">=", ">", "<=", "<", "==", "!="}:
            try:
                number = float(literal)
            except ValueError:
                return [literal]
            whole = int(number) if number.is_integer() else number
            return [whole - 1, whole, whole + 1]
        if expected in {"present", "absent"}:
            return []
    return [expected]


def _values(param: Param, compared: list[Any]) -> list[Any]:
    """Every value worth trying for one param: its domain, or what conditions compare it to.
    A param with a default always has a value; one without may have none."""
    domain = param.domain
    if domain is not None and domain.kind is MeasurementKind.BOOLEAN:
        values: list[Any] = [True, False]
    elif domain is not None and domain.kind is MeasurementKind.ENUM and domain.values:
        values = list(domain.values)
    else:
        values = list(dict.fromkeys(compared)) or [param.default]
    if param.default is None:
        values = [None, *(v for v in values if v is not None)]
    return values


def _conditions(contract: ModuleContract) -> list[dict[str, Any]]:
    whens = [row.when for row in rows_of(contract)] + [g.when for g in contract.groups]
    return whens + [o.produced_when for o in contract.produces if o.produced_when]


def check_constraints(contract: ModuleContract) -> list[str]:
    """Findings, each a coded message: MD0603 no valid setup, MD0604 a dead optional input,
    MD0605 a fake optional one, MD0606 an output never produced, MD0607 too many setups."""
    optional = contract.optional_ports()
    required = frozenset(p.name for p in contract.consumes if p.required)
    compared: dict[str, list[Any]] = {}
    for when in _conditions(contract):
        for key, expected in when.items():
            space, _, name = key.partition(".")
            if space == "param":
                compared.setdefault(name, []).extend(_literals(expected))
    params = [p for p in contract.params if p.name in compared]
    choices = [_values(p, compared[p.name]) for p in params]
    count = 2 ** len(optional) * prod(len(c) for c in choices)
    if count > SETUP_BOUND:
        return [coded("MD0607", f"{contract.id} has {count} setups to check, above "
                      f"{SETUP_BOUND}: fewer optional inputs or conditioned params")]
    valid: list[tuple[frozenset[str], Verdict]] = []
    for size in range(len(optional) + 1):
        for chosen in combinations(optional, size):
            given = required | frozenset(chosen)
            for values in product(*choices):
                setup = Setup(given=given, params=dict(zip([p.name for p in params], values,
                                                           strict=True)))
                verdict = evaluate(contract, setup)
                if not verdict.missing and not verdict.forbidden:
                    valid.append((given, verdict))
    if not valid:
        return [coded("MD0603", f"{contract.id}: no combination of inputs and params satisfies "
                      "its constraints, so the tool can never run")]
    findings = []
    for port in optional:
        used = [port in given for given, _ in valid]
        if not any(used):
            findings.append(coded("MD0604", f"{contract.id}: optional input {port!r} is "
                                  "connected in no combination its constraints allow"))
        elif all(used):
            findings.append(coded("MD0605", f"{contract.id}: optional input {port!r} is "
                                  "connected in every combination its constraints allow, so "
                                  "it is required"))
    for output in contract.produces:
        if output.produced_when and not any(output.name in v.produced for _, v in valid):
            findings.append(coded("MD0606", f"{contract.id}: output {output.name!r} is "
                                  "produced in no combination its constraints allow"))
    return findings
