"""Observation in, scaffold out — and scaffold in, contract out.

Two directions of one mapping, kept in one file because they must agree: a field this
module fills must be a field the other reads, and splitting them is how the two halves of
a serialiser drift apart.

**The mapping is `notes/audits/2026-08-16-forge-derivability.md`, implemented literally.**
That table was measured against every vendored module rather than reasoned about. Where
this file and the table disagree, the table is right.
"""

from typing import Any

from comeni_core.declared.layered import DeclaredKind
from mendel_resolver.layers import Layers

from mendel_forge import candidates
from mendel_forge.observe import Observation
from mendel_forge.scaffold import FilledValue, Filler, Hole, Scaffold

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


def _derived(value: Any, obs: Observation, name: str) -> FilledValue:
    evidence = obs.facts[name].evidence
    return FilledValue(
        value=value, filler=Filler.DERIVED, by=obs.source, why=f"read from {evidence.locator}"
    )


def _hole(
    field: str, stack: Layers, obs: Observation, *, why: str, type_id: str | None = None
) -> Hole:
    return Hole(
        field=field,
        what=f"a value for {field}",
        why_open=why,
        candidates=candidates.for_field(field, stack, type_id=type_id),
        evidence=list(obs.prose),
    )


def scaffold_for(obs: Observation, stack: Layers, *, ident: str, version: str) -> Scaffold:
    filled: dict[str, FilledValue] = {}
    holes: list[Hole] = []

    filled["id"] = FilledValue(
        value=f"{ident}@{version}",
        filler=Filler.DERIVED,
        by=obs.source,
        why=f"the tool's path and version under {obs.source}",
    )
    filled["provenance.source"] = FilledValue(
        value=obs.source, filler=Filler.DERIVED, by=obs.source, why="the source it was read from"
    )

    for name, field in (
        ("process", "nf_process"),
        ("nf_include", "nf_include"),
        ("container", "container"),
    ):
        if obs.fact(name) is not None:
            filled[field] = _derived(obs.fact(name), obs, name)
        else:
            holes.append(_hole(field, stack, obs, why=_WHY_OPEN.get(field, "not derivable")))

    emits = obs.fact("emits") or []
    for index, emit in enumerate(emits):
        filled[f"produces[{index}].name"] = _derived(emits, obs, "emits").model_copy(
            update={"value": emit}
        )
        holes.append(_hole(f"produces[{index}].type_id", stack, obs, why=_WHY_OPEN["type_id"]))

    arity = obs.fact("input_arity")
    if arity is not None:
        filled["nf_inputs.arity"] = _derived(arity, obs, "input_arity")

    holes.append(_hole("roles", stack, obs, why=_WHY_OPEN["roles"]))
    holes.append(_hole("priority_because", stack, obs, why=_WHY_OPEN["priority_because"]))

    return Scaffold(
        kind=DeclaredKind.CONTRACTS,
        target=_target(ident),
        observation=obs,
        filled=filled,
        holes=sorted(holes, key=lambda h: h.field),
    )


def _target(ident: str) -> str:
    """Where the file lands, following the convention the public registry already uses.

    A layer's layout is free — invariant 11 says a file declares its own kind, so nothing
    reads the path. The convention groups a tool's files together, and it is **not uniform**:

        nf-core/fastqc         -> tools/nf-core/fastqc/fastqc.contract.yml
        nf-core/samtools/sort  -> tools/nf-core/samtools/sort.contract.yml

    A single-segment tool doubles its name to get a directory of its own; a multi-segment
    one already has one. Read off the shipped registry rather than invented — every id in
    it was checked when this was written.
    """
    source, _, tool = ident.partition("/")
    tail = tool if "/" in tool else f"{tool}/{tool}"
    return f"tools/{source}/{tail}.contract.yml"
