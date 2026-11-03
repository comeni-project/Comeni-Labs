"""Constructor fields come from the value models used by the command boundary."""

from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.values import Answer, NoneNeeded, value_model
from pydantic import BaseModel, JsonValue, TypeAdapter

from mendel_api.services import forging

KINDS = (
    ("questions:role", "The tool's job", False),
    ("questions:input_type", "An input's type", True),
    ("questions:output_type", "An output's type", True),
    ("questions:competition", "Whether a selection rule is needed", False),
    ("contract:process", "Process", False),
    ("contract:input", "Input", True),
    ("contract:output", "Output", True),
    ("contract:nf_inputs", "Process input wiring", False),
    ("parameters:param", "Setting", True),
    ("parameters:ext_args", "Baseline arguments", False),
    ("vocabulary:type", "Data type or added states", True),
    ("vocabulary:measurement", "Measurement", True),
    ("vocabulary:role", "Job", True),
    ("rules:rule", "Decision rule", True),
    ("tests:test", "Test", True),
)


class Constructor(BaseModel):
    family: str
    label: str
    named: bool
    fields: dict[str, JsonValue]


class Constructors(BaseModel):
    kinds: list[Constructor]
    inputs: list[str] = []
    outputs: list[str] = []


def kinds() -> list[Constructor]:
    """Question constructors record an answer, rather than inventing a model question."""
    result = [Constructor(family=family, label=label, named=named,
        fields=TypeAdapter(Answer if family.startswith("questions:")
                           else value_model(family)).json_schema())
        for family, label, named in KINDS]
    result.extend(Constructor(family=f"{piece}:none", label="Nothing needed", named=False,
        fields=NoneNeeded.model_json_schema())
        for piece in ("parameters", "vocabulary", "rules"))
    return result


def read(adaptation_id: str) -> Constructors:
    adaptation = forging.row(adaptation_id)
    source = forging.module_folder(adaptation.source, adaptation.path) / "main.nf"
    spec = ModuleSpec.parse(source) if source.is_file() else None
    return Constructors(kinds=kinds(),
        inputs=sorted({name for slot in spec.inputs for name in slot.names}) if spec else [],
        outputs=sorted(spec.emits) if spec else [])
