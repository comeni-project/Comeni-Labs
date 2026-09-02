"""Observation in, scaffold out — and scaffold in, contract out.

Two directions of one mapping, kept in one file because they must agree: a field this
module fills must be a field the other reads, and splitting them is how the two halves of
a serialiser drift apart.

**The mapping is `docs/notes/audits/2026-08-16-forge-derivability.md`, implemented literally.**
That table was measured against every vendored module rather than reasoned about. Where
this file and the table disagree, the table is right.
"""

import re
from typing import Any

import yaml
from comeni_core.declared.contract import InputPort, ModuleContract, OutputPort, Provenance
from comeni_core.declared.layered import DeclaredKind
from comeni_core.diagnostics import coded
from comeni_core.review import ValueSource
from mendel_resolver.layers import Layers

from mendel_forge import candidates
from mendel_forge.observe import Excerpt, Observation
from mendel_forge.scaffold import FilledValue, Hole, Scaffold

_WHY_OPEN = {
    "roles": (
        "a module declares no role — a role is the job it does in a pipeline, "
        "which is a judgement about the registry rather than a fact about the tool"
    ),
    "type_id": (
        "nf-core declares an output as `type: file` with a filename pattern; the "
        "semantic type exists only in the English description"
    ),
    "state": "the same — `sorted` is in the prose, never in the declaration",
    "priority_because": (
        "why this contract ranks where it does is a judgement, and a bare "
        "integer with no reason is the gap audit A128 is about"
    ),
    "nf_process": (
        "this source ships no Nextflow module, so the process name is whatever "
        "the generated one is called"
    ),
}


DERIVED_FIELDS: tuple[tuple[str, str], ...] = (
    ("process", "nf_process"),
    ("nf_include", "nf_include"),
    ("container", "container"),
)
"""Fact name -> contract field, for the fields a source can prove outright.

Named once and read by both `scaffold_for` and `ops.check`, because the two ask the same
question in opposite directions — *what should this field be* and *does this field still
match*. Two copies of this tuple would drift, and the drift would be invisible: `check`
would simply stop noticing a field.

Every entry is a `derived` row in `docs/notes/audits/2026-08-16-forge-derivability.md`. Adding
one here without measuring it there is how an estimate gets back in.
"""


def _derived(value: Any, obs: Observation, name: str) -> FilledValue:
    evidence = obs.facts[name].evidence
    return FilledValue(
        value=value, how=ValueSource.DERIVED, by=obs.source, why=f"read from {evidence.locator}"
    )


def _hole(
    field: str,
    stack: Layers,
    obs: Observation,
    *,
    why: str,
    type_id: str | None = None,
    what: str | None = None,
    port: str | None = None,
    excluding: str | None = None,
) -> Hole:
    """One open field.

    `what` overrides the generic phrasing, and `port` narrows the evidence to that port's own
    documentation. Both exist because the generic form was measured and found wanting: a hole
    reading *"a value for produces[0].type_id"* carrying every port's documentation is a
    question that does not say which port it is about, and a model answered all three of
    `fastqc`'s outputs identically because the prompts differed only in an index digit.
    """
    offered = candidates.for_field(
        field, stack, type_id=type_id, excluding=excluding, port=port, tool=excluding
    )
    return Hole(
        subject=field,
        what=what or f"a value for {field}",
        why_open=why,
        # **`port` reaches the candidates now, not only the evidence.** It has been a parameter
        # of this function since Phase 2 and was spent entirely on `_evidence_for` — so the one
        # fact that says which type a hole is about was present at the call site and thrown
        # away. Alphabetical order was the result: `genome.fasta` sixth of twenty-two for a
        # port literally called `fa`.
        #
        # **`tool=excluding` is one fact used twice, not two that happen to agree.** `excluding`
        # is the module key of the tool being drafted, which is exactly what the ranking needs
        # to know which tool is asking — giving the scorer its own parameter would let the two
        # drift apart silently, and the whole value of signal 3 is that they cannot.
        candidates=offered,
        suggested=candidates.suggestion(offered, port=port, tool=excluding),
        evidence=_evidence_for(obs, port),
    )


def _evidence_for(obs: Observation, port: str | None) -> list[Excerpt]:
    """The tool's description, plus the documentation for one port when one is named.

    **Every hole used to carry every excerpt.** With per-port prose that is both noisy and
    large — `star/align` documents twenty-six ports — and an oversized prompt does not degrade
    gracefully: its instruction gets buried and the model answers a different question. Sending
    a port's own line instead is smaller *and* more relevant, which is the rare change that
    costs nothing to get both.

    Falls back to everything when no port matches, because less evidence is a worse hole and
    an empty one is a useless hole.
    """
    if port is None:
        return list(obs.prose)
    described = [e for e in obs.prose if e.locator.endswith(f".{port}")]
    if not described:
        return list(obs.prose)
    general = [e for e in obs.prose if e.locator.endswith(":description")]
    return [*general, *described]


def scaffold_for(obs: Observation, stack: Layers, *, ident: str, version: str) -> Scaffold:
    filled: dict[str, FilledValue] = {}
    holes: list[Hole] = []

    filled["id"] = FilledValue(
        value=f"{ident}@{version}",
        how=ValueSource.DERIVED,
        by=obs.source,
        why=f"the tool's path and version under {obs.source}",
    )
    filled["provenance.source"] = FilledValue(
        value=obs.source, how=ValueSource.DERIVED, by=obs.source, why="the source it was read from"
    )

    for name, field in DERIVED_FIELDS:
        if obs.fact(name) is not None:
            filled[field] = _derived(obs.fact(name), obs, name)
        else:
            holes.append(
                _hole(field, stack, obs, why=_WHY_OPEN.get(field, "not derivable"),
                      excluding=ident)
            )

    # **One port per module input channel.** Nextflow matches arity, and a contract with no
    # `nf_inputs` gets one channel per `consumes` port — so a draft with no input ports at all
    # declares zero channels for a process that takes some, and MD0102 refuses it at rung 4.
    # The first version of this function omitted these holes entirely, which made
    # `is_complete()` false in the worst way: a draft reporting no holes that could not
    # become a contract. Found by running the documented loop end to end, not by a test.
    #
    # The *name* is a hole with the module's channel names as candidates, because a contract
    # port name is chosen rather than read — four of twelve shipped contracts rename, and
    # `docs/notes/audits/2026-08-16-forge-derivability.md` measures it.
    for index, slot in enumerate(obs.fact("input_names") or []):
        offered = [name for name in slot if not name.startswith("meta")]
        holes.append(
            Hole(
                subject=f"consumes[{index}].name",
                # **The module's channel name is deliberately not repeated here.** It used to
                # be — "the module calls it meta, input" — which named the wrong answer in the
                # question, offered it first, and hoped for something else. That clause dates
                # from Phase 1, when channel names were the only candidates and saying so was
                # the whole of the help. It is one candidate among several now, and the
                # sentence was arguing for it.
                what=f"what this contract calls the thing arriving on channel {index}",
                why_open="a port name says what the channel carries; the module's says what "
                "the process calls it, and the two are not the same choice",
                candidates=candidates.for_field(
                    f"consumes[{index}].name",
                    stack,
                    channels=tuple(offered),
                    excluding=ident,
                ),
                evidence=_evidence_for(obs, offered[0] if offered else None),
                # **Answered after its type, and its candidates recomputed then.** Twenty-four
                # of thirty shipped ports are named after a segment of their own type_id, so
                # until the type is known the right answer may not be offerable at all — which
                # is exactly how `multiqc` came to be handed one candidate and it was wrong.
                after=f"consumes[{index}].type_id",
                channels=tuple(offered),
            )
        )
        # **Name the channel in the question.** `consumes[1]` is an index, and an index is not
        # something a tool's documentation talks about; `index` and `gtf` are. Three of the
        # seven type_id misses measured on 2026-08-17 were second inputs answered with the
        # first input's type, which is what "channel 1" invites when nothing says what it is.
        called = ", ".join(offered) or f"channel {index}"
        holes.append(
            _hole(
                f"consumes[{index}].type_id",
                stack,
                obs,
                why=_WHY_OPEN["type_id"],
                excluding=ident,
                what=f"the semantic type of the input the module calls {called}",
                port=offered[0] if offered else None,
            )
        )

    emits = obs.fact("emits") or []
    for index, emit in enumerate(emits):
        filled[f"produces[{index}].name"] = _derived(emits, obs, "emits").model_copy(
            update={"value": emit}
        )
        holes.append(
            _hole(
                f"produces[{index}].type_id",
                stack,
                obs,
                why=_WHY_OPEN["type_id"],
                excluding=ident,
                what=f"the semantic type of the output the module emits as {emit}",
                port=emit,
            )
        )

    arity = obs.fact("input_arity")
    if arity is not None:
        filled["nf_inputs.arity"] = _derived(arity, obs, "input_arity")

    holes.append(
        _hole(
            "roles",
            stack,
            obs,
            why=_WHY_OPEN["roles"],
            excluding=ident,
            what=_roles_question(stack, ident),
        )
    )
    holes.append(
        _hole(
            "priority_because",
            stack,
            obs,
            why=_WHY_OPEN["priority_because"],
            # **The one hole that named itself instead of asking.** `what` fell through to
            # `f"a value for {field}"` — the placeholder the comment on `_hole` complains
            # about — so the only question in the forge with no candidates to lean on was also
            # the only one with no question in it.
            what=(
                "why this contract should be preferred over another that produces the same "
                "type — routing ranks candidates by priority, and this is the sentence a "
                "reviewer reads when it does"
            ),
        )
    )

    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target=_target(ident),
        observation=obs,
        filled=filled,
        holes=sorted(holes, key=lambda h: h.subject),
    )


def _target(ident: str) -> str:
    """Where the file lands, following the convention the public registry already uses.

    A layer's layout is free — invariant 11 says a file declares its own kind, so nothing
    reads the path. The convention groups a tool's files together, and since Plan 5A it is
    **uniform**, which it was not before:

        nf-core/fastqc         -> tools/nf-core/fastqc/contract.yml
        nf-core/samtools/sort  -> tools/nf-core/samtools/sort/contract.yml

    It used to double a single-segment tool's name — `fastqc/fastqc.contract.yml` — because a
    tool needed a directory of its own and the contract was the only thing in it. A tool now
    carries its `module/` and its `module.yml` too, so the directory is earned rather than
    contrived, and **a contract sits beside the module it is a binding for**.

    FORGE-REWORK — the forge is deferred until its own rework (spec §5) and this is a path
    constant rather than a code path: without it `forge land` writes into a layout the registry
    no longer uses, which is *more* broken than leaving it alone rather than equally broken.
    Whether a landed contract belongs at this path at all is the rework's question.
    """
    source, _, tool = ident.partition("/")
    return f"tools/{source}/{tool}/contract.yml"


_PORT_KEY = re.compile(r"^(consumes|produces)\[(\d+)\]\.(\w+)$")


def _ports(filled: dict[str, Any], group: str) -> list[dict[str, Any]]:
    """Regroup flat `produces[0].type_id` keys back into one dict per index.

    The scaffold is flat on purpose — a hole names one field, and `produces[0].type_id`
    is a field a person can be asked about while `produces` is not. Reassembling here is
    the cost of that, and it is paid in one place.
    """
    by_index: dict[int, dict[str, Any]] = {}
    for key, value in filled.items():
        match = _PORT_KEY.match(key)
        if match and match.group(1) == group:
            by_index.setdefault(int(match.group(2)), {})[match.group(3)] = value
    return [by_index[index] for index in sorted(by_index)]


def _require_complete(scaffold: Scaffold) -> None:
    if scaffold.is_complete():
        return
    open_fields = ", ".join(h.subject for h in sorted(scaffold.holes, key=lambda h: h.subject))
    message = (
        coded("MF0004", f"{scaffold.target} has {len(scaffold.holes)} open hole(s)")
        + f"\n  open: {open_fields}"
    )
    if scaffold.proposed:
        # **A proposal is why a hole is open, not a reason it is closed.** Saying so here is
        # the difference between "somebody has not looked at this" and "the vocabulary cannot
        # express it and here is what it would take" — different work, different reviewer.
        wanted = ", ".join(
            f"{field} wants {p.id!r}" for field, p in sorted(scaffold.proposed.items())
        )
        message += (
            f"\n  {len(scaffold.proposed)} of them propose a new declared entry: {wanted}"
            "\n  approve the entry into the registry first, then fill the hole with it"
        )
    raise ValueError(message)


def _drafted_by(scaffold: Scaffold) -> str:
    """`hand` when a person filled every non-derived hole; the model id when one did.

    Phase 2 needs no change here: `ValueSource.MODEL` already exists and `by` already carries
    the id, so a model-filled scaffold lands with its model named in the file.

    **The `"hand"` is a string literal and must stay one.** It is what `Provenance.drafted_by`
    carries into a landed contract, and it is *not* `ValueSource.HUMAN.value`. That is the
    whole reason Plan 2.5 could fold `Filler.HAND` into `ValueSource.HUMAN` without moving a
    byte of any published registry artifact — the enum never reached one. The spec's §4.3
    first claimed the opposite and was corrected by reading this function.
    """
    sources = {v.how: v.by for v in scaffold.filled.values()}
    return sources.get(ValueSource.MODEL, "hand")


def contract_from(scaffold: Scaffold, *, approved_by: str, approved_at: str) -> ModuleContract:
    _require_complete(scaffold)
    value = {field: filled.value for field, filled in scaffold.filled.items()}

    produces = [
        OutputPort(
            name=port["name"],
            type_id=port["type_id"],
            state=frozenset(port.get("state", [])),
        )
        for port in _ports(value, "produces")
    ]
    consumes = [
        InputPort(
            name=port["name"],
            type_id=port["type_id"],
            state_required=frozenset(port.get("state_required", [])),
        )
        for port in _ports(value, "consumes")
    ]

    return ModuleContract(
        id=value["id"],
        nf_process=value["nf_process"],
        nf_include=value["nf_include"],
        consumes=consumes,
        produces=produces,
        roles=value.get("roles", []),
        priority=value.get("priority", 0),
        priority_because=value.get("priority_because", ""),
        container=value.get("container"),
        provenance=Provenance(
            source=value["provenance.source"],
            drafted_by=_drafted_by(scaffold),
            approved_by=approved_by,
            approved_at=approved_at,
        ),
    )


def to_yaml(scaffold: Scaffold, *, approved_by: str, approved_at: str) -> str:
    """The file as it will land. `declares: contract` first, because that is the line the
    loader reads to know what the file is — comeni-registry#1 retired the directory that
    used to say it, and a misspelled `declares:` is MD0011 rather than an impossibility."""
    contract = contract_from(scaffold, approved_by=approved_by, approved_at=approved_at)
    body = contract.model_dump(mode="json", exclude_defaults=True)
    return "declares: contract\n" + yaml.safe_dump(body, sort_keys=False, width=100)


def _roles_question(stack: Layers, ident: str) -> str:
    """What to ask for `roles`, including how many roles contracts here actually declare.

    **Derived, never asserted.** Every shipped contract declares exactly one role, and the
    measured failure was a model picking two or three — `[alignment, bam_indexing, bam_sorting]`
    for STAR, where a person wrote `[alignment]`. Telling it the observed distribution is
    stronger than telling it to "choose the smallest set", which was tried and did not work.

    Counted from the stack at draft time rather than written into this sentence, because a
    number repeated in prose is a number that goes stale while everything around it stays true
    (A71/A72). If the registry grows a two-role contract this text changes on its own, and it
    stops claiming something that is no longer so.
    """
    others = [c for c in stack.registry.contracts.values() if c.id.split("@")[0] != ident]
    counts = {len(c.roles) for c in others}
    asked = "the job this tool does in a pipeline"
    if counts == {1}:
        return (
            f"{asked} — every one of the {len(others)} contracts in this registry "
            "declares exactly one role"
        )
    if counts:
        return f"{asked} — contracts here declare between {min(counts)} and {max(counts)} roles"
    return asked
