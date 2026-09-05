"""Scoring one proposal against a contract that is already landed and known to be right.

§5.9's method: take a tool whose contract a human already approved, hide that contract from the
context, adapt the upstream source as if for the first time, and compare. It is the only way to
measure a prompt without a person reading every answer, and the registry is the only place a
known-good answer exists.

**Precision and coverage are reported together and neither means anything alone.** A model that
declines every hole has perfect precision; a model that guesses every hole has perfect coverage.
§5.9's last row — *unresolved weak-source case: expected, not failure* — is only expressible if
declining is scored as neither right nor wrong, and that is exactly the arrangement that makes
a single number a lie. `Score.summary()` refuses to print one without the other.

**Nothing here calls a model.** A `Proposal` comes in and a `Score` comes out, so the same
scoring runs over a recorded response in CI and over a live Ollama answer locally, and the two
are comparable because they went through the same arithmetic.
"""

from collections.abc import Mapping, Sequence

from comeni_core.declared.contract import ModuleContract
from pydantic import BaseModel, ConfigDict

from mendel_forge.ai.schemas import Proposal
from mendel_forge.hole_manifest import ScaffoldHole

_FROZEN = ConfigDict(extra="forbid", frozen=True)


def expected_from(contract: ModuleContract) -> dict[str, str]:
    """A landed contract projected onto the hole ids a scaffold would open for it.

    **Matched by channel name, not by position.** That is the whole reason Task 5 made hole ids
    semantic: the upstream module may have gained a port since the contract landed, and a
    positional comparison would then score every port after it as wrong. A port the scaffold
    opens and the contract does not have is simply absent here, and `Score.unknown` counts it.
    """
    expected: dict[str, str] = {}
    for group, ports in (("consumes", contract.consumes), ("produces", contract.produces)):
        for port in ports:
            name = getattr(port, "name", None) or getattr(port, "type_id", "")
            slug = _slug(str(name))
            expected[f"{group}.{slug}.type_id"] = str(port.type_id)
            if getattr(port, "name", None):
                expected[f"{group}.{slug}.name"] = str(port.name)
    if contract.roles:
        expected["roles"] = str(contract.roles[0])
    return expected


def _slug(text: str) -> str:
    """The same transformation `hole_manifest.slug` applies, and it must stay the same one.

    Imported rather than reimplemented would be better; it is spelled out here only because a
    circular import would otherwise run `hole_manifest` -> `ai` -> `hole_manifest`. If a third
    caller appears, move it.
    """
    from mendel_forge.hole_manifest import slug

    return slug(text)


class Score(BaseModel):
    """What one proposal got right, wrong, and honestly declined.

    Counts rather than a verdict. §5.9's table has nine rows with different gates — some are
    *must be zero*, one is *report per port*, and one is *expected, not failure* — and
    collapsing them into a pass mark would hide exactly the row that was moving.
    """

    model_config = _FROZEN

    case: str
    correct: int = 0
    wrong: int = 0
    declined: int = 0
    """Answered as an unresolved item. **Neither right nor wrong**, which is what makes the
    weak-source case expressible at all."""
    missing: int = 0
    """Neither answered nor declined. This one *is* a failure — a hole the model forgot is not
    a hole the model refused, and `owed()` is where the difference is drawn."""
    unknown: int = 0
    """Answered, but the landed contract has no value for that hole to be compared against.
    Not wrong: the upstream module may have gained a port since the contract landed."""
    invented_citations: tuple[str, ...] = ()
    """§5.9 gates this at zero. Populated only when `admit()` was bypassed — the live path
    raises `MF0401` before a proposal ever reaches scoring, so a non-empty tuple here means the
    harness ran without the gate and the number is the measurement of what would have got
    through."""
    outside_candidates: tuple[str, ...] = ()
    """Same: `MF0403` refuses these on the live path."""
    mutated_facts: tuple[str, ...] = ()
    """§5.9's *source fact mutation: 0*. A proposal that answers a hole the scaffold had already
    settled from the source is claiming to know better than the thing it was reading."""
    schema_valid: bool = True
    repairs_used: int = 0

    def answered(self) -> int:
        return self.correct + self.wrong + self.unknown

    def precision(self) -> float | None:
        """Of the holes it answered and could be checked, how many were right.

        `None` rather than 1.0 when it answered nothing checkable — a model that declined
        everything has not achieved perfect precision, it has not been measured.
        """
        judged = self.correct + self.wrong
        return None if judged == 0 else self.correct / judged

    def coverage(self) -> float | None:
        """Of the holes it was asked, how many it answered at all."""
        asked = self.answered() + self.declined + self.missing
        return None if asked == 0 else self.answered() / asked

    def summary(self) -> str:
        """Both numbers, always, and the counts behind them.

        **There is no single-number form of this on purpose.** Either metric alone is trivially
        gamed by the opposite failure, and a report that prints one is a report that will be
        quoted.
        """
        precision = self.precision()
        coverage = self.coverage()
        return (
            f"{self.case}: "
            f"precision {'—' if precision is None else f'{precision:.0%}'} "
            f"({self.correct}/{self.correct + self.wrong}), "
            f"coverage {'—' if coverage is None else f'{coverage:.0%}'}, "
            f"declined {self.declined}, missing {self.missing}, "
            f"repairs {self.repairs_used}"
        )


def score(
    proposal: Proposal,
    *,
    case: str,
    expected: Mapping[str, str],
    holes: Sequence[ScaffoldHole],
    evidence_ids: frozenset[str] = frozenset(),
    settled: Mapping[str, str] | None = None,
    repairs_used: int = 0,
) -> Score:
    """Compare a proposal with the known answer, counting rather than judging."""
    answers = {a.hole_id: a.value for a in proposal.analysis.answers}
    declined = {u.hole_id for u in proposal.analysis.unresolved}
    required = {hole.id for hole in holes if hole.required}
    by_id = {hole.id: hole for hole in holes}

    correct = wrong = unknown = 0
    for hole_id, value in answers.items():
        if hole_id not in expected:
            unknown += 1
        elif expected[hole_id] == value:
            correct += 1
        else:
            wrong += 1

    outside = tuple(
        sorted(
            hole_id
            for hole_id, value in answers.items()
            if (hole := by_id.get(hole_id))
            and hole.exhaustive
            and hole.legal_values
            and value not in hole.legal_values
        )
    )

    return Score(
        case=case,
        correct=correct,
        wrong=wrong,
        declined=len(declined),
        missing=len(required - set(answers) - declined),
        unknown=unknown,
        invented_citations=tuple(sorted(proposal.analysis.cited() - evidence_ids)),
        outside_candidates=outside,
        mutated_facts=tuple(sorted(set(answers) & set(settled or {}))),
        repairs_used=repairs_used,
    )


class Report(BaseModel):
    """Every case in one run, with the gates §5.9 states.

    A run is reported whole rather than case by case, because the interesting movement is
    across cases: a prompt change that helps `fastqc` and hurts `star/align` is a prompt change
    that should not land, and neither case alone says so.
    """

    model_config = _FROZEN

    model: str
    scores: tuple[Score, ...] = ()

    def failures(self) -> tuple[str, ...]:
        """The rows §5.9 gates at zero, as sentences.

        Precision is deliberately not here. It is a *report per port* row with a floor of *must
        not regress the current measured baseline*, and there is no baseline yet — asserting a
        number nobody has measured would be inventing the thing this harness exists to find.
        """
        found = []
        for entry in self.scores:
            if not entry.schema_valid:
                found.append(f"{entry.case}: no valid response after {entry.repairs_used} repairs")
            for citation in entry.invented_citations:
                found.append(f"{entry.case}: cited {citation}, which is not in the dossier")
            for hole_id in entry.outside_candidates:
                found.append(f"{entry.case}: answered {hole_id} outside its candidate set")
            for fact in entry.mutated_facts:
                found.append(f"{entry.case}: overwrote {fact}, which the source had settled")
        return tuple(found)

    def render(self) -> str:
        lines = [f"model: {self.model}", ""]
        lines.extend(entry.summary() for entry in self.scores)
        if failures := self.failures():
            lines.extend(["", "GATE FAILURES — §5.9 puts these at zero:"])
            lines.extend(f"  {failure}" for failure in failures)
        else:
            lines.extend(["", "every zero-gate row is at zero"])
        return "\n".join(lines) + "\n"
