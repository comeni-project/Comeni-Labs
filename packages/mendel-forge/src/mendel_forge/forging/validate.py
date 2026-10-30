"""Check a reply's items against the registry and the module before anything is stored (§3).

A model's reply is validated where it arrives, even if the provider enforced a schema: every id
must name a registry entry, vocabulary this adaptation proposes, or *pending* vocabulary from an
assembled adaptation; ports must exist in the module's `main.nf`; a setting must be passed
somewhere. Anything else is a coded problem, and the reply is never a proposal.
"""

from dataclasses import dataclass

from comeni_core.declared.contract import NfInput
from mendel_compiler.modulespec import ModuleSpec
from mendel_resolver.layers import Layers
from pydantic import JsonValue

from mendel_forge.model import Problem


@dataclass(frozen=True)
class Known:
    types: frozenset[str]
    roles: frozenset[str]
    measurements: frozenset[str]
    contracts: frozenset[str]
    pending: frozenset[str] = frozenset()
    """Ids from assembled adaptations, usable here and tagged as pending."""


def known(stack: Layers, pending: frozenset[str] = frozenset()) -> Known:
    return Known(
        types=frozenset(stack.vocabulary.types),
        roles=frozenset(stack.roles.names),
        measurements=frozenset(stack.measurements.measurements),
        contracts=frozenset(c.id for c in stack.registry.all()),
        pending=pending,
    )


def _own(items: dict[str, JsonValue], family: str) -> frozenset[str]:
    """Ids this adaptation proposes itself (`vocabulary:type:<id>` …)."""
    prefix = f"vocabulary:{family}:"
    return frozenset(k.removeprefix(prefix) for k in items if k.startswith(prefix))


def _referenced(items: dict[str, JsonValue]) -> dict[str, set[str]]:
    types = {v["type_id"] for k, v in items.items()
             if k.startswith(("contract:input:", "contract:output:"))
             and isinstance(v, dict) and v.get("type_id")}
    process = items.get("contract:process")
    roles = set(process.get("roles", [])) if isinstance(process, dict) else set()
    return {"types": types, "roles": roles}


def pending_used(items: dict[str, JsonValue], seen: Known) -> set[str]:
    """The pending ids the items use: what this adaptation will depend on."""
    used = _referenced(items)
    return (used["types"] | used["roles"]) & seen.pending


def check_items(
    items: dict[str, JsonValue], seen: Known, module: ModuleSpec
) -> list[Problem]:
    problems: list[Problem] = []
    used = _referenced(items)
    for type_id in sorted(used["types"]):
        if type_id not in seen.types | seen.pending | _own(items, "type"):
            problems.append(Problem(code="MF0507", says=f"type {type_id!r} is not in the "
                                    "registry, pending, or proposed here"))
    for role in sorted(used["roles"]):
        if role not in seen.roles | seen.pending | _own(items, "role"):
            problems.append(Problem(code="MF0507", says=f"role {role!r} is not in the registry, "
                                    "pending, or proposed here"))
    inputs = {name for slot in module.inputs for name in slot.names}
    for key in sorted(k for k in items if k.startswith("contract:input:")):
        name = key.removeprefix("contract:input:")
        if name not in inputs:
            problems.append(Problem(code="MF0508", says=f"input {name!r}: {module.process}'s "
                                    "main.nf takes no input by that name"))
    for key in sorted(k for k in items if k.startswith("contract:output:")):
        name = key.removeprefix("contract:output:")
        if name not in module.emits:
            problems.append(Problem(code="MF0508", says=f"output {name!r}: {module.process}'s "
                                    "main.nf emits nothing by that name"))
    wired = {i.param for i in _nf_inputs(items) if i.param}
    for key in sorted(k for k in items if k.startswith("parameters:param:")):
        param = items[key] if isinstance(items[key], dict) else {}
        via, name = param.get("via"), key.removeprefix("parameters:param:")
        if (via == "ext" and not param.get("key")) or (via == "positional" and name not in wired):
            problems.append(Problem(code="MF0509", says=f"setting {name!r} is passed nowhere: "
                                    "give its ext key, or wire it as an input"))
    return problems


def _nf_inputs(items: dict[str, JsonValue]) -> list[NfInput]:
    raw = items.get("contract:nf_inputs") or []
    return [NfInput(**entry) for entry in raw if isinstance(entry, dict)]
