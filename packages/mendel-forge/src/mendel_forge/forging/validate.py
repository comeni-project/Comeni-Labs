"""Check a reply's items against the registry and the module before anything is stored (§3).

A model's reply is validated where it arrives, even if the provider enforced a schema: every id
must name a registry entry, vocabulary this adaptation proposes, or *pending* vocabulary from an
assembled adaptation; ports must exist in the module's `main.nf`; a setting must be passed
somewhere. Anything else is a coded problem, and the reply is never a proposal.
"""

from dataclasses import dataclass, field

from comeni_core.declared.contract import NfInput
from comeni_core.declared.signature import split
from comeni_core.declared.tooltest import TestDraft
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
    states: dict[str, frozenset[str]] = field(default_factory=dict)
    pending: frozenset[str] = frozenset()
    """Ids from assembled adaptations, usable here and tagged as pending."""


def known(stack: Layers, pending: frozenset[str] = frozenset()) -> Known:
    return Known(
        types=frozenset(stack.vocabulary.types),
        states=dict(stack.vocabulary.types),
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
    types = {split(v["type_id"])[0] for k, v in items.items()
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
    for key in sorted(k for k in items if k.startswith(("contract:input:", "contract:output:"))):
        value = items[key] if isinstance(items[key], dict) else {}
        if value.get("name") != key.rsplit(":", 1)[1]:
            problems.append(Problem(code="MF0508", says=f"{key} names its port "
                                    f"{value.get('name')!r}: a port's item and name agree"))
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
    return [*problems, *_signature_problems(items, seen), *_test_problems(items, seen)]


def _names(items: dict[str, JsonValue], prefix: str) -> set[str]:
    return {k.removeprefix(prefix) for k in items if k.startswith(prefix)}


def _test_problems(items: dict[str, JsonValue], seen: Known) -> list[Problem]:
    """A test must fit the contract as it stands: every port fed, every output accounted for."""
    takes, makes = _names(items, "contract:input:"), _names(items, "contract:output:")
    settings = _names(items, "parameters:param:")
    problems: list[str] = []
    for key in sorted(k for k in items if k.startswith("tests:test:")):
        test = TestDraft.model_validate(items[key])
        fed = {port for step in test.setup for port in step.feeds.values()}
        for port in sorted(set(test.inputs) - takes):
            problems.append(f"{key}: input {port!r} is not a port of this contract")
        for port in sorted(fed - takes):
            problems.append(f"{key}: a setup step feeds {port!r}, not a port of this contract")
        for port in sorted(takes - set(test.inputs) - fed):
            problems.append(f"{key}: nothing feeds input {port!r}")
        for name in sorted(set(test.params) - settings):
            problems.append(f"{key}: setting {name!r} is not one this contract declares")
        for step in test.setup:
            if step.tool not in seen.contracts | seen.pending:
                problems.append(f"{key}: setup tool {step.tool!r} is not registered or pending")
        expected = {e.port for e in test.expect}
        for port in sorted(expected - makes):
            problems.append(f"{key}: output {port!r} is not a port of this contract")
        for port in sorted(makes - expected - set(test.unchecked)):
            problems.append(f"{key}: output {port!r} is neither expected nor given a reason")
    return [Problem(code="MF0507", says=says) for says in problems]


def _nf_inputs(items: dict[str, JsonValue]) -> list[NfInput]:
    raw = items.get("contract:nf_inputs") or []
    return [NfInput(**entry) for entry in raw if isinstance(entry, dict)]


def _signature_problems(items: dict[str, JsonValue], seen: Known) -> list[Problem]:
    problems = []
    allowed = dict(seen.states)
    for key, value in items.items():
        if key.startswith("vocabulary:type:") and isinstance(value, dict):
            identifier = key.removeprefix("vocabulary:type:")
            allowed[identifier] = (allowed.get(identifier, frozenset()) |
                frozenset(value.get("add_states", value.get("states", []))))
    # An explicit answer may be carried into a contract draft before the vocabulary piece.
    # Assembly still loads the layer and refuses it until its vocabulary is declared.
    for key, value in items.items():
        if (key.startswith(("questions:input_type:", "questions:output_type:"))
                and isinstance(value, dict) and value.get("new") and value.get("choice")):
            identifier, states = split(value["choice"])
            allowed[identifier] = allowed.get(identifier, frozenset()) | states
    for key, value in items.items():
        if not isinstance(value, dict):
            continue
        signatures = []
        if key.startswith(("contract:input:", "contract:output:")):
            signatures = [(value.get("type_id", ""), False)]
        elif key.startswith(("questions:input_type:", "questions:output_type:")):
            options = value.get("options", [])
            signatures = [(o["id"], o.get("new", False)) for o in options]
            if value.get("suggested") and value["suggested"] not in {o["id"] for o in options}:
                problems.append(Problem(code="MF0507",
                    says=f"{key}: suggestion is not an offered option"))
        for signature, new in signatures:
            try:
                identifier, states = split(signature)
                if new:
                    continue
                if identifier not in seen.types | seen.pending | _own(items, "type"):
                    if key.startswith("contract:"):
                        continue  # The reference check above already reports this type.
                    raise ValueError(f"{signature!r} is not declared; mark a new option as new")
                if not states <= allowed.get(identifier, frozenset()):
                    raise ValueError(f"{signature!r} has undeclared states; "
                                     "propose vocabulary for review")
            except ValueError as error:
                problems.append(Problem(code="MF0507", says=f"{key}: {error}"))
    return problems
