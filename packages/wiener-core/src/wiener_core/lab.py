"""The mark on a field a laboratory's own words reach (`LabString`), on its own so any payload
module can use it."""

from typing import Final, final


@final
class LabString:
    """Marks a field a laboratory's own words reach. §10.2's redactor filters on this, and §8
    forbids one becoming a span attribute.

    A sentinel **type** rather than a bare `"lab-string"` — A182. The marking is load-bearing:
    §10.2's claim is that a marked field added later *cannot* be missed, because the totality
    test fails rather than the data leaking. A string is spellable by accident and collides
    with any other `Annotated[str, "lab-string"]`; an instance of a private class is neither.

    It is deliberately **not** `comeni_core.spell.Mark` — widening that enum pulls in the
    egress accounting invariant 14 keeps, for a marking that never crosses a Mendel door.
    """


LAB_STRING: Final = LabString()
