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
from comeni_core.goal.profile import DataProfile, Measured
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
    per_sample: bool = False
    """Whether this is a property of each sample rather than of the study.

    A per-sample measurement may be written as **a scalar or a list**: a scalar says the
    cohort is uniform in this respect, which is what every goal file written so far means by
    `read_length: 150`, and a list gives one value per sample. Both are the same claim at
    different resolutions, and refusing the scalar would invalidate every existing goal to
    buy nothing — the same call `DataProfile._accept_mapping` and `Constraints._accept_mapping`
    already make about the ergonomic form and the safe one being different decisions.

    Distinct from `describes`, which says *what kind of thing* a measurement is about and
    governs whether it can be carried into a module's `meta` map. `n_samples` describes the
    study and is not per-sample; `read_length` is both. A rule that must reduce a cohort to
    one number says so through a `derives:` aggregate rather than by hoping the profile
    happened to carry a scalar.
    """
    assertion_only: bool = False
    """Whether nothing in this stack can measure it, so a goal must assert it.

    Issue #38: *"a measurement is a claim that some property of the data is worth measuring
    and **can be**"*, and the second half was invisible. A profiling contract produces a
    `measurement.<id>` type, so the answer is already derivable from the registry — but
    nothing said it, so a measurement nobody could produce looked exactly like one somebody
    had wired a tool for, and a rule keyed on it looked exactly as sound.

    Declared rather than derived, even though it is derivable, for the reason `describes` is:
    the registry is data a domain expert writes and a curator approves, and *"we have not
    wired a tool for this yet"* is a statement somebody should have to make. Where the two
    disagree, `tests/test_measurement_vocabulary.py` refuses the file.

    An asserted measurement is not a lesser one — `strandedness` is asserted in every shipped
    goal and drives featureCounts' `-s` — but it is different **evidence**, which is what
    `PremiseOrigin` records and what the `sealed` profile is meant to act on.
    """

    assertion_only_because: str = ""
    """Why nothing measures it. Required where `assertion_only` is set.

    A boolean with no reason is a fact nobody can act on: a reader cannot tell "no tool exists
    for this" from "the tool exists and nobody has vendored it", and those are different
    amounts of work. §4.7's rule — no structured value is a reader's only account of itself —
    applied to a flag rather than to a mapping.
    """

    minimum: float | None = None
    maximum: float | None = None
    unit: str | None = None
    description: str = ""
    cite: str | None = None
    edam: str | None = None
    describes: TypeId | None = None
    """Which type this is a property of, e.g. `fastq.reads`.

    **A `TypeId`, not a `MeasurementId`** — it was annotated as the latter, and nothing
    noticed because neither alias validated anything. A64 (issue #28) gave both a shape and
    the mismatch failed on the first load: `fastq.reads` is a type id and is not a
    measurement id. Two declared aliases that accept the same strings are two labels, and a
    label applied to the wrong kind of value is exactly what invariant 14's *"a declared ID
    alias"* was supposed to rule out.

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
    @model_validator(mode="after")
    def _assertion_only_says_why(self) -> "Measurement":
        """A flag with no reason is a fact nobody can act on. Issue #38."""
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
    """A meaning change gets a *new id*; this one stays forever, pointing at its successor.

    OBO practice, which the ontologies this registry cites have used for two decades: never
    reuse an identifier, keep obsolete terms indefinitely. Per-measurement `@version` was
    rejected — every rule condition would grow a version, and omitting one would silently
    mean *latest*, which is the ambiguity versioning was meant to remove.
    """


class MeasurementDelta(BaseModel):
    """An overlay extending a measurement's values rather than replacing it.

    A separate type rather than an optional field on `Measurement`, because the two are
    genuinely different declarations: this one is meaningless without a lower layer, and
    `stack()` needs to be able to tell them apart in `merge` without inspecting whether a
    field happens to be empty.
    """

    model_config = ConfigDict(extra="forbid")

    id: MeasurementId
    add_values: list[str]


def _parse_measurement(path: Path) -> list[Measurement | MeasurementDelta]:
    """One measurement file — a declaration, or an extension of one.

    The filename is the id unless the file declares one — comeni-registry#1, so a file can be
    moved without being renamed. `declares:` is accepted and ignored for the same reason: every
    declared model forbids extra fields, so a migrated file must load before the loader starts
    depending on the field.
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
            # It used to be popped and the rest of the file ignored, so an overlay
            # declaring `add_values` *and* a new `meta_key` silently got only the values.
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
    """What a higher layer's file does to the one below it.

    A whole declaration replaces; an `add_values` extends. One function, so the two are
    a visible pair rather than two branches in a loop — which is A35's shape in the
    vocabulary loader, where some fields replaced and others did not.
    """
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


class MeasurementRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurements: dict[str, Measurement] = Field(default_factory=dict)

    displaced: list[Displacement] = Field(default_factory=list)
    """What a higher layer replaced or extended here.

    On the registry rather than returned beside it, for the reason `Registry.displaced`
    gives: a caller who has to carry a second value is a caller who will drop it, and this
    one reaches `PipelineIR.displaced` and therefore a publish bundle.
    """

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
        """Load measurements across a layer stack.

        **Takes layer roots, not `measurements/` directories.** A layer is one directory
        holding all four kinds, and a loader that is handed a slice of one cannot know
        which layer it is reading — which is exactly why displacement went unrecorded
        (A23). Callers wanting the displacements use `stack()` and `of()` directly, as
        `mendel_resolver.layers.load` does.
        """
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
            f"  To add one, declare <layer>/measurements/{measurement_id}.yml"
        )

    def check(self, measurement_id: str, value: ParamValue | list[ParamValue]) -> None:
        """Raise unless `value` satisfies the declaration for `measurement_id`.

        A list is permitted only where the measurement declares `per_sample`, and then every
        element is checked against the same declaration — a cohort of read lengths is a cohort
        of read lengths, not a new kind of thing. Refusing a list everywhere else matters more
        than it looks: `check` is what stands between a goal file and routing, and a list
        reaching a comparison predicate raises `TypeError` at resolution rather than a
        diagnostic at load.
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
        mapping: dict[str, ParamValue | list[ParamValue]],
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
        return {key: value for key, (_, value) in self.meta_sources_for(type_id, profile).items()}

    def meta_sources_for(
        self, type_id: str, profile: DataProfile
    ) -> dict[str, tuple["Measurement", ParamValue]]:
        """The same entries, each with the measurement that produced it.

        `meta_for` answers *what value* and is what emission needs. This answers *on whose
        authority*, which is what the artifact needs and did not have: `strandedness: reverse`
        becomes featureCounts' `-s 2` — the classic way to a matrix of zeroes — and it reached
        the tool with no provenance of any kind while the measurement's own declared `cite`
        stopped at the registry. Audit A80.

        Two accessors rather than one richer return, because the callers want different
        things and `meta_for`'s three test callers assert on a plain mapping. This is the
        provenance-carrying one; that one stays the value-carrying one and is now derived from
        it, so they cannot disagree about which entries exist.
        """
        found: dict[str, tuple[Measurement, ParamValue]] = {}
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
            found[measurement.meta_key] = (measurement, value)
        return found
