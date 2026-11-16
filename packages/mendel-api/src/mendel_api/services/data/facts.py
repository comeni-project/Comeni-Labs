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
    """The facts and inputs the kept `samples` (as `analysis_data` stores them) establish."""
    kept = [s for s in samples if not s.get("left_out")]
    if not kept:
        return [], []
    measured: list[dict[str, object]] = [
        {f["measurement"]: f.get("value") for f in s.get("facts", []) if f.get("value") is not None}
        for s in kept]
    every = set(measured[0]).intersection(*measured[1:])
    facts = []
    for subject in sorted(every):
        values = {repr(m[subject]) for m in measured}
        facts.append(FactDecision(subject=subject, value=measured[0][subject],
                                  origin=FactOrigin.MEASURED) if len(values) == 1
                     else FactDecision(subject=subject, origin=FactOrigin.VARIES))
    kinds = sorted({s["type_id"] for s in kept if s.get("type_id")})
    inputs = [InputDecision(key=kind, type_id=kind, present=True, origin=FactOrigin.MEASURED)
              for kind in kinds]
    return facts, inputs


_SAID = (FactOrigin.PERSON_SAID, FactOrigin.MODEL_READ, FactOrigin.OPEN)
"""What a person (or the AI, for them) said about a fact: it stands over the data's."""


def merge(decided_facts, decided_inputs, samples, references=()):
    """Decided facts and inputs with the data's beside them: a fact someone said stands; one the
    data measured replaces an older measured one; an input decided either way stands."""
    facts, inputs = derive(samples)
    have = {i.type_id for i in inputs}
    inputs += [InputDecision(key=r["type_id"], type_id=r["type_id"], present=True,
                             origin=FactOrigin.MEASURED)
               for r in references if r["type_id"] not in have and not have.add(r["type_id"])]
    said = {f.subject: f for f in decided_facts if f.origin in _SAID}
    derived = {f.subject: f for f in facts}
    merged = [f for f in decided_facts if f.subject in said or f.subject not in derived]
    merged += [f for s, f in derived.items() if s not in said]
    decided_types = {i.type_id for i in decided_inputs}
    return (sorted(merged, key=lambda f: f.subject),
            [*decided_inputs, *[i for i in inputs if i.type_id not in decided_types]])
