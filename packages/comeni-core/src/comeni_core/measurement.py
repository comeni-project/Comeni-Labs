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
from comeni_core.profile import DataProfile, Measured
from comeni_core.tiers import ValueSource


class UnknownMeasurementError(KeyError):
    """Raised when nothing declares this measurement."""


class BadMeasurementValueError(ValueError):
    """Raised when a value does not satisfy its declaration."""


class MeasurementKind(StrEnum):
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"


class MetaValue(BaseModel):
    """One value translation between our vocabulary and a module's.

    A list of records rather than a mapping, matching `ParamBinding` and `Measured`: a
    typed key does not prove a declared key, and `Measurement` is one field away from
    being reachable from a publish bundle.
    """

    model_config = ConfigDict(extra="forbid")

    when: ParamValue
    then: ParamValue


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
    describes: MeasurementId | None = None
    """Which type this is a property of, e.g. `fastq.reads`.

    Only measurements that describe something can be carried into that thing's `meta` map.
    `n_samples` describes the study rather than a read, so it has no `describes` and is
    never carried.
    """

    meta_key: str | None = None
    """How a module spells this in `meta`, if any. Absent means never carried.

    Opt-in, so nothing lands in a meta map by accident. nf-core modules read
    `meta.strandedness` and `meta.single_end` directly and do their own translation into
    flags — which is why Mendel carries the *fact* and lets the module keep its encoding.
    """

    meta_values: list[MetaValue] = Field(default_factory=list)
    """Value translations, when our vocabulary and the module's disagree.

    We ask whether a library is `paired`; nf-core asks whether it is `single_end`. The same
    fact spelled inside out. Declared here rather than known by the compiler, for the same
    reason `entry_channel` is declared: this has to work for a module nobody has seen.
    """
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

    def profile(
        self,
        mapping: dict[str, ParamValue],
        *,
        source: ValueSource = ValueSource.GOAL,
        by: str | None = None,
    ) -> DataProfile:
        """The one validated way to build a `DataProfile`.

        Validation needs this registry, which the model cannot hold, so it happens here.
        `tests/test_construction.py` asserts nothing else constructs a profile — a second
        path skipping validation would produce an unchecked profile flowing straight into
        routing, which is the class of bug that left `subject: aligner` dead for months.
        """
        for measurement_id, value in mapping.items():
            self.check(measurement_id, value)
        return DataProfile(
            measurements=[
                Measured(measurement=k, value=v, source=source, by=by)
                for k, v in sorted(mapping.items())
            ]
        )


    def to_measure(self, by_contract: dict[str, str]) -> DataProfile:
        """A profile naming what will be measured and by what, with no values yet.

        `value: None` is deliberate and honest: the pipeline has been *emitted*, not run.
        The laboratory runs it and fills the values in. Anything else would be Mendel
        reporting a number it has never seen, which is what invariant 15 exists to
        prevent — and the file it writes is the same shape a goal accepts back, so the
        round trip is measure, fill in, build.
        """
        for measurement_id in by_contract:
            self.get(measurement_id)  # raises naming what is declared
        return DataProfile(
            measurements=[
                Measured(measurement=k, value=None, source=ValueSource.MEASURED, by=v)
                for k, v in sorted(by_contract.items())
            ]
        )


    def meta_for(self, type_id: str, profile: DataProfile) -> dict[str, ParamValue]:
        """The `meta` entries a channel of `type_id` should carry, from this profile.

        Only measurements that declare both `describes` and `meta_key`, and that the
        profile actually measured. Everything else is silence, which is the honest default:
        a `meta` key with a made-up value is worse than an absent one, because the module
        will use it.
        """
        found: dict[str, ParamValue] = {}
        for measurement_id in self.ids():
            measurement = self.get(measurement_id)
            if measurement.describes != type_id or not measurement.meta_key:
                continue
            value = profile.get(measurement_id)
            if value is None:
                continue
            for translation in measurement.meta_values:
                if translation.when == value:
                    value = translation.then
                    break
            found[measurement.meta_key] = value
        return found


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
