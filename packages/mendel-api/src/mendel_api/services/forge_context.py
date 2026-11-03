"""The declared and upstream evidence behind an open forge question."""

from comeni_core.declared.signature import split
from mendel_forge.forging.context import SourceLine, uses
from mendel_forge.nfcore.parse import parse_module
from pydantic import BaseModel

from mendel_api.services import forging, registry


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
    contracts = sorted(stack.registry.all(), key=lambda c: c.id)
    choices = []
    for option in question["options"]:
        identifier = option["id"]
        if kind == "role":
            choices.append(ContextChoice(
                id=identifier, explain=stack.roles.explains.get(identifier),
                tools=[c.id for c in contracts if identifier in c.roles],
                proposed=identifier not in stack.roles.names))
        elif kind in {"input_type", "output_type"}:
            type_id, states = split(identifier)
            vocabulary = stack.vocabulary
            choices.append(ContextChoice(id=identifier, name=vocabulary.names.get(type_id),
                explain=vocabulary.explains.get(type_id), scope=vocabulary.scopes.get(type_id),
                tools=[c.id for c in contracts if
                       any(p.type_id == type_id and states <= p.state for p in c.produces) or
                       any(a.type_id == type_id and states <= a.states
                           for p in c.consumes for a in p.alternatives())],
                proposed=type_id not in vocabulary.types or
                         not states <= vocabulary.types.get(type_id, frozenset())))
    decides = {
        "role": "Chooses the job this tool does, so rules can choose it for that job.",
        "input_type": f"Chooses what {name} reads, so the engine can connect a matching source.",
        "output_type": f"Chooses what {name} holds, so the engine can connect tools that read it.",
        "competition": "Decides whether a rule is needed to choose between tools doing this job.",
    }.get(kind, "Records this answer for the remaining pieces.")
    # Conformance checks declared outputs against emits; it does not require every emit to
    # be declared. This is optional declaration, not Nextflow's optional file flag.
    optional = kind == "output_type"
    return QuestionContext(lines=uses(script, name), source_available=source.is_file(),
        upstream=description if isinstance(description, str) else None, choices=choices,
        decides=decides, optional=optional)
