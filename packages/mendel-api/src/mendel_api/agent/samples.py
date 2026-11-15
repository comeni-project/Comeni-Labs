"""Samples a person uploads (#134, #466): kept on the session with what each measured, and the
facts every sample agrees on."""

from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession


def _sample_name(name: str) -> str:
    """A sample's name as the session keeps it: at most 256 characters, cut rather than refused,
    so a long file name never fails the upload or reaches a validation message (review)."""
    return name if len(name) <= 256 else name[:255] + "…"


def _keep_samples(session_id: str, grouped, inspections) -> None:
    """Every sample, with its name, its files and what was measured on it, on the session."""
    from mendel_api.authoring.types import SampleFact, UploadedSample

    kept = [
        UploadedSample(
            name=_sample_name(sample.name),
            files=[_sample_name(name) for name, _ in sample.files], outcome=found.outcome,
            facts=[SampleFact(measurement=f.measurement, value=f.value, coverage=f.coverage)
                   for f in found.facts if f.undetermined is None],
        ).model_dump(mode="json")
        for sample, found in zip(grouped, inspections, strict=True)
    ]
    with session_scope() as db:
        db.get(PipelineAuthoringSession, session_id).samples = kept


def _agreed(inspections):
    """What several samples settle together: each fact every sample decided the same way. A fact
    they disagree on, or one a sample did not decide (or was not read), is left out, to be asked
    (#466)."""
    measured = [i for i in inspections if i.outcome == "measured"]
    if not measured:
        return inspections[0]
    first = measured[0]
    values: dict[str, set] = {}
    for found in measured:
        for f in found.facts:
            if f.undetermined is None:
                values.setdefault(f.measurement, set()).add(repr(f.value))
    # Every sample, not only those read: a sample nothing measured has not agreed (review).
    decided = {m for m, v in values.items() if len(v) == 1 and len(measured) == len(inspections)
               and all(any(f.measurement == m and f.undetermined is None for f in i.facts)
                       for i in measured)}
    return first.model_copy(update={
        "facts": [f for f in first.facts if f.measurement in decided],
        "steps": [*first.steps, f"measured {len(measured)} of {len(inspections)} samples"],
    })
