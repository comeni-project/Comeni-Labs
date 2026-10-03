"""One fact a decision rested on, as the artifact records it.

Its own module because both `ir.py` and `pipeline.py` need it and `pipeline.py` imports `ir`,
so neither of those can be its home without a cycle. Same shape as `profile.py`, which was
split out for the same reason and says so.

`PremiseOrigin` lives in `comeni_core.plan.tiers` beside `ValueSource` — it is a vocabulary about
evidence, and the two answer different questions about the same value.
"""

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.plan.tiers import PremiseOrigin
from comeni_core.spell.marks import ContractId, MeasurementId, ParamValue, PieceRef


class PremiseRecord(BaseModel):
    """One fact a decision rested on, and how good that fact is.

    A **list of records**, not two parallel mappings. The plan drafted `premise:
    dict[str, Any]` beside `premise_origin: dict[str, str]`, and `tests/guards/test_egress.py`
    refused it three ways at once — a mapping, an `Any`, and a bare `str` key — because `Why`
    is reachable from door 4, publication, the door with no undo.

    Being forced into a record is the better shape anyway: two parallel mappings can disagree
    about their key sets and nothing would notice, and the guard's own message says why the
    list is the house style — *"a typed key does not prove a declared key"*.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: MeasurementId
    value: ParamValue | list[ParamValue]
    origin: PremiseOrigin
    by: ContractId | None = Field(default=None, exclude_if=lambda by: by is None)
    """The profiler's contract that measured it, when one did."""
    pieces: list[PieceRef] = Field(default_factory=list, exclude_if=lambda pieces: not pieces)
    """The inspector pieces that measured it, when they did (issue 233). Both are left out of
    the dump when empty, so a record nothing measured reads and serialises as before."""

    def prose(self) -> str:
        """`read_length is 101, measured by fastq@1.0.0 + read_length@1.0.0` — the sentence.

        Spec §6.1: no structured value is a reader's only account of itself. The **value**
        comes first because it is what a reviewer checks against the sample sheet; the
        **origin** second because it is what tells them whether checking is worth the time;
        and **what measured it**, when something did, because a tier-3 decision asks the
        reader to check its premise, and that says what to check (issue 233, decided A).
        """
        said = f"{self.id} is {self.value}, {_ORIGIN_PROSE[self.origin]}"
        measurer = " + ".join(self.pieces) if self.pieces else self.by
        if measurer and self.origin is PremiseOrigin.MEASURED:
            return f"{said} by {measurer}"
        return said

_ORIGIN_PROSE = {
    PremiseOrigin.MEASURED: "measured",
    PremiseOrigin.ASSERTED: "asserted, not measured",
    PremiseOrigin.GOAL: "declared in the goal",
    PremiseOrigin.DERIVED: "inferred — nothing measured it",
    PremiseOrigin.UNMEASURED: "not measured",
}
"""Total over `PremiseOrigin` and read with `[]`, so a sixth member forces somebody to write
its sentence rather than defaulting into silence. A38's tripwire, in a third place."""
