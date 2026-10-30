"""An item's value is the registry's own model (spec §2): a port is an `InputPort`, a setting a
`Param`, a rule a `Decision`. So whatever the registry refuses, forging refuses, with the
registry's own messages, and an assembled contract is a `ModuleContract` like any other.

Item keys: `contract:process`, `contract:input:<port>`, `contract:output:<port>`,
`contract:nf_inputs`, `parameters:param:<name>`, `parameters:ext_args`,
`vocabulary:type:<id>`, `vocabulary:measurement:<id>`, `vocabulary:role:<name>`,
`rules:rule:<role>`, `tests:test:<name>`, `<piece>:none`, `questions:<subject>`.
"""

from comeni_core.declared.contract import (
    ContractExtArgs,
    InputPort,
    ModuleContract,
    NfInput,
    OutputPort,
    Param,
    Provenance,
)
from comeni_core.declared.measurement import Measurement
from comeni_core.declared.tooltest import TestDraft
from comeni_core.declared.vocabulary import TypeDeclaration
from mendel_resolver.rules.format import Decision
from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InputItem(InputPort):
    position: int
    """Where the port sits in `consumes`: the order is part of the contract."""


class OutputItem(OutputPort):
    position: int


class ParamItem(Param):
    position: int


class ProcessDraft(_Frozen):
    nf_process: str
    nf_include: str
    roles: list[str] = []
    container: str | None = None
    priority: int = 0
    priority_because: str = ""


class RoleDraft(_Frozen):
    name: str
    because: str = ""


class NoneNeeded(_Frozen):
    """A piece that needs nothing, said explicitly: an empty piece is an unfinished one."""

    because: str


class Option(_Frozen):
    id: str
    label: str
    because: str


class Question(_Frozen):
    asks: str
    options: list[Option]
    allows_new: bool = True
    suggested: str | None = None
    """The option the AI is confident in, shown for the person to accept; never an answer."""


class Answer(_Frozen):
    choice: str
    new: bool = False
    """A name the person made up, rather than one of the options."""


_FAMILIES: dict[str, type] = {
    "contract:process": ProcessDraft,
    "contract:input": InputItem,
    "contract:output": OutputItem,
    "contract:nf_inputs": list[NfInput],
    "parameters:param": ParamItem,
    "parameters:ext_args": ContractExtArgs,
    "vocabulary:type": TypeDeclaration,
    "vocabulary:measurement": Measurement,
    "vocabulary:role": RoleDraft,
    "rules:rule": Decision,
    "tests:test": TestDraft,
}


def value_model(key: str, *, answer: bool = False) -> type:
    """The model an item's value must validate as. A question's answer is an `Answer`."""
    piece, _, rest = key.partition(":")
    if piece == "questions":
        return Answer if answer else Question
    if rest == "none":
        return NoneNeeded
    family = f"{piece}:{rest.split(':', 1)[0]}"
    if family not in _FAMILIES:
        raise KeyError(f"{key!r} is not an item forging knows")
    return _FAMILIES[family]


def validate_value(key: str, value: JsonValue, *, answer: bool = False):
    """The validated model, or a `ValidationError` in the registry's words."""
    return TypeAdapter(value_model(key, answer=answer)).validate_python(value)


def items_of(contract: ModuleContract) -> dict[str, JsonValue]:
    """A contract as forging's items: how a re-forge starts from the registry's contract."""
    items: dict[str, JsonValue] = {
        "contract:process": ProcessDraft(
            nf_process=contract.nf_process, nf_include=contract.nf_include,
            roles=list(contract.roles), container=contract.container,
            priority=contract.priority, priority_because=contract.priority_because,
        ).model_dump(mode="json"),
    }
    for n, port in enumerate(contract.consumes):
        items[f"contract:input:{port.name}"] = {"position": n, **port.model_dump(mode="json")}
    for n, port in enumerate(contract.produces):
        items[f"contract:output:{port.name}"] = {"position": n, **port.model_dump(mode="json")}
    if contract.nf_inputs:
        items["contract:nf_inputs"] = [i.model_dump(mode="json") for i in contract.nf_inputs]
    for n, param in enumerate(contract.params):
        items[f"parameters:param:{param.name}"] = {"position": n, **param.model_dump(mode="json")}
    ext = contract.ext_args
    if ext:
        ext = ext if isinstance(ext, ContractExtArgs) else ContractExtArgs(template=ext)
        items["parameters:ext_args"] = ext.model_dump(mode="json")
    return items


def contract_of(
    values: dict[str, JsonValue], contract_id: str, provenance: Provenance
) -> ModuleContract:
    """The contract the approved items make. Raises the registry's own `ValidationError`."""

    def family(prefix: str, model: type) -> list:
        found = [validate_value(k, v) for k, v in values.items() if k.startswith(prefix)]
        return [_strip(item, model) for item in sorted(found, key=lambda i: i.position)]

    process = validate_value("contract:process", values["contract:process"])
    ext_value = values.get("parameters:ext_args")
    ext = validate_value("parameters:ext_args", ext_value) if ext_value else ""
    if isinstance(ext, ContractExtArgs) and not ext.because:
        ext = ext.template
    return ModuleContract(
        id=contract_id,
        nf_process=process.nf_process,
        nf_include=process.nf_include,
        roles=process.roles,
        container=process.container,
        priority=process.priority,
        priority_because=process.priority_because,
        consumes=family("contract:input:", InputPort),
        produces=family("contract:output:", OutputPort),
        params=family("parameters:param:", Param),
        nf_inputs=validate_value("contract:nf_inputs", values.get("contract:nf_inputs", [])),
        ext_args=ext,
        provenance=provenance,
    )


def _strip(item: BaseModel, model: type[BaseModel]) -> BaseModel:
    return model(**item.model_dump(exclude={"position"}))
