"""Check a reply's items against the registry and the module before anything is stored (§3).

A model's reply is validated where it arrives, even if the provider enforced a schema: every id
must name a registry entry, vocabulary this adaptation proposes, or *pending* vocabulary from an
assembled adaptation; ports must exist in the module's `main.nf`; a setting must be passed
somewhere. Anything else is a coded problem, and the reply is never a proposal.
"""

import re
from dataclasses import dataclass, field

from comeni_core.declared.contract import InputPort, NfInput, OutputPort
from comeni_core.declared.families import family_of
from comeni_core.declared.signature import join, split
from comeni_core.declared.tooltest import TestDraft
from mendel_compiler.modulespec import ModuleSpec
from mendel_compiler.registry_lint import piece_problems
from mendel_resolver.layers import Layers
from pydantic import JsonValue

from mendel_forge.forging.model import Adaptation, Piece, Status
from mendel_forge.forging.values import Answer, MeasurerDraft
from mendel_forge.model import Problem


@dataclass(frozen=True)
class Known:
    types: frozenset[str]
    roles: frozenset[str]
    measurements: frozenset[str]
    contracts: frozenset[str]
    families: frozenset[str] = frozenset()
    pending_families: frozenset[str] = frozenset()
    states: dict[str, frozenset[str]] = field(default_factory=dict)
    pending: frozenset[str] = frozenset()
    """Ids from assembled adaptations, usable here and tagged as pending."""


def known(stack: Layers, pending: frozenset[str] = frozenset(),
          pending_families: frozenset[str] = frozenset()) -> Known:
    return Known(
        types=frozenset(stack.vocabulary.types),
        states=dict(stack.vocabulary.types),
        roles=frozenset(stack.roles.names),
        measurements=frozenset(stack.measurements.measurements),
        contracts=frozenset(c.id for c in stack.registry.all()),
        pending=pending,
        families=frozenset(stack.families.families),
        pending_families=pending_families,
    )


def _own(items: dict[str, JsonValue], family: str) -> frozenset[str]:
    """Ids this adaptation proposes itself (`vocabulary:type:<id>` …)."""
    prefix = f"vocabulary:{family}:"
    return frozenset(k.removeprefix(prefix) for k in items if k.startswith(prefix))


def validation_items(state: Adaptation) -> dict[str, JsonValue]:
    """Current values for checking drafts; only approved answers can introduce names."""
    return {key: item.value for key, item in state.items.items()
            if item.status is not Status.REMOVED and not (
                item.piece is Piece.QUESTIONS and isinstance(item.value, dict)
                and "choice" in item.value and item.status is not Status.APPROVED)}


def _introduced(items: dict[str, JsonValue]) -> tuple[dict[str, frozenset[str]], set[str]]:
    types: dict[str, frozenset[str]] = {}
    roles: set[str] = set()
    for key, value in items.items():
        if not key.startswith("questions:") or not isinstance(value, dict) or "choice" not in value:
            continue
        answer = Answer.model_validate(value)
        if not answer.new:
            continue
        if key == "questions:role":
            roles.add(answer.choice)
        elif key.startswith(("questions:input_type:", "questions:output_type:")):
            identifier, states = split(answer.choice)
            types[identifier] = types.get(identifier, frozenset()) | states
    return types, roles


def option_is_new(key: str, identifier: str, seen: Known,
                  items: dict[str, JsonValue]) -> bool:
    """Whether a question's option needs vocabulary review (#451): the engine decides from the
    registry, pending and this adaptation's own drafts and approved answers, never the model."""
    introduced_types, introduced_roles = _introduced(items)
    if key == "questions:role":
        return identifier not in (seen.roles | seen.pending | _own(items, "role")
                                  | introduced_roles)
    if not key.startswith(("questions:input_type:", "questions:output_type:")):
        return False
    try:
        type_id, states = split(identifier)
    except ValueError:
        return True
    allowed = set(seen.states.get(type_id, frozenset())) | set(introduced_types.get(type_id, ()))
    own = items.get(f"vocabulary:type:{type_id}")
    if isinstance(own, dict):
        allowed |= set(own.get("add_states", own.get("states", [])))
    declared = type_id in (seen.types | seen.pending | _own(items, "type")
                           | introduced_types.keys())
    return not declared or not states <= allowed


def mark_new(key: str, value: JsonValue, seen: Known,
             items: dict[str, JsonValue]) -> JsonValue:
    """A question with each option's `new` set by `option_is_new`, replacing the model's."""
    if not isinstance(value, dict) or not isinstance(value.get("options"), list):
        return value
    options = [{**o, "new": option_is_new(key, str(o.get("id", "")), seen, items)}
               if isinstance(o, dict) else o for o in value["options"]]
    return {**value, "options": options}


def _port_signatures(key: str, value: dict) -> list[str]:
    """Read the port models' alternatives and state fields, including `::` input notation."""
    fields = {k: v for k, v in value.items() if k != "position"}
    if key.startswith("contract:input:"):
        port = InputPort.model_validate(fields)
        return [join(a.type_id, a.states) for a in port.alternatives()]
    port = OutputPort.model_validate(fields)
    return [join(port.type_id, port.state)]


def _referenced(items: dict[str, JsonValue]) -> dict[str, set[str]]:
    types = {split(signature)[0] for key, value in items.items()
             if key.startswith(("contract:input:", "contract:output:")) and isinstance(value, dict)
             for signature in _port_signatures(key, value)}
    process = items.get("contract:process")
    roles = set(process.get("roles", [])) if isinstance(process, dict) else set()
    return {"types": types, "roles": roles}


def pending_used(items: dict[str, JsonValue], seen: Known) -> set[str]:
    """The pending ids the items use: what this adaptation will depend on."""
    used = _referenced(items)
    return (used["types"] | used["roles"]) & seen.pending


def families_used(items: dict[str, JsonValue]) -> set[str]:
    """Family references in ports and type declarations, independently of type ownership."""
    return {family_of(identifier) for identifier in
            _referenced(items)["types"] | set(_own(items, "type"))}


def pending_families_used(items: dict[str, JsonValue], seen: Known) -> set[str]:
    return families_used(items) & (seen.pending_families - seen.families - _own(items, "family"))


def check_items(
    items: dict[str, JsonValue], seen: Known, module: ModuleSpec
) -> list[Problem]:
    problems: list[Problem] = []
    used = _referenced(items)
    for key, value in items.items():
        if (key.startswith("vocabulary:family:") and isinstance(value, dict)
                and value.get("id") != key.removeprefix("vocabulary:family:")):
            problems.append(Problem(code="MF0507",
                                    says=f"{key}: family ID must match its item key"))
    introduced_types, introduced_roles = _introduced(items)
    for type_id in sorted(used["types"]):
        if type_id not in seen.types | seen.pending | _own(items, "type") | introduced_types.keys():
            problems.append(Problem(code="MF0507", says=f"type {type_id!r} is not in the "
                                    "registry, pending, proposed here, or introduced by an "
                                    "approved answer"))
    for role in sorted(used["roles"]):
        if role not in seen.roles | seen.pending | _own(items, "role") | introduced_roles:
            problems.append(Problem(code="MF0507", says=f"role {role!r} is not in the registry, "
                                    "pending, proposed here, or introduced by an approved answer"))
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
    return [*problems, *_signature_problems(items, seen, introduced_types),
            *_test_problems(items, seen), *_measurer_problems(items, seen)]


def _names(items: dict[str, JsonValue], prefix: str) -> set[str]:
    return {k.removeprefix(prefix) for k in items if k.startswith(prefix)}


def _required(items: dict[str, JsonValue]) -> set[str]:
    """The inputs a test must feed: an optional one it leaves out runs without (#470)."""
    return {key.rsplit(":", 1)[1] for key, value in items.items()
            if key.startswith("contract:input:")
            and not (isinstance(value, dict) and value.get("required") is False)}


def _accepted(items: dict[str, JsonValue]) -> dict[str, set[str]]:
    """Each input's types: its `type_id`, or the types its `accepts` lists (#464)."""
    found: dict[str, set[str]] = {}
    for key, value in items.items():
        if key.startswith("contract:input:") and isinstance(value, dict):
            types = {a.get("type_id") for a in value.get("accepts") or [] if isinstance(a, dict)}
            found[key.rsplit(":", 1)[1]] = types or {value.get("type_id")}
    return found


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
        given = {port for port, paths in test.inputs.items() if paths}
        for port in sorted(_required(items) - given - fed):
            problems.append(f"{key}: nothing feeds input {port!r}")
        accepted = _accepted(items)
        for port, type_id in sorted(test.types.items()):
            if port not in takes:
                problems.append(f"{key}: types names {port!r}, not an input of this contract")
            elif type_id not in accepted.get(port, set()):
                problems.append(f"{key}: input {port!r} does not accept {type_id!r}")
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


def _unproven_says(key: str, output: str) -> str:
    return f"{key}: no test expects output {output!r}, so the parser cannot be proven"


def unproven(items: dict[str, JsonValue]) -> list[Problem]:
    """Measurers whose output no test expects: asked again at assembly, since removing a test is
    a decision nothing validates (#487 review I1)."""
    expected = {e.port for key in items if key.startswith("tests:test:")
                for e in TestDraft.model_validate(items[key]).expect}
    return [Problem(code="MF0507", says=_unproven_says(key, value["output"]))
            for key, value in sorted(items.items())
            if key.startswith("measurers:measurer:") and isinstance(value, dict)
            and value.get("output") not in expected]


def _measurer_problems(items: dict[str, JsonValue], seen: Known) -> list[Problem]:
    """A drafted measurer must measure something known, read an output of this contract that a
    test expects (or nothing proves it), and keep the pieces' rules (MD0027, #487)."""
    measurements = (seen.measurements | seen.pending
                    | _names(items, "vocabulary:measurement:")
                    | _names(items, "measurers:measurement:"))
    makes = _names(items, "contract:output:")
    expected = {e.port for key in items if key.startswith("tests:test:")
                for e in TestDraft.model_validate(items[key]).expect}
    problems: list[str] = []
    for key in sorted(k for k in items if k.startswith("measurers:measurement:")):
        value = items[key] if isinstance(items[key], dict) else {}
        if value.get("id") != key.removeprefix("measurers:measurement:"):
            problems.append(f"{key}: measurement ID must match its item key")
    first: dict[str, str] = {}
    for key in sorted(k for k in items if k.startswith("measurers:measurer:")):
        name = key.removeprefix("measurers:measurer:")
        measures = items[key].get("measures") if isinstance(items[key], dict) else None
        if measures in first:
            problems.append(f"{key}: {first[measures]} also measures {measures!r}; a run keeps "
                            "one fact per measurement, so keep one measurer")
        elif measures:
            first[measures] = name
        if not name.isidentifier():
            problems.append(f"{key}: {name!r} is not a Python name; its parser is imported by "
                            "it, so use letters, digits and '_'")
        draft = MeasurerDraft.model_validate(items[key])
        if draft.measures not in measurements:
            problems.append(f"{key}: measures {draft.measures!r}, which is not a measurement in "
                            "the registry or drafted here")
        if draft.output not in makes:
            problems.append(f"{key}: reads output {draft.output!r}, which this contract does not "
                            "produce")
        elif draft.output not in expected:
            problems.append(_unproven_says(key, draft.output))
        reached = piece_problems(draft.code)
        if reached:
            problems.append(f"{key}: MD0027 its code reaches past what a piece may import or "
                            f"call: {', '.join(reached)}")
        elif not re.search(r"^def parse\(\s*stream\s*,\s*decided\s*\)", draft.code, re.M):
            problems.append(f"{key}: its code defines no parse(stream, decided)")
        if not re.search(r"^def test_", draft.tests, re.M):
            problems.append(f"{key}: its tests define no test_ function")
    return [Problem(code="MF0507", says=says) for says in problems]


def _nf_inputs(items: dict[str, JsonValue]) -> list[NfInput]:
    raw = items.get("contract:nf_inputs") or []
    return [NfInput(**entry) for entry in raw if isinstance(entry, dict)]


def _signature_problems(
    items: dict[str, JsonValue], seen: Known, introduced: dict[str, frozenset[str]],
) -> list[Problem]:
    problems = []
    allowed = dict(seen.states)
    for key, value in items.items():
        if key.startswith("vocabulary:type:") and isinstance(value, dict):
            identifier = key.removeprefix("vocabulary:type:")
            allowed[identifier] = (allowed.get(identifier, frozenset()) |
                frozenset(value.get("add_states", value.get("states", []))))
    # Introduced names are draft permissions, not vocabulary declarations.
    for identifier, states in introduced.items():
        allowed[identifier] = allowed.get(identifier, frozenset()) | states
    for key, value in items.items():
        if not isinstance(value, dict):
            continue
        signatures = []
        if key.startswith(("contract:input:", "contract:output:")):
            signatures = [(signature, False) for signature in _port_signatures(key, value)]
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
                if identifier not in (seen.types | seen.pending | _own(items, "type")
                                      | introduced.keys()):
                    if key.startswith("contract:"):
                        continue  # The reference check above already reports this type.
                    raise ValueError(f"{signature!r} is not declared; mark a new option as new")
                if not states <= allowed.get(identifier, frozenset()):
                    raise ValueError(f"{signature!r} has undeclared states; "
                                     "propose vocabulary for review")
            except ValueError as error:
                problems.append(Problem(code="MF0507", says=f"{key}: {error}"))
    return problems
