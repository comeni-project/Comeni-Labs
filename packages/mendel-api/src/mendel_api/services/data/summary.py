"""The Data Overview (#511): the same four tiles whatever the data is, the measured facts the
samples can be compared by, and what was measured. **Neutral to the kind of data**: what is shown
comes from what this data measured, never from a list kept for reads."""

from statistics import median

from pydantic import BaseModel

from mendel_api.services.data.facts import derive


class Tile(BaseModel):
    label: str
    value: str
    hint: str | None = None


class SampleValue(BaseModel):
    sample: str
    value: float | int


class CompareBy(BaseModel):
    measurement: str
    label: str
    unit: str | None = None
    values: list[SampleValue]
    median: float | int


class MeasuredFact(BaseModel):
    measurement: str
    label: str
    value: object = None
    origin: str


class Summary(BaseModel):
    tiles: list[Tile] = []
    compare_by: list[CompareBy] = []
    measured: list[MeasuredFact] = []


def label(measurement: str) -> str:
    """A measurement's words: its id as a sentence (`read_length` → *Read length*)."""
    return measurement.replace("_", " ").replace(".", " ").capitalize()


def _unit(measurement: str) -> str | None:
    from mendel_api.services import registry

    try:
        return registry.stack().measurements.get(measurement).unit
    except Exception:  # noqa: BLE001 — an undeclared measurement simply has no unit
        return None


def _size(total: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024 or unit == "GB":
            return f"{total:.0f} {unit}" if unit == "B" else f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} TB"


def summary(samples: list[dict], files: list[dict]) -> Summary:
    kept = [s for s in samples if not s.get("left_out")]
    kinds = {s.get("type_id") for s in kept}
    tiles = [
        Tile(label="Samples", value=str(len(kept)),
             hint=f"{len(samples) - len(kept)} left out" if len(samples) > len(kept) else None),
        Tile(label="Kinds of data", value=str(len(kinds))),
        Tile(label="Size on disk", value=_size(sum(f.get("size", 0) for f in files))),
        Tile(label="Files", value=str(len(files))),
    ]
    numeric: dict[str, list[SampleValue]] = {}
    for s in kept:
        for fact in s.get("facts", []):
            value = fact.get("value")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric.setdefault(fact["measurement"], []).append(
                    SampleValue(sample=s["name"], value=value))
    compare = [CompareBy(measurement=m, label=label(m), unit=_unit(m), values=values,
                         median=median(v.value for v in values))
               for m, values in sorted(numeric.items()) if len(values) == len(kept)]
    facts, _ = derive(samples)
    measured = [MeasuredFact(measurement=f.subject, label=label(f.subject), value=f.value,
                         origin=f.origin.value) for f in facts]
    return Summary(tiles=tiles, compare_by=compare, measured=measured)
