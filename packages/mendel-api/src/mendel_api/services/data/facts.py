"""**Facts about the data are derived, not decided** (#511, Checkpoint A).

What the kept samples measured is a fact about the data the analysis has now, so it is read from
the analysis's data every time decisions are read, never written to the decision log. Change the
folders and the facts change; nothing has to be withdrawn. The log keeps choices: what a person
or the AI said, which stands over what the data measured, and is marked whose it is.

- A measurement every kept sample made, with one value, is MEASURED.
- One they made with different values VARIES: each sample keeps its own, for the run to use.
- One some sample did not make is left open, to be asked.
- Each kind of data the kept samples are is an input the analysis has.
"""

from mendel_authoring.decisions import FactDecision, FactOrigin, InputDecision


def derive(samples: list[dict]) -> tuple[list[FactDecision], list[InputDecision]]:
    """The facts and inputs the kept `samples` (as `analysis_data` stores them) establish.

    **Each fact over the samples of the kinds that measure it** (Checkpoint B): a genome among
    reads does not erase the reads' read length. A fact keeps the pieces that measured it, so the
    pipeline file says which measurer answered."""
    kept = [s for s in samples if not s.get("left_out")]
    if not kept:
        return [], []
    measured: dict[str, list[tuple[str | None, dict]]] = {}
    for s in kept:
        for fact in s.get("facts", []):
            if fact.get("value") is not None:
                measured.setdefault(fact["measurement"], []).append((s.get("type_id"), fact))
    facts = []
    for subject in sorted(measured):
        found = measured[subject]
        kinds = {kind for kind, _ in found}
        among = [s for s in kept if s.get("type_id") in kinds]
        if len(found) != len(among):
            continue  # some sample of these kinds did not measure it: open, to be asked
        values = {repr(f["value"]) for _, f in found}
        pieces = sorted({p for _, f in found for p in f.get("pieces", [])})
        facts.append(FactDecision(subject=subject, value=found[0][1]["value"],
                                  origin=FactOrigin.MEASURED, pieces=pieces)
                     if len(values) == 1
                     else FactDecision(subject=subject, origin=FactOrigin.VARIES))
    kinds = sorted({s["type_id"] for s in kept if s.get("type_id")})
    inputs = [InputDecision(key=kind, type_id=kind, present=True, origin=FactOrigin.MEASURED)
              for kind in kinds]
    return facts, inputs


_SAID = (FactOrigin.PERSON_SAID, FactOrigin.MODEL_READ, FactOrigin.VARIES)
"""What a person (or the AI, for them) said about a fact: it stands over the data's. **Not
`open`**: that is what retracting an override writes, and a retraction lets the data speak
again (Checkpoint B). Scans write no decision, so a decided `varies` is always someone's word."""


def _beside(said: FactDecision, data: FactDecision | None) -> FactDecision:
    """A said fact with what the data measured beside it, when the two disagree (#510). Only a
    person's word: the AI may not contradict the data (`changes`, MI0228), and a `varies` has
    no value to compare."""
    if (data is None or data.origin is not FactOrigin.MEASURED
            or said.origin is not FactOrigin.PERSON_SAID or data.value == said.value):
        return said
    return said.model_copy(update={"measured": data.value})


def merge(decided_facts, decided_inputs, samples, references=()):
    """Decided facts and inputs with the data's beside them: a fact someone said stands; one the
    data measured replaces an older measured one; an input decided either way stands."""
    facts, inputs = derive(samples)
    have = {i.type_id for i in inputs}
    for kind in sorted({r["type_id"] for r in references} - have):
        inputs.append(InputDecision(key=kind, type_id=kind, present=True,
                                    origin=FactOrigin.MEASURED))
        have.add(kind)
    said = {f.subject: f for f in decided_facts if f.origin in _SAID}
    derived = {f.subject: f for f in facts}
    # A person's word stands over the data's, and when they disagree both are kept (#510).
    decided_facts = [_beside(f, derived.get(f.subject)) if f.subject in said else f
                     for f in decided_facts]
    merged = [f for f in decided_facts if f.subject in said or f.subject not in derived]
    merged += [f for s, f in derived.items() if s not in said]
    # An input decided either way stands, except one forgotten (`open`): the data says it again.
    decided_inputs = [i for i in decided_inputs
                      if not (i.origin is FactOrigin.OPEN and i.type_id in have)]
    decided_types = {i.type_id for i in decided_inputs}
    return (sorted(merged, key=lambda f: f.subject),
            [*decided_inputs, *[i for i in inputs if i.type_id not in decided_types]])
