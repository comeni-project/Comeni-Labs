"""Declare typed measurements and validate profiled values.

Measurements are registry data used by goal loading, routing, and pipeline metadata. Supported
kinds are integer, number, boolean, and enum. Free text is intentionally unsupported; categorical
values must be declared as an enum.
"""

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from comeni_core import yaml_strict
from comeni_core.declared.layered import (
    DeclaredKind,
    Displacement,
    Kind,
    Policy,
    Stacked,
    layers_of,
    stack,
)
from comeni_core.diagnostics import coded
from comeni_core.goal.profile import DataProfile, Evidence, Measured
from comeni_core.plan.tiers import ValueSource
from comeni_core.spell.marks import MeasurementId, ParamValue, TypeId


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
    """Translate one declared value to the value expected in module metadata."""

    model_config = ConfigDict(extra="forbid")

    when: ParamValue
    then: ParamValue


class Measurement(BaseModel):
    """A typed property that a goal may assert or a profiling contract may measure."""

    model_config = ConfigDict(extra="forbid")

    id: MeasurementId
    kind: MeasurementKind
    values: list[str] = Field(default_factory=list)
    extensible: bool = False
    """Whether an overlay may extend this declaration with `add_values`."""
    per_sample: bool = False
    """Whether the value may be a list with one entry per sample.

    Scalars remain valid for a uniform cohort. This is independent of `describes`, which controls
    whether the value can be carried into metadata for a particular data type.
    """
    assertion_only: bool = False
    """Whether a goal must supply this value because no profiling contract produces it."""

    assertion_only_because: str = ""
    """Human-readable reason for `assertion_only`; required exactly when that flag is true."""

    minimum: float | None = None
    maximum: float | None = None
    unit: str | None = None
    description: str = ""
    cite: str | None = None
    explain: str | None = Field(default=None, min_length=1, max_length=600)
    """Short user-facing explanation; it does not affect pipeline construction."""
    edam: str | None = None
    describes: TypeId | None = None
    """Data type whose metadata may carry this measurement, for example `fastq.reads`."""

    meta_key: str | None = None
    """Key used when carrying this value in module metadata; absent disables carrying it."""

    meta_values: list[MetaValue] = Field(default_factory=list)
    """Optional translations from declared values to module metadata values."""

    @model_validator(mode="after")
    def _assertion_only_says_why(self) -> "Measurement":
        """Require `assertion_only` and its explanation to appear together."""
        if self.assertion_only and not self.assertion_only_because:
            raise ValueError(
                coded("MD0315", f"measurement {self.id!r} declares `assertion_only` with no "
                f"`assertion_only_because`. A reader cannot tell 'no tool exists for this' "
                f"from 'the tool exists and nobody has vendored it', and those are "
                f"different amounts of work.")
            )
        if self.assertion_only_because and not self.assertion_only:
            raise ValueError(
                coded(
                    "MD0315",
                    f"measurement {self.id!r} explains why nothing measures it and does "
                    f"not declare `assertion_only: true`. One of the two is wrong.")
            )
        return self

    deprecated: bool = False
    replaced_by: MeasurementId | None = None
    """Successor ID for a deprecated measurement; meaning changes receive a new ID."""


class MeasurementDelta(BaseModel):
    """An overlay that adds values to an extensible declaration in a lower layer."""

    model_config = ConfigDict(extra="forbid")

    id: MeasurementId
    add_values: list[str]


def _parse_measurement(path: Path) -> list[Measurement | MeasurementDelta]:
    """Parse one declaration or `add_values` extension.

    `id` is required. The generic stacker consumes `declares`; this parser discards it before
    strict model validation. Extensions may not carry replacement fields.
    """
    data = yaml_strict.load(path) or {}
    data.pop("declares", None)
    measurement_id = data.pop("id", None)
    if not measurement_id:
        raise ValueError(
            coded(
                "MD0012",
                f"{path} is a measurement and declares no `id:`. The filename stopped\n"
                f"  being the identity when a file stopped having to live in a directory\n"
                f"  named for its kind.",
            )
        )
    added = data.pop("add_values", None)
    if added is not None:
        if data:
            # An extension cannot also replace fields from the underlying declaration.
            raise ValueError(
                f"{path}: `add_values` extends a declaration and cannot carry "
                f"{', '.join(sorted(data))} as well. Shadow the whole file to change those."
            )
        return [MeasurementDelta(id=measurement_id, add_values=added)]
    if data.get("kind") == "string":
        raise ValueError(
            f"{path}: kind 'string' does not exist. A categorical measurement "
            f"declares its values as an enum; free text has nowhere safe to go."
        )
    return [Measurement(id=measurement_id, **data)]


def _merge_measurement(
    old: Measurement | MeasurementDelta, new: Measurement | MeasurementDelta
) -> Measurement | MeasurementDelta:
    """Replace with a full declaration or append an allowed `add_values` extension."""
    if not isinstance(new, MeasurementDelta):
        return new
    if isinstance(old, MeasurementDelta):
        return MeasurementDelta(id=old.id, add_values=[*old.add_values, *new.add_values])
    if not old.extensible:
        raise ValueError(
            f"{old.id!r} is not extensible. Shadow the whole declaration to change it, "
            f"or set `extensible: true` where it is declared."
        )
    return old.model_copy(update={"values": [*old.values, *new.add_values]})


class MeasuredEntry(NamedTuple):
    """One fact for `profile_of`, including its source and optional evidence."""

    measurement: str
    value: ParamValue | list[ParamValue]
    source: ValueSource
    by: str | None = None
    pieces: tuple[str, ...] = ()
    evidence: Evidence | None = None


class MeasurementRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurements: dict[str, Measurement] = Field(default_factory=dict)

    displaced: list[Displacement] = Field(default_factory=list)
    """Declarations replaced or extended by higher layers."""

    @staticmethod
    def kind() -> Kind[str, Measurement | MeasurementDelta]:
        """How measurements are found, keyed and stacked. Everything else is `stack()`."""
        return Kind(
            DeclaredKind.MEASUREMENTS,
            parse=_parse_measurement,
            key=lambda entry: entry.id,
            policy=Policy.MERGE,
            merge=_merge_measurement,
        )

    @classmethod
    def of(cls, stacked: Stacked[str, "Measurement | MeasurementDelta"]) -> "MeasurementRegistry":
        """Build a registry from a stacked result, refusing an extension of nothing."""
        found: dict[str, Measurement] = {}
        for measurement_id, entry in stacked.entries.items():
            if isinstance(entry, MeasurementDelta):
                raise ValueError(
                    f"add_values for {measurement_id!r}, which no layer declares"
                )
            found[measurement_id] = entry
        return cls(measurements=found, displaced=list(stacked.displaced))

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "MeasurementRegistry":
        """Load declarations from one or more layer roots in precedence order."""
        return cls.of(stack(layers_of(layers), cls.kind()))

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
            f"  To add one, add a file to a layer carrying `declares: measurement`\n"
            f"  and `id: {measurement_id}`. Since comeni-registry#1 the path is free;\n"
            f"  the convention is <layer>/measurements/{measurement_id}.yml."
        )

    def coerce(
        self, measurement_id: str, value: ParamValue | list[ParamValue]
    ) -> ParamValue | list[ParamValue]:
        """`value` read as the declaration's kind when it arrived as text, else unchanged.

        Integer, decimal, and boolean text is converted only when it unambiguously matches the
        declared kind. Other text is returned unchanged so `check` can report the mismatch.
        """
        if isinstance(value, list):
            return [self.coerce(measurement_id, element) for element in value]
        if not isinstance(value, str):
            return value
        kind, text = self.get(measurement_id).kind, value.strip()
        digits = text[1:] if text[:1] in "+-" else text
        whole = digits.isdecimal()
        if kind is MeasurementKind.INTEGER and whole:
            return int(text)
        if kind is MeasurementKind.NUMBER and (
            whole or (digits.count(".") == 1 and digits.replace(".", "", 1).isdecimal())
        ):
            return int(text) if whole else float(text)
        if kind is MeasurementKind.BOOLEAN and text.lower() in ("true", "false"):
            return text.lower() == "true"
        return value

    def check(self, measurement_id: str, value: ParamValue | list[ParamValue]) -> None:
        """Raise unless `value` satisfies the declaration for `measurement_id`.

        Lists are accepted only for `per_sample` measurements and are validated element by
        element. Numeric bounds are inclusive. Booleans are not accepted as integers.
        """
        measurement = self.get(measurement_id)
        if isinstance(value, list):
            if not measurement.per_sample:
                raise BadMeasurementValueError(
                    f"{measurement_id!r} is not declared `per_sample`, so it takes one value "
                    f"and not a list. Declare `per_sample: true` where it is declared, or "
                    f"write the one value the whole cohort shares."
                )
            for element in value:
                self.check(measurement_id, element)
            return
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
            article = "an" if kind is MeasurementKind.INTEGER else "a"
            raise BadMeasurementValueError(
                f"{measurement_id!r} is {article} {kind}, got {value!r}"
            )
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
        mapping: dict[str, ParamValue | list[ParamValue]],
        *,
        source: ValueSource = ValueSource.SAID,
        by: str | None = None,
    ) -> DataProfile:
        """Build a validated profile whose entries share one source and optional producer."""
        return self.profile_of([MeasuredEntry(k, v, source, by) for k, v in mapping.items()])

    def profile_of(self, entries: Sequence["MeasuredEntry | tuple"]) -> DataProfile:
        """Build a validated profile from entries with independent provenance.

        A four-item `(measurement, value, source, by)` tuple is accepted and receives no pieces
        or evidence. Output is sorted by measurement ID.
        """
        given = [MeasuredEntry(*entry) for entry in entries]
        for entry in given:
            if isinstance(entry.pieces, str):
                # A string is iterable, so it was read letter by letter (issue 225).
                raise ValueError(
                    f"{entry.measurement}: pieces is a tuple of piece refs, not one string "
                    f"({entry.pieces!r}); write ({entry.pieces!r},)"
                )
            self.check(entry.measurement, entry.value)
        return DataProfile(
            measurements=[
                Measured(
                    measurement=entry.measurement,
                    value=entry.value,
                    source=entry.source,
                    by=entry.by,
                    pieces=list(entry.pieces),
                    evidence=entry.evidence,
                )
                for entry in sorted(given, key=lambda entry: entry.measurement)
            ]
        )


    def to_measure(self, by_contract: dict[str, str]) -> DataProfile:
        """Describe pending measurements and their contracts, using `None` for unknown values."""
        for measurement_id in by_contract:
            self.get(measurement_id)  # raises naming what is declared
        return DataProfile(
            measurements=[
                Measured(measurement=k, value=None, source=ValueSource.MEASURED, by=v)
                for k, v in sorted(by_contract.items())
            ]
        )


    def meta_for(self, type_id: str, profile: DataProfile) -> dict[str, ParamValue]:
        """Return metadata values applicable to `type_id` from the supplied profile."""
        return {key: value for key, (_, value) in self.meta_sources_for(type_id, profile).items()}

    def meta_sources_for(
        self, type_id: str, profile: DataProfile
    ) -> dict[str, tuple["Measurement", ParamValue]]:
        """Return metadata values and their declarations for one input type."""
        return self.meta_sources_by_type({type_id}, profile).get(type_id, {})

    def meta_sources_by_type(
        self, type_ids: set[str], profile: DataProfile
    ) -> dict[str, dict[str, tuple["Measurement", ParamValue]]]:
        """Collect metadata values and declarations for several types in one registry pass.

        Measurement ID order defines precedence when declarations share a metadata key.
        """
        values = {entry.measurement: entry.value for entry in reversed(profile.measurements)}
        found: dict[str, dict[str, tuple[Measurement, ParamValue]]] = {}
        for measurement_id in self.ids():
            measurement = self.get(measurement_id)
            if measurement.describes not in type_ids or not measurement.meta_key:
                continue
            value = values.get(measurement_id)
            if value is None:
                continue
            for translation in measurement.meta_values:
                if translation.when == value:
                    value = translation.then
                    break
            found.setdefault(measurement.describes, {})[measurement.meta_key] = (measurement, value)
        return found
