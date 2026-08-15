"""What the input data measurably looks like. A shape, never data.

Invariant 15: Mendel does not receive patient data. A profile says "paired, 150bp,
reverse-stranded, twelve samples", which is true of thousands of studies and identifies
nobody. There is no filename field, no sample identifier and no path, and `extra="forbid"`
on both models is what stops one being added by accident.

This lives in `comeni-core` rather than beside `Goal` in `mendel-resolver` because a
profile is made of measurements, and measurements are declared here. The alternative —
`MeasurementRegistry.profile()` reaching back into `mendel-resolver` through a
function-local import — is a layering inversion wearing a disguise, and would have meant
widening `comeni-core`'s closed allowlist in `tests/test_purity.py` to permit it. Closes
issue #4. `mendel_resolver.goal` re-exports both names, so every existing import still
resolves.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from comeni_core.plan.tiers import ValueSource
from comeni_core.spell.marks import ContractId, MeasurementId, ParamValue


class Measured(BaseModel):
    """One measurement and where its value came from.

    A generated profile records the tool; a hand-written goal records nothing, and that is
    an assertion by whoever wrote it. The shorthand is not an abbreviation of provenance —
    it *is* the provenance, which is why a bare scalar is allowed at all.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: MeasurementId
    value: ParamValue | list[ParamValue]
    """A list only where the measurement declares `per_sample` — `MeasurementRegistry.check`
    is what enforces that, since the declaration lives there and not here."""
    source: ValueSource = ValueSource.GOAL
    by: ContractId | None = None
    """Which contract produced this value. `None` for anything a person asserted."""


class DataProfile(BaseModel):
    """Measured properties of the input data.

    A list rather than a mapping because `tests/test_egress.py` forbids mappings in
    anything reachable from a payload: a typed key does not prove a *declared* key.

    Build one through `MeasurementRegistry.profile()`, which is the only place that
    validates values against their declarations — `tests/test_construction.py` enforces
    that. The mapping shorthand below exists because it is the natural way to *write* one
    in a goal file, and because `Goal` needs a default.
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
        """Reject a repeated measurement, and sort.

        `MeasurementRegistry.profile()` takes a `dict` and sorts it, so the validated path
        was always normalised and the deserialised path never was. `get` returns the first
        match, so two profiles asserting the same facts in a different order resolved to
        different pipelines — invariant 10 held literally (same `Goal`, same bytes) and
        failed in the sense anyone would rely on. Audit 2026-08-06, A13.

        In the validator rather than in one constructor, because a profile arrives from a
        published bundle as often as it is built, and a normalisation only one of two
        entry points performs is the shape of half this audit's findings.
        """
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
