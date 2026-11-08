"""The declared and upstream evidence behind an open forge question."""

from comeni_core.declared.signature import split
from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.checks import QuestionFinding, arrival
from mendel_forge.forging.context import SourceLine, uses
from mendel_forge.forging.validate import known, option_is_new, validation_items
from mendel_forge.nfcore.parse import parse_module
from pydantic import BaseModel

from mendel_api.services import forge_checks, forging, registry


class ContextChoice(BaseModel):
    id: str
    name: str | None = None
    explain: str | None = None
    scope: str | None = None
    tools: list[str] = []
    proposed: bool = False


class QuestionContext(BaseModel):
    lines: list[SourceLine]
    source_available: bool
    upstream: str | None = None
    choices: list[ContextChoice]
    decides: str
    optional: bool = False
    arrival: str | None = None
    """`sample` or `run`, from the module's meta naming (#452); none when it says nothing."""
    channel: str | None = None
    """The `main.nf` input line that declares this channel, e.g. `tuple val(meta), path(x)`."""
    findings: list[QuestionFinding] = []


def read(adaptation_id: str, key: str) -> QuestionContext:
    adaptation = forging.row(adaptation_id)
    item = forging.load(adaptation_id).items[key]
    question = next((r.value for r in reversed(item.revisions)
                     if isinstance(r.value, dict) and "asks" in r.value), None)
    if question is None:
        raise KeyError(key)
    folder = forging.module_folder(adaptation.source, adaptation.path)
    source = folder / "main.nf"
    script = source.read_text() if source.is_file() else ""
    upstream = parse_module(folder, adaptation.path, adaptation.source)
    parts = key.split(":", 2)
    kind, name = parts[1], parts[2] if len(parts) > 2 else ""
    channels = upstream.outputs if kind == "output_type" else upstream.inputs
    description = next((c.description for c in channels if c.name == name), None)
    description = description or upstream.description
    stack = registry.stack()
    state = forging.load(adaptation_id)
    seen = known(stack, pending=forging.pending_ids(adaptation_id),
                 pending_families=forging.pending_families(adaptation_id))
    merged = validation_items(state)
    contracts = sorted(stack.registry.all(), key=lambda c: c.id)
    choices = []
    for option in question["options"]:
        identifier = option["id"]
        if kind == "role":
            choices.append(ContextChoice(
                id=identifier, explain=stack.roles.explains.get(identifier),
                tools=[c.id for c in contracts if identifier in c.roles],
                proposed=option_is_new(key, identifier, seen, merged)))
        elif kind in {"input_type", "output_type"}:
            type_id, states = split(identifier)
            vocabulary = stack.vocabulary
            choices.append(ContextChoice(id=identifier, name=vocabulary.names.get(type_id),
                explain=vocabulary.explains.get(type_id), scope=vocabulary.scopes.get(type_id),
                tools=[c.id for c in contracts if
                       any(p.type_id == type_id and states <= p.state for p in c.produces) or
                       any(a.type_id == type_id and states <= a.states
                           for p in c.consumes for a in p.alternatives())],
                proposed=option_is_new(key, identifier, seen, merged)))
    decides = {
        "role": "Chooses the job this tool does, so rules can choose it for that job.",
        "input_type": f"Chooses what {name} reads, so the engine can connect a matching source.",
        "output_type": f"Chooses what {name} holds, so the engine can connect tools that read it.",
        "competition": "Decides whether a rule is needed to choose between tools doing this job.",
    }.get(kind, "Records this answer for the remaining pieces.")
    # Conformance checks declared outputs against emits; it does not require every emit to
    # be declared. This is optional declaration, not Nextflow's optional file flag.
    optional = kind == "output_type"
    spec = ModuleSpec.of(script) if script and kind == "input_type" else None
    found = forge_checks.for_adaptation(adaptation.source, adaptation.path, state).get(key, [])
    declared = next((line.text.strip() for line in uses(script, name)
                     if "path(" in line.text and name in line.text), None) if spec else None
    return QuestionContext(lines=uses(script, name), source_available=source.is_file(),
        upstream=description if isinstance(description, str) else None, choices=choices,
        decides=decides, optional=optional, arrival=arrival(spec, name) if spec else None,
        channel=declared, findings=found)
