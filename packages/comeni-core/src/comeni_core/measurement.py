"""Measurements as declared data.

`DataProfile` used to be four hardcoded fields, so a rule could only ever reason about
four things and adding a fifth meant editing a pure package, bumping a version and cutting
a release — something a bioinformatician cannot do and a curator cannot approve. The
tier-3 promise is that rules are data a domain expert adds; this is what makes that true.

`kind` is closed and there is deliberately no `string`. A free-text measurement is exactly
the hole `tests/test_egress.py` exists to close — `organism: "patient 4471023's tumour"` is
a perfectly valid string. A categorical declares its values instead, which also lets a rule
over it be checked for exhaustiveness.
"""

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from comeni_core.marks import MeasurementId, ParamValue


class UnknownMeasurementError(KeyError):
    """Raised when nothing declares this measurement."""


class BadMeasurementValueError(ValueError):
    """Raised when a value does not satisfy its declaration."""


class MeasurementKind(StrEnum):
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: MeasurementId
    kind: MeasurementKind
    values: list[str] = Field(default_factory=list)
    extensible: bool = False
    """Whether an overlay may contribute `add_values`.

    Per measurement, because the semantics genuinely differ: `strandedness` has exactly
    three values and a fourth is a bug, while `organism` can never be enumerated and a
    registry that tries is wrong.
    """
    minimum: float | None = None
    maximum: float | None = None
    unit: str | None = None
    description: str = ""
    cite: str | None = None
    edam: str | None = None
    deprecated: bool = False
    replaced_by: MeasurementId | None = None
    """A meaning change gets a *new id*; this one stays forever, pointing at its successor.

    OBO practice, which the ontologies this registry cites have used for two decades: never
    reuse an identifier, keep obsolete terms indefinitely. Per-measurement `@version` was
    rejected — every rule condition would grow a version, and omitting one would silently
    mean *latest*, which is the ambiguity versioning was meant to remove.
    """


class MeasurementRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurements: dict[str, Measurement] = Field(default_factory=dict)

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "MeasurementRegistry":
        if isinstance(layers, Path):
            layers = [layers]
        found: dict[str, Measurement] = {}
        for layer in layers:
            if not layer.exists():
                continue
            for path in sorted(layer.glob("*.yml")):
                measurement_id = path.name.removesuffix(".yml")
                data = yaml.safe_load(path.read_text()) or {}
                added = data.pop("add_values", None)
                if added is not None:
                    found[measurement_id] = _extend(found, measurement_id, added, path)
                    continue
                if data.get("kind") == "string":
                    raise ValueError(
                        f"{path}: kind 'string' does not exist. A categorical measurement "
                        f"declares its values as an enum; free text has nowhere safe to go."
                    )
                found[measurement_id] = Measurement(id=measurement_id, **data)
        return cls(measurements=found)

    def get(self, measurement_id: str) -> Measurement:
        if measurement_id not in self.measurements:
            raise UnknownMeasurementError(self._unknown(measurement_id))
        return self.measurements[measurement_id]

    def ids(self) -> list[str]:
        return sorted(self.measurements)

    def _unknown(self, measurement_id: str) -> str:
        return (
            f"{measurement_id!r} is not a declared measurement.\n"
            f"  Declared: {', '.join(self.ids()) or '(none)'}\n"
            f"  To add one, declare <layer>/measurements/{measurement_id}.yml"
        )

    def check(self, measurement_id: str, value: ParamValue) -> None:
        """Raise unless `value` satisfies the declaration for `measurement_id`."""
        measurement = self.get(measurement_id)
        kind = measurement.kind
        if kind is MeasurementKind.ENUM:
            if value not in measurement.values:
                raise BadMeasurementValueError(
                    f"{value!r} is not a declared value for {measurement_id!r}; "
                    f"allowed: {', '.join(measurement.values)}"
                )
            return
        if kind is MeasurementKind.BOOLEAN:
            if not isinstance(value, bool):
                raise BadMeasurementValueError(f"{measurement_id!r} is a boolean, got {value!r}")
            return
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise BadMeasurementValueError(f"{measurement_id!r} is a {kind}, got {value!r}")
        if kind is MeasurementKind.INTEGER and not isinstance(value, int):
            raise BadMeasurementValueError(f"{measurement_id!r} is an integer, got {value!r}")
        if measurement.minimum is not None and value < measurement.minimum:
            raise BadMeasurementValueError(
                f"{measurement_id!r} has minimum {measurement.minimum}, got {value!r}"
            )
        if measurement.maximum is not None and value > measurement.maximum:
            raise BadMeasurementValueError(
                f"{measurement_id!r} has maximum {measurement.maximum}, got {value!r}"
            )


def _extend(
    found: dict[str, Measurement], measurement_id: str, added: list[str], path: Path
) -> Measurement:
    if measurement_id not in found:
        raise ValueError(f"{path}: add_values for {measurement_id!r}, which no layer declares")
    base = found[measurement_id]
    if not base.extensible:
        raise ValueError(
            f"{path}: {measurement_id!r} is not extensible. Shadow the whole declaration to "
            f"change it, or set `extensible: true` where it is declared."
        )
    return base.model_copy(update={"values": [*base.values, *added]})
