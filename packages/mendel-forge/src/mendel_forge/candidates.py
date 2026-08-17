"""What a hole will accept, read off the layer stack rather than hard-coded.

**This is invariant 7 moved earlier.** Vocabularies are closed: a contract naming an
undeclared state fails to load. A hole carrying its legal values turns that load-time
refusal into a fill-time one — and, from Phase 2, turns an open prompt into a closed
choice. A model asked *"which of these nine types"* cannot invent a tenth.

**An unknown field yields no candidates rather than raising.** A contract gaining a field
before this module knows about it must degrade to free text, not to a crash: the forge is
the thing that keeps working while the registry moves.
"""

import re

from mendel_resolver.layers import Layers

from mendel_forge.scaffold import Candidate

_INDEX = re.compile(r"\[\d+\]")


def _base(field: str) -> str:
    """`produces[0].type_id` and `consumes[2].type_id` ask the same question."""
    return _INDEX.sub("[]", field)


def for_field(field: str, stack: Layers, *, type_id: str | None = None) -> list[Candidate]:
    base = _base(field)

    if base.endswith("type_id"):
        return [
            Candidate(value=name, note="declared type") for name in sorted(stack.vocabulary.types)
        ]

    if base == "roles":
        return [Candidate(value=name, note="declared role") for name in sorted(stack.roles.names)]

    if base.endswith("state") or base.endswith("state_required"):
        if type_id is None:
            return []
        return [
            Candidate(value=state, note=f"state of {type_id}")
            for state in sorted(stack.vocabulary.states_for(type_id))
        ]

    return []
