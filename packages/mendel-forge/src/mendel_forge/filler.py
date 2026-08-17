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

from mendel_ai.choice import (
    Option,
    Proposed,
    choose_many,
    choose_one,
    choose_or_propose,
    suggest,
)
from mendel_ai.client import Client

from mendel_forge.observe import Observation
from mendel_forge.scaffold import FilledValue, Filler, Hole, Proposal

_LIST_VALUED = ("roles",)
"""Fields holding several members of one closed set.

Kept beside `_LIST_SUFFIXES` and mirroring `candidates.for_field`'s dispatch, so a field added
to one is visibly missing from the other. `Hole.legal` checks these member by member, which is
why they need `choose_many` rather than `choose_one`.
"""

_LIST_SUFFIXES = ("state", "state_required")

_MAY_PROPOSE = ("type_id",)
"""Fields whose answer may legitimately not exist yet.

**Only `type_id` for now**, because that is where the failure was measured and because it is a
single-valued choice from a closed vocabulary — the shape `choose_or_propose` handles. `roles`
is also a closed vocabulary and a new role is also proposable, but it is list-valued and
"propose one member of a set while choosing others" is a different question that nothing has
asked yet. Widening this is a change with a measurement behind it, not a guess.

A port *name* is deliberately absent: it is not a vocabulary, and since its candidates now come
from the type_id there is always a reachable right answer.
"""


def _may_propose(field: str) -> bool:
    return field.rsplit(".", 1)[-1] in _MAY_PROPOSE


def _is_list_valued(field: str) -> bool:
    base = field.rsplit(".", 1)[-1]
    return field in _LIST_VALUED or base in _LIST_VALUED or base.endswith(_LIST_SUFFIXES)


class ModelFiller:
    """Phase 2's implementation of `HoleFiller`."""

    def __init__(self, client: Client, model_id: str) -> None:
        self.client = client
        self.model_id = model_id

    def fill(self, hole: Hole, observation: Observation) -> FilledValue | Proposal | None:
        if not hole.candidates:
            return None

        options = [Option(value=c.value, note=c.note) for c in hole.candidates]
        # **The hole's own evidence, not the whole observation.** `assemble` narrows a port's
        # evidence to that port's documentation; appending `observation.prose` again put every
        # other port back and was how `star/align` came to send ~13,000 characters per question.
        evidence = [f"{e.locator}: {e.text}" for e in hole.evidence]
        # **`why_open` is sent.** It was not, and it is where the scaffold explains the actual
        # judgement — for a port name it says the contract's name and the module's channel name
        # are different choices, which is the distinction three of the measured misses got
        # wrong while the sentence explaining it sat unused in the Hole.
        question = "\n\n".join(
            [
                f"{hole.what}.",
                f"Why this is a judgement rather than something readable: {hole.why_open}.",
                f"You are filling the field {hole.field} of a Mendel module contract "
                f"for the tool {observation.ref_id}.",
            ]
        )
        if _is_list_valued(hole.field):
            question += (
                "\n\nChoose the smallest set that is true of this tool. "
                "Do not add a value merely because the tool touches it."
            )

        value: object
        if not hole.closed:
            # **Suggested, not restricted.** A port name is not a vocabulary, so the candidates
            # are examples of what this registry calls such a port and the model may answer
            # something else. Closing it made `multiqc`'s `reports` unreachable — a legal name
            # that was simply not on a list this codebase invented.
            answered = suggest(self.client, question, options, evidence)
            if answered is None:
                return None
            value, why = answered.value, answered.why
        elif _may_propose(hole.field):
            # **The one hole where "none of these" is a real answer.** A type_id is chosen from
            # a closed vocabulary, and for a tool nobody has written a contract for the right
            # type routinely does not exist yet — `star/align` emits nineteen channels and the
            # vocabulary can type one of them. Forcing a pick there produces a wrong type, and a
            # wrong type routes. Spec §3.1.
            answered = choose_or_propose(
                self.client, question, options, evidence, proposing="a new declared type"
            )
            if answered is None:
                return None
            if isinstance(answered, Proposed):
                return Proposal(
                    id=answered.id,
                    description=answered.description,
                    why=answered.why,
                    by=self.model_id,
                )
            value, why = answered.value, answered.why
        elif _is_list_valued(hole.field):
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
