"""One fact a decision rested on, as the artifact records it.

Its own module because both `ir.py` and `pipeline.py` need it and `pipeline.py` imports `ir`,
so neither of those can be its home without a cycle. Same shape as `profile.py`, which was
split out for the same reason and says so.

`PremiseOrigin` lives in `comeni_core.plan.tiers` beside `ValueSource` — it is a vocabulary about
evidence, and the two answer different questions about the same value.
"""

from pydantic import BaseModel, ConfigDict

from comeni_core.plan.tiers import PremiseOrigin
from comeni_core.spell.marks import MeasurementId, ParamValue


class PremiseRecord(BaseModel):
    """One fact a decision rested on, and how good that fact is.

    A **list of records**, not two parallel mappings. The plan drafted `premise:
    dict[str, Any]` beside `premise_origin: dict[str, str]`, and `tests/test_egress.py`
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

    def prose(self) -> str:
        """`read_length is 150, measured` — the sentence, not the mapping.

        Spec §6.1: no structured value is a reader's only account of itself. The **value**
        comes first because it is what a reviewer checks against the sample sheet; the
        **origin** second because it is what tells them whether checking is worth the time.
        """
        return f"{self.id} is {self.value}, {_ORIGIN_PROSE[self.origin]}"

_ORIGIN_PROSE = {
    PremiseOrigin.MEASURED: "measured",
    PremiseOrigin.ASSERTED: "asserted, not measured",
    PremiseOrigin.GOAL: "declared in the goal",
    PremiseOrigin.DERIVED: "inferred — nothing measured it",
    PremiseOrigin.UNMEASURED: "not measured",
}
"""Total over `PremiseOrigin` and read with `[]`, so a sixth member forces somebody to write
its sentence rather than defaulting into silence. A38's tripwire, in a third place."""
