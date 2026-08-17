"""A model, behind the `HoleFiller` seam.

**Candidate-bearing holes only.** A hole with candidates is checkable: the candidates come off
the layer stack, and `Hole.legal` refuses anything outside them. A hole without them is free
text, nothing can check it, and the one such value that reaches the registry —
`priority_because` — is gated by issue #70. This filler does not ask about them at all, which
is stronger than asking and discarding: no prose about them ever leaves.

**Validated twice, deliberately.** `choose_*` refuses a value the model was not offered, and
`hole.legal` refuses it again here. That is not redundancy — the second is the check a person's
fill already goes through, and routing a model's answer through it means one rule rather than
two that drift.

**`None` is a normal answer.** A hole a model declines is a hole a person still sees, which is
`ports.py`'s point and the reason the return type has always been optional.
"""

from mendel_ai.choice import Option, choose_many, choose_one
from mendel_ai.client import Client

from mendel_forge.observe import Observation
from mendel_forge.scaffold import FilledValue, Filler, Hole

_LIST_VALUED = ("roles",)
"""Fields holding several members of one closed set.

Kept beside `_LIST_SUFFIXES` and mirroring `candidates.for_field`'s dispatch, so a field added
to one is visibly missing from the other. `Hole.legal` checks these member by member, which is
why they need `choose_many` rather than `choose_one`.
"""

_LIST_SUFFIXES = ("state", "state_required")


def _is_list_valued(field: str) -> bool:
    base = field.rsplit(".", 1)[-1]
    return field in _LIST_VALUED or base in _LIST_VALUED or base.endswith(_LIST_SUFFIXES)


class ModelFiller:
    """Phase 2's implementation of `HoleFiller`."""

    def __init__(self, client: Client, model_id: str) -> None:
        self.client = client
        self.model_id = model_id

    def fill(self, hole: Hole, observation: Observation) -> FilledValue | None:
        if not hole.candidates:
            return None

        options = [Option(value=c.value, note=c.note) for c in hole.candidates]
        evidence = [f"{e.locator}: {e.text}" for e in (*hole.evidence, *observation.prose)]
        question = f"{hole.what}\n\nThis is the field {hole.field} of a Mendel module contract."

        value: object
        if _is_list_valued(hole.field):
            many = choose_many(self.client, question, options, evidence)
            if many is None:
                return None
            value, why = many.values, many.why
        else:
            one = choose_one(self.client, question, options, evidence)
            if one is None:
                return None
            value, why = one.value, one.why

        if not hole.legal(value):
            return None
        return FilledValue(value=value, filler=Filler.MODEL, by=self.model_id, why=why)
