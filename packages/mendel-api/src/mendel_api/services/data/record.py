"""What several samples settle together, recorded on the draft (#466, #511): the facts every
sample measured the same way become the pipeline's measured facts, and the input type is set.
**One path for every way data arrives**, so the resolver, the rules and the builder agent read
the same facts whichever way the samples came."""

from mendel_authoring.decisions import FactOrigin
from mendel_authoring.payloads import DecisionChange

from mendel_api.services import changes, decisions
from mendel_api.services.inspect import Inspection


def agreed(inspections: list[Inspection]) -> Inspection:
    """What several samples settle together: each fact every sample decided the same way. A fact
    they disagree on, or one a sample did not decide (or was not read), is left out, to be asked
    (#466)."""
    measured = [i for i in inspections if i.outcome == "measured"]
    if not measured:
        return inspections[0] if inspections else Inspection(outcome="unreadable")
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


def record_measured(draft_id: str, found: Inspection, *, who: str) -> list[str]:
    """Each agreed fact recorded as measured, unless the person already said it (their word
    stands), and the input type set. Returns the measurements recorded."""
    said = {f.subject for f in decisions.read(draft_id).facts
            if f.origin is FactOrigin.PERSON_SAID}
    recorded = []
    for fact in found.facts:
        if fact.undetermined is not None or fact.value is None or fact.measurement in said:
            continue
        decisions.observe(draft_id, fact.measurement, fact.value, origin=FactOrigin.MEASURED,
                          pieces=fact.pieces)
        recorded.append(fact.measurement)
    if found.type_id:
        changes.apply(draft_id, DecisionChange(kind="input", subject=found.type_id, value=True),
                      who=who)
    return recorded
