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
    excluding: str | None = None,
) -> list[Candidate]:
    base = _base(field)

    if base.endswith("type_id"):
        carried = _carried_by(stack, excluding)
        return [
            Candidate(value=name, note=_note("declared type", carried.get(name, ())))
            for name in sorted(stack.vocabulary.types)
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
        # **What other contracts already call a port of this type.** The decisive evidence:
        # asked what to call an `alignment.bam` input, "other contracts call this bam" answers
        # it outright, where "the module's channel name is bams" invites the channel name —
        # which is what the model kept picking. Same source as the role exemplars, and for the
        # same reason: a port name is a convention of this registry, not a fact about the tool.
        # **Order matters, and the first version had it backwards.** The module's channel name
        # was listed first and chosen every time across three tools — `input`, `bams`,
        # `multiqc_files` — while the right answer sat below it. Position bias is real and it
        # was pointing at the wrong candidate, so the registry's own convention leads now and
        # the channel name comes last.
        offered: dict[str, str] = {}
        for name in _named_by(stack, type_id, excluding):
            offered[name] = f"what other contracts call an {type_id} port"
        for part in [p for p in type_id.split(".") if p]:
            offered.setdefault(part, f"from the type {type_id}")
            offered.setdefault(f"{part}s", f"from the type {type_id}, plural")
        for name in channels:
            offered.setdefault(name, "the module's internal channel name")
        return [Candidate(value=v, note=n) for v, n in offered.items()]

    if base == "roles":
        played = _played_by(stack, excluding)
        return [
            Candidate(value=name, note=_note("declared role", played.get(name, ())))
            for name in sorted(stack.roles.names)
        ]

    if base.endswith("state") or base.endswith("state_required"):
        if type_id is None:
            return []
        return [
            Candidate(value=state, note=f"state of {type_id}")
            for state in sorted(stack.vocabulary.states_for(type_id))
        ]

    return []


_EXEMPLARS = 3
"""How many existing users to name beside a candidate.

Enough to show the pattern, few enough that twenty-two types do not bury the question. An
oversized prompt does not degrade gracefully — it gets its instruction ignored, which is how
`star/align` came to be answered with an essay about YAML.
"""


def _tool(contract_id: str) -> str:
    """`nf-core/hisat2/build@1.0` -> `hisat2/build`.

    The namespace goes and the rest stays: bare leaf names are ambiguous exactly where it
    matters — `align` is both HISAT2 and STAR, and `build`, `index` and `sort` say nothing.
    """
    without_version = contract_id.split("@")[0]
    parts = without_version.split("/")
    return "/".join(parts[1:]) if len(parts) > 1 else without_version


def _note(kind: str, users: "tuple[str, ...] | list[str]") -> str:
    """A candidate, and who already uses it.

    **A role is a judgement about the registry, not a fact about the tool** — `_WHY_OPEN`
    says so — and until now the evidence offered was the tool's own documentation, which
    cannot answer it. `meta.yml` describes what STAR does; it says nothing about how this
    registry partitions work into roles.

    Naming existing users is the evidence that does answer it: `index_building` beside
    `hisat2/build, star/genomegenerate` is visibly about building genome indexes rather than
    indexing anything, which is the distinction `samtools/index` was measured getting wrong.

    Everything here was already loaded. `Candidate.note` already reaches the prompt through
    `Option.note`. Nothing new is fetched, computed twice or plumbed.
    """
    if not users:
        # **Neutral, not "nothing uses it yet".** That phrasing is accurate and reads as
        # discouragement, and the case where it appears most is exactly the case where it
        # would mislead: drafting `samtools/index` excludes itself, so `bam_indexing` — the
        # right answer — is the one with no other user. An exemplar list should disambiguate
        # candidates, never rank them.
        return kind
    shown = sorted(set(users))
    more = len(shown) - _EXEMPLARS
    listed = ", ".join(shown[:_EXEMPLARS]) + (f", +{more} more" if more > 0 else "")
    return f"{kind} — used by {listed}"


def _played_by(stack: Layers, excluding: str | None = None) -> dict[str, list[str]]:
    """Role -> the tools that declare it, never counting the tool being drafted.

    **`excluding` is not an optimisation, it is what makes the exemplars honest.** Re-drafting
    a tool that is already in the registry would otherwise offer
    `bam_indexing — used by samtools/index` while asking what role `samtools/index` plays: the
    answer, in the prompt. Every accuracy figure measured that way would be meaningless.

    It also matches reality rather than merely protecting a measurement. The case the forge
    exists for is a tool nobody has written a contract for, and such a tool is not in the
    registry to cite itself.
    """
    found: dict[str, list[str]] = {}
    for contract in stack.registry.contracts.values():
        if excluding and contract.id.split("@")[0] == excluding:
            continue
        for role in contract.roles:
            found.setdefault(role, []).append(_tool(contract.id))
    return found


def _carried_by(stack: Layers, excluding: str | None = None) -> dict[str, list[str]]:
    """Type -> the tools with a port of that type, on either side.

    Both sides on purpose: a type is as much characterised by what consumes it as by what
    produces it, and `annotation.gtf` is only ever consumed here.
    """
    found: dict[str, list[str]] = {}
    for contract in stack.registry.contracts.values():
        if excluding and contract.id.split("@")[0] == excluding:
            continue
        for port in (*contract.consumes, *contract.produces):
            found.setdefault(port.type_id, []).append(_tool(contract.id))
    return found


def _named_by(stack: Layers, type_id: str, excluding: str | None = None) -> list[str]:
    """What existing contracts name their ports of this type, most common first.

    A port name is a convention of this registry — `alignment.bam` is called `bam` in four
    contracts — and until now the only candidate carrying any authority was the module's own
    channel name, which is the one the measurement showed the model wrongly preferring.
    """
    seen: dict[str, int] = {}
    for contract in stack.registry.contracts.values():
        if excluding and contract.id.split("@")[0] == excluding:
            continue
        for port in (*contract.consumes, *contract.produces):
            if port.type_id == type_id:
                seen[port.name] = seen.get(port.name, 0) + 1
    return [name for name, _ in sorted(seen.items(), key=lambda kv: (-kv[1], kv[0]))]
