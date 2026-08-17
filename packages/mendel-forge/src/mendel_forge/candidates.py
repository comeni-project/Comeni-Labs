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


def for_field(
    field: str,
    stack: Layers,
    *,
    type_id: str | None = None,
    channels: tuple[str, ...] = (),
) -> list[Candidate]:
    base = _base(field)

    if base.endswith("type_id"):
        return [
            Candidate(value=name, note="declared type") for name in sorted(stack.vocabulary.types)
        ]

    if base.endswith("name"):
        # **A port's name comes from its type, not only from its channel.** Twenty-four of the
        # thirty shipped ports are named after a segment of their own `type_id` — `bam` from
        # `alignment.bam`, `index` from `genome.index.star`, `counts` from `counts.matrix` —
        # and the module's channel name is often something else entirely (`multiqc_files`,
        # `bams`, `input`). Offering only the channel names meant `multiqc` was handed one
        # candidate and it was the wrong one, so the answer could not be reached at all.
        #
        # Returns nothing when the type is unknown, which is why the name hole is asked *after*
        # the type hole and its candidates recomputed in between. `channels` carries what the
        # module calls it, since that is sometimes right and always worth offering.
        if type_id is None:
            return [Candidate(value=name, note="the module's channel name") for name in channels]
        segments = [part for part in type_id.split(".") if part]
        offered = {name: "the module's channel name" for name in channels}
        for part in segments:
            offered.setdefault(part, f"from the type {type_id}")
            offered.setdefault(f"{part}s", f"from the type {type_id}, plural")
        return [Candidate(value=v, note=n) for v, n in offered.items()]

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
