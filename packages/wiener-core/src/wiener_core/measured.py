"""What a run measured, and how it compares with what the pipeline was built on (#465, #217).

A pipeline built by Mendel may measure facts while it runs: to decide a setting at run time, or
to confirm on all the data an estimate the build used. Each measuring step publishes a report
(`<sample>.measured.json`), and each run-time setting a record of the value it took
(`decided/<step>.<setting>.tsv`). When the run completes, Wiener reads them back as its own
`MEASURED` events: Nextflow never authors one, and only the closed payloads below enter.

`compare` sets them beside the pipeline's own record of what it rested on: an estimate the
run's value matches is confirmed; one it does not is a disagreement naming every decision that
used it. **The run's value wins**: it is what the data says, and a decision built on the
estimate is flagged, never silently kept.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from wiener_core.lab import LAB_STRING

_ID = r"^[a-z][a-z0-9_]{0,63}$"
Value = int | float | bool | str | None


class MeasuredFact(BaseModel):
    """One fact a measuring step reported for one sample."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: str = Field(pattern=_ID)
    sample: Annotated[str, LAB_STRING] = Field(max_length=256)
    """`meta.id`: a laboratory's own sample name."""
    value: int | float | bool | Annotated[str, LAB_STRING, Field(max_length=256)] | None = None
    """A string value may come from a laboratory's own file, so it is marked as theirs."""
    undetermined: Annotated[str, LAB_STRING] | None = Field(default=None, max_length=512)
    """Why there is no value; it may name a file, so it is the laboratory's words."""
    coverage: Literal["head", "all"] | None = None
    by: list[Annotated[str, Field(pattern=r"^[a-z0-9_]+@[0-9][0-9A-Za-z.+-]*$")]] = Field(
        default_factory=list, max_length=8)
    """The pieces, `fastq@1.1.0` then `read_length@1.0.0`."""


class DecidedValue(BaseModel):
    """The value a run-time setting took for one sample."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    setting: str = Field(pattern=_ID)
    sample: Annotated[str, LAB_STRING] = Field(max_length=256)
    value: Annotated[str, LAB_STRING] = Field(max_length=256)
    """As the run printed it; `null` when the lookup gave nothing."""


class Measurements(BaseModel):
    model_config = ConfigDict(frozen=True)

    facts: list[MeasuredFact] = Field(default_factory=list)
    """Sorted by measurement, then sample."""
    decided: list[DecidedValue] = Field(default_factory=list)
    """Sorted by step, setting, then sample."""


class Estimate(BaseModel):
    """What the pipeline rested on: from `pipeline.yml`'s `confirms`."""

    model_config = ConfigDict(frozen=True)

    measurement: str
    estimate: Value | list[Value]
    used_by: list[str]


class MeasuredView(BaseModel):
    """One measured fact as the run page shows it."""

    model_config = ConfigDict(frozen=True)

    measurement: str
    sample: Annotated[str, LAB_STRING]
    value: Value
    status: Literal["confirmed", "disagrees", "measured", "undetermined"]
    """`confirmed`: equal to the estimate the build used. `disagrees`: different, so every
    decision in `used_by` rested on a value the data does not bear out. `measured`: nothing was
    estimated (a run-time fact). `undetermined`: the step could not say."""
    estimate: Value | list[Value] = None
    used_by: list[str] = Field(default_factory=list)
    coverage: Literal["head", "all"] | None = None
    by: list[str] = Field(default_factory=list)
    reason: Annotated[str, LAB_STRING] | None = None


def collect(events) -> Measurements:
    """The facts and decided values among a run's events, in a stable order; a redelivered
    report counts once."""
    events = list(events)  # read twice below; a generator would give the second pass nothing
    facts = {(e.measured.measurement, e.measured.sample): e.measured
             for e in events if getattr(e, "measured", None) is not None}
    decided = {(d.step, d.setting, d.sample): d
               for d in (getattr(e, "decided", None) for e in events) if d is not None}
    return Measurements(facts=[facts[k] for k in sorted(facts)],
                        decided=[decided[k] for k in sorted(decided)])


def _agrees(estimate, value) -> bool:
    """A cohort's estimate (one value per sample) agrees when the sample's value is among it."""
    if isinstance(estimate, list):
        return value in estimate
    if isinstance(estimate, int | float) and isinstance(value, int | float) \
            and not isinstance(estimate, bool) and not isinstance(value, bool):
        return float(estimate) == float(value)
    return estimate == value


def compare(measured: Measurements, estimates: list[Estimate]) -> list[MeasuredView]:
    """Each measured fact beside the estimate the build used, if it used one."""
    by_fact = {e.measurement: e for e in estimates}
    views = []
    for fact in measured.facts:
        estimate = by_fact.get(fact.measurement)
        if fact.undetermined is not None or fact.value is None:
            status = "undetermined"
        elif estimate is None:
            status = "measured"
        else:
            status = "confirmed" if _agrees(estimate.estimate, fact.value) else "disagrees"
        views.append(MeasuredView(
            measurement=fact.measurement, sample=fact.sample, value=fact.value, status=status,
            estimate=estimate.estimate if estimate else None,
            used_by=list(estimate.used_by) if estimate else [],
            coverage=fact.coverage, by=list(fact.by), reason=fact.undetermined,
        ))
    return views
