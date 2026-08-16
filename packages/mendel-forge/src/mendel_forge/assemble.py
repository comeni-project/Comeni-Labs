"""Observation in, scaffold out — and scaffold in, contract out.

Two directions of one mapping, kept in one file because they must agree: a field this
module fills must be a field the other reads, and splitting them is how the two halves of
a serialiser drift apart.

**The mapping is `notes/audits/2026-08-16-forge-derivability.md`, implemented literally.**
That table was measured against every vendored module rather than reasoned about. Where
this file and the table disagree, the table is right.
"""

import re
from typing import Any

import yaml
from comeni_core.declared.contract import InputPort, ModuleContract, OutputPort, Provenance
from comeni_core.declared.layered import DeclaredKind
from comeni_core.diagnostics import coded
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

Every entry is a `derived` row in `notes/audits/2026-08-16-forge-derivability.md`. Adding
one here without measuring it there is how an estimate gets back in.
"""


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

    for name, field in DERIVED_FIELDS:
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
    open_fields = ", ".join(h.field for h in sorted(scaffold.holes, key=lambda h: h.field))
    raise ValueError(
        coded("MF0004", f"{scaffold.target} has {len(scaffold.holes)} open hole(s)")
        + f"\n  open: {open_fields}"
    )


def _drafted_by(scaffold: Scaffold) -> str:
    """`hand` when a person filled every non-derived hole; the model id when one did.

    Phase 2 needs no change here: `Filler.MODEL` already exists and `by` already carries
    the id, so a model-filled scaffold lands with its model named in the file.
    """
    fillers = {v.filler: v.by for v in scaffold.filled.values()}
    return fillers.get(Filler.MODEL, "hand")


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
