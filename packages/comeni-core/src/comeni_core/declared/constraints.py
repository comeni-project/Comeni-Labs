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
from itertools import combinations
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.declared.contract import ConstraintRow, GroupKind, ModuleContract
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
