"""Serializable facts and provenance used to explain a decision.

The model is independent of both intermediate and published pipeline representations so they can
share it without an import cycle. ``PremiseOrigin`` describes evidence quality, while
``ValueSource`` describes who supplied a value.
"""

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.plan.tiers import Coverage, PremiseOrigin
from comeni_core.spell.marks import ContractId, MeasurementId, ParamValue, PieceRef


class PremiseRecord(BaseModel):
    """One fact used by a decision, including its evidence quality and measurer.

    Keeping the value and origin in one record prevents the mismatched key sets possible with
    parallel mappings.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: MeasurementId
    value: ParamValue | list[ParamValue]
    origin: PremiseOrigin
    by: ContractId | None = Field(default=None, exclude_if=lambda by: by is None)
    """The profiling contract that measured the fact, when one did."""
    pieces: list[PieceRef] = Field(default_factory=list, exclude_if=lambda pieces: not pieces)
    """The inspector pieces that measured the fact, omitted when empty."""
    coverage: Coverage | None = Field(default=None, exclude_if=lambda coverage: coverage is None)
    """How much of the data it was measured on, when a measurer read it (#465)."""

    def prose(self) -> str:
        """Render the fact, evidence quality, and optional measurer for a reviewer."""
        said = f"{self.id} is {self.value}, {_ORIGIN_PROSE[self.origin]}"
        if self.coverage == "head" and self.origin is PremiseOrigin.MEASURED:
            said += " on part of the data"
        measurer = " + ".join(self.pieces) if self.pieces else self.by
        if measurer and self.origin is PremiseOrigin.MEASURED:
            return f"{said} by {measurer}"
        return said


_ORIGIN_PROSE = {
    PremiseOrigin.MEASURED: "measured",
    PremiseOrigin.MODEL_READ: "read by AI",
    PremiseOrigin.ASSERTED: "asserted, not measured",
    PremiseOrigin.GOAL: "declared in the goal",
    PremiseOrigin.DERIVED: "inferred — nothing measured it",
    PremiseOrigin.UNMEASURED: "not measured",
}
"""A total mapping so every new origin requires explicit reader-facing prose."""
