"""What a contract field affects, what can check it, and what a change to one means.

**Two checkers ask whether the registry still agrees with its sources.** `ops.check` compares
the three values a source states outright; `mendel_compiler.conformance` compares the
contract's structure to the module and emits MD0101–MD0108. They overlap on `nf_process` and
`container`. Spec §3.1 decided not to merge them — they have different callers and different
obligations, and one of them must be able to refuse a build — so what is declared here instead
is the coverage, in one place, with a totality test on each half.

**The verdict is a fold over this table and never a case analysis.**
`notes/specs/2026-08-18-plan-3.md` §4.7 asked for exactly that, for a stated reason: a verdict
written per case is wrong the first time a field is added, and wrong silently.
"""

from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Impact(StrEnum):
    """What reads this field — which is what decides how much a change to it matters."""

    ROUTES = "routes"
    """The resolver reads it: which contract is chosen, and how the graph connects."""
    BUILDS = "builds"
    """The compiler reads it: what the emitted Nextflow contains and what runs."""
    RECORDS = "records"
    """Nothing reads it at build time. It is provenance for a human."""

    @property
    def rank(self) -> int:
        """Worst first.

        **Declared rather than derived from the member order**, the same argument as
        `Band.rank`: this is a `StrEnum`, so `sorted()` compares the strings and would put
        `builds` above `records` above `routes` — alphabetical order reading as consequence.
        That shipped once, in the queue.
        """
        return {Impact.ROUTES: 1, Impact.BUILDS: 2, Impact.RECORDS: 3}[self]


class Verdict(StrEnum):
    """The only question a maintainer really has, answered — design §7."""

    BREAKS = "breaks"
    """A conformance check refuses: a pipeline pinning this contract cannot be emitted."""
    REROUTES = "reroutes"
    REBUILDS = "rebuilds"
    RECORDED = "recorded"
    """Only fields nothing reads at build time moved. Unreachable today, and total anyway."""
    AGREES = "agrees"


class FieldFacts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    impact: Impact
    read_by: str
    """Where it is read, so the classification can be checked rather than believed."""
    by_value: bool = False
    """A source states this field outright — `assemble.DERIVED_FIELDS`."""
    codes: tuple[str, ...] = ()
    """The conformance diagnostics that speak to it."""

    @property
    def checked(self) -> bool:
        return self.by_value or bool(self.codes)


FIELDS: dict[str, FieldFacts] = {
    "id": FieldFacts(
        impact=Impact.ROUTES,
        read_by="layered.py — a higher layer displaces on the module key; router.py orders on id",
    ),
    "nf_process": FieldFacts(
        impact=Impact.BUILDS,
        read_by="emit.py — `process <name>` and `include { <name> }`",
        by_value=True,
        codes=("MD0101",),
    ),
    "nf_include": FieldFacts(
        impact=Impact.BUILDS,
        read_by="emit.py — the include path",
        by_value=True,
    ),
    "consumes": FieldFacts(
        impact=Impact.ROUTES,
        read_by="router.py — a candidate's requirements; resolve.py — the edges",
    ),
    "produces": FieldFacts(
        impact=Impact.ROUTES,
        read_by="router.py — `producers_of`; emit.py — `PROCESS.out.<name>`",
        codes=("MD0105",),
    ),
    "params": FieldFacts(
        impact=Impact.BUILDS,
        read_by="resolve.py — what there is to settle; emit.py — where a value goes",
        codes=("MD0108",),
    ),
    "roles": FieldFacts(
        impact=Impact.ROUTES,
        read_by="router.py — what a tier-3 rule targets, and the only thing it may",
    ),
    "priority": FieldFacts(
        impact=Impact.ROUTES,
        read_by="router.py — `(surplus, -priority, id)`",
    ),
    "priority_because": FieldFacts(
        impact=Impact.RECORDS,
        read_by="the artifact's `axis_reason` — read by a person, never by a decision",
    ),
    "container": FieldFacts(
        impact=Impact.BUILDS,
        read_by="emit.py — the container directive; what actually runs",
        by_value=True,
        codes=("MD0107",),
    ),
    "nf_inputs": FieldFacts(
        impact=Impact.BUILDS,
        read_by="emit.py — the process call signature, which Nextflow matches by arity",
        codes=("MD0102", "MD0103", "MD0104"),
    ),
    "ext_args": FieldFacts(
        impact=Impact.BUILDS,
        read_by="emit.py — `withName: … { ext.args = … }`",
        codes=("MD0108",),
    ),
    "provenance": FieldFacts(
        impact=Impact.RECORDS,
        read_by="a reviewer — who approved this contract, and when",
    ),
}

NOT_A_FIELD: dict[str, str] = {
    "MD0100": "the module source is absent — about the module, not about a field",
    "MD0106": (
        "registry-wide: emitted by conformance.check() over the measurement vocabulary, and its"
        " `where` may name a measurement rather than a contract. against() never emits it."
    ),
}
"""Conformance codes that are not about a field of `ModuleContract`, with the reason.

Declared rather than allowed to fall through the totality test, because *"it is not in the
table"* and *"it does not belong in the table"* look identical to a test and completely
different to a reader.
"""

_FOR_IMPACT = {
    Impact.ROUTES: Verdict.REROUTES,
    Impact.BUILDS: Verdict.REBUILDS,
    Impact.RECORDS: Verdict.RECORDED,
}


def field_for(code: str) -> str | None:
    """Which field a conformance diagnostic is about, or `None` when it is about no field.

    The first match, and MD0108 is the reason that is a decision rather than an accident: it
    speaks to `params` and to `ext_args`, and a drift row needs one field to name. `FIELDS`
    is ordered as `ModuleContract` declares its fields, so the answer is stable.
    """
    for field, facts in FIELDS.items():
        if code in facts.codes:
            return field
    return None


def verdict_for(*, disagreeing: Iterable[str], refusing: Iterable[str]) -> Verdict:
    """The worst thing that is true, and nothing softer.

    `refusing` is diagnostic codes from a conformance run that refuse; `disagreeing` is field
    names. A refusal outranks every field because it is not a question of what would route
    differently — the contract can no longer be emitted at all.
    """
    if list(refusing):
        return Verdict.BREAKS
    impacts = sorted((FIELDS[field].impact for field in disagreeing), key=lambda i: i.rank)
    return _FOR_IMPACT[impacts[0]] if impacts else Verdict.AGREES


def sentence_for(verdict: Verdict, *, disagreeing: Iterable[str], refusing: Iterable[str]) -> str:
    """The verdict block's one sentence, naming the fields it is about.

    Specific to the change in front of you rather than generic — design §7: a container bump
    and a `type_id` change are wildly different events and the screen must say which this is.
    """
    fields = ", ".join(sorted(disagreeing))
    codes = ", ".join(sorted(refusing))
    if verdict is Verdict.BREAKS:
        return (
            f"This contract no longer describes its module ({codes}). A pipeline that pins it"
            " cannot be emitted until the disagreement is settled."
        )
    if verdict is Verdict.REROUTES:
        return (
            f"Routing can change. {fields} is read by the router, so a pipeline that resolved"
            " to this contract may now resolve to another."
        )
    if verdict is Verdict.REBUILDS:
        return (
            f"Nothing routes differently — {fields} is not read by the router, so every"
            " pipeline that resolved to this contract still resolves to it. What runs changes."
        )
    if verdict is Verdict.RECORDED:
        return f"{fields} moved, and nothing reads it at build time."
    return "The registry says what its source says, on every field anything can check."
