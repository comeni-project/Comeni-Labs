"""Validated measurements describing input shape rather than input data.

Profiles may describe properties such as read length, pairing, and sample count. Their closed
models have no filename, sample-identifier, or path field. The types live in ``comeni-core`` so
measurement declarations can construct profiles without depending on the resolver; the resolver
re-exports them for compatibility.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from comeni_core.plan.tiers import ValueSource
from comeni_core.spell.marks import ContractId, MeasurementId, ParamValue, PieceRef


class Evidence(BaseModel):
    """How much input an inspector read to establish a measurement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    records: int | None = Field(default=None, ge=0, exclude_if=lambda count: count is None)
    rows: int | None = Field(default=None, ge=0, exclude_if=lambda count: count is None)
    share: float | None = Field(default=None, ge=0, le=1, exclude_if=lambda share: share is None)
    """Each value is serialized only when known."""

    @model_validator(mode="after")
    def _says_something(self) -> "Evidence":
        if self.records is None and self.rows is None and self.share is None:
            raise ValueError("evidence with no count says nothing; leave it out instead")
        return self


class Measured(BaseModel):
    """One measurement and where its value came from.

    Generated entries record their measurer; a bare person-authored value is asserted.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: MeasurementId
    value: ParamValue | list[ParamValue]
    """Lists are valid only for declarations marked ``per_sample`` by the registry."""
    source: ValueSource = ValueSource.SAID
    by: ContractId | None = None
    """The profiling contract that produced the value, when applicable."""
    pieces: list[PieceRef] = Field(default_factory=list, exclude_if=lambda pieces: not pieces)
    """Ordered inspector pieces that produced the value, omitted when empty.

    A profiling contract uses ``by`` instead. Person-authored assertions use neither.
    """
    evidence: Evidence | None = Field(default=None, exclude_if=lambda evidence: evidence is None)

    @model_validator(mode="after")
    def _one_measurer(self) -> "Measured":
        if self.by is not None and self.pieces:
            raise ValueError(
                "a measured value has one measurer: a contract (`by`) or inspector pieces, "
                "not both"
            )
        if (self.pieces or self.evidence is not None) and self.source is not ValueSource.MEASURED:
            # Its reason would say *asserted* while its own entry names what measured it.
            raise ValueError(
                f"pieces and evidence belong to a measured value, and this one is "
                f"{self.source.value}"
            )
        return self


class DataProfile(BaseModel):
    """Measured properties of the input data.

    The record list gives published payloads declared keys. Person-authored goal files may use a
    concise measurement-to-value mapping, which the pre-validator converts to records.

    Production callers should build profiles through ``MeasurementRegistry.profile()`` so values
    are also checked against their measurement declarations.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurements: list[Measured] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_mapping(cls, data: object) -> object:
        if isinstance(data, dict) and "measurements" not in data:
            return {
                "measurements": [{"measurement": k, "value": v} for k, v in sorted(data.items())]
            }
        return data

    @model_validator(mode="after")
    def _one_entry_per_measurement(self) -> "DataProfile":
        """Reject duplicate facts and normalize order at every construction boundary."""
        names = [m.measurement for m in self.measurements]
        repeated = sorted({n for n in names if names.count(n) > 1})
        if repeated:
            raise ValueError(
                f"a profile may state each measurement once; repeated: {', '.join(repeated)}"
            )
        self.measurements.sort(key=lambda m: m.measurement)
        return self

    def get(self, measurement_id: str) -> ParamValue | list[ParamValue]:
        return next(
            (m.value for m in self.measurements if m.measurement == measurement_id), None
        )
