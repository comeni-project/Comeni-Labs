"""A proposal becoming candidate files, through the machinery a human fill already uses.

**A model's answer goes in through `Scaffold.fill`, exactly as a curator's does.** The two
differ in one argument — `ValueSource.MODEL` rather than `ValueSource.HUMAN` — and in nothing
else, which is what keeps `human_override` meaning what it says. A separate path for the model
would be a second set of rules about what a legal fill is, and the two would drift in the
direction that makes the model's work easier to accept.

**A response never chooses a destination.** Every path here is computed from the adaptation id
by `bundle.joined`; `schemas.py` has no field that could hold one and a test says so. This
module composes text and returns it — `Workspace.write_bundle` is still the only writer, so
the write boundary stays at the two it has had since Task 5.

**Answering a hole is addressed by id and applied by pointer.** `bundle.derive` deliberately
left the scaffold's two spellings unconverted — `open` holds stable hole ids and `filled` is
keyed by `assemble`'s field names — with a note that Task 6 would convert them back. This is
that conversion, in one function, so there is one place where the two vocabularies meet.
"""

import re
from collections.abc import Sequence

from comeni_core.diagnostics import coded
from comeni_core.review import ValueSource

from mendel_forge.ai.schemas import Proposal
from mendel_forge.hole_manifest import ScaffoldHole
from mendel_forge.modulegen import INPUT_HOLE, OUTPUT_HOLE, SCRIPT_HOLE, open_sections
from mendel_forge.scaffold import Scaffold

_POINTER_PORT = re.compile(r"^/(consumes|produces)/(\d+)/(\w+)$")
_POINTER_PLAIN = re.compile(r"^/(\w+)$")


def field_for(pointer: str) -> str:
    """`/consumes/0/type_id` -> `consumes[0].type_id`; `/roles` -> `roles`.

    The one place the hole vocabulary and the scaffold vocabulary meet. They are two spellings
    because they answer two questions — a hole id has to survive a channel being added
    upstream, and a field name has to be the key `assemble.contract_from` reads — and fusing
    them is the defect `consumes[0].type_id` as an *id* already was.
    """
    if port := _POINTER_PORT.match(pointer):
        group, index, field = port.groups()
        return f"{group}[{index}].{field}"
    if plain := _POINTER_PLAIN.match(pointer):
        return plain.group(1)
    raise ValueError(
        f"{pointer!r} is not a pointer this scaffold can address. "
        "A hole's pointer is either /<field> or /<group>/<index>/<field>; anything else "
        "addresses a document shape `assemble` does not produce."
    )


def apply(
    scaffold: Scaffold,
    proposal: Proposal,
    *,
    holes: Sequence[ScaffoldHole],
    by: str,
) -> Scaffold:
    """Every answer filled in, in a deterministic order, attributed to the model.

    `by` is the model identifier rather than a person — `ValueSource.MODEL` and a name is what
    `model_override_by` was added for, and a pipeline an agent assembled must not read as one a
    person drew by hand.

    **Unresolved items are not filled and not recorded as failures.** The hole stays open, which
    is what a curator then sees on the review page: the question, the model's `needed_evidence`,
    and the same *Ask* it had before. That is the honest state and it is the one §5.4 asks the
    model to choose when evidence runs out.
    """
    by_id = {hole.id: hole for hole in holes}
    updated = scaffold
    for answer in sorted(proposal.analysis.answers, key=lambda a: a.hole_id):
        hole = by_id.get(answer.hole_id)
        if hole is None:
            raise ValueError(
                coded("MF0402", f"nothing to apply {answer.hole_id!r} to")
                + "\n  `admit()` should have refused this response before it reached rendering"
            )
        updated = updated.fill(
            field_for(hole.pointer),
            answer.value,
            ValueSource.MODEL,
            by=by,
            why=answer.reason or f"proposed from {', '.join(answer.evidence_ids) or 'no evidence'}",
        )
    return updated


_SECTIONS = {
    "input_block": INPUT_HOLE,
    "output_block": OUTPUT_HOLE,
    "script": SCRIPT_HOLE,
}
"""Which response field replaces which marker.

Keyed by the response field so a marker with no answer is simply not substituted, and the
module keeps its `MF0005`/`MF0011` comment. **An empty section must stay a marked hole**: an
empty `script:` is a process that runs nothing and reports success, which is the failure a stub
gate cannot see either.
"""


def module_text(skeleton: str, proposal: Proposal) -> str:
    """The generated module with the model's sections substituted for their markers.

    Substitution rather than regeneration. The skeleton carries the container reference, the
    process name and the directives that were *derived*, and a model returning whole module
    text could quietly move any of them — the diff a reviewer reads would then be against
    nothing.

    Returns the skeleton unchanged when there is no module proposal, so a caller does not have
    to branch on it.
    """
    if proposal.module is None:
        return skeleton
    text = skeleton
    for field, marker in _SECTIONS.items():
        body = getattr(proposal.module, field)
        if body.strip() and marker in text:
            # **`split`/`join` rather than `str.replace`**, and it is the third time in this
            # repository. `tests/guards/test_forge_write_boundary.py` is an AST scan, so it
            # cannot tell `str.replace` from `Path.replace` — and teaching it to would mean
            # inferring types in a guard whose whole value is that it is blunt and unfoolable.
            # Spelling it this way costs one line; weakening the guard costs the boundary.
            text = body.strip().join(text.split(marker))
    return text


def still_open(module: str) -> tuple[str, ...]:
    """Which markers survived. `modulegen.open_sections` is the implementation.

    Re-exported rather than reimplemented, because a rung that scanned for two of three would
    pass a module whose outputs were still a guess — and it would pass silently, which is the
    shape of defect the whole marker scheme exists to prevent.
    """
    return open_sections(module)
