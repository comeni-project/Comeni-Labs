"""One declaration kind for everything that measures (#465): our own code, or a tool plus a
parser for its output, each saying where it may run."""

import pytest
from comeni_core.declared.inspection import InspectionCatalogue, Measurer
from pydantic import ValidationError

CODE = {
    "id": "read_length", "version": "1.0.0", "measures": "read_length", "by": "code",
    "record": "sequence", "decided": {"min_records": 1000}, "entry": "piece/read_length.py",
    "runs": ["server", "pipeline"],
}
TOOL = {
    "id": "genome_length_fai", "version": "1.0.0", "measures": "genome_length", "by": "tool",
    "uses": "nf-core/samtools/faidx@1.21", "output": "fai", "entry": "piece/fai.py",
    "runs": ["pipeline"],
}


def _refused(data: dict) -> str:
    with pytest.raises(ValidationError) as caught:
        Measurer.model_validate(data)
    return str(caught.value)


def test_a_code_measurer_loads():
    measurer = Measurer.model_validate(CODE)
    assert measurer.runs == ["server", "pipeline"]
    assert measurer.runs_on("pipeline") and measurer.runs_on("server")


def test_a_tool_measurer_loads():
    measurer = Measurer.model_validate(TOOL)
    assert measurer.uses == "nf-core/samtools/faidx@1.21" and not measurer.runs_on("server")


def test_a_tool_measurer_never_runs_on_the_server():
    assert "MD0326" in _refused({**TOOL, "runs": ["server", "pipeline"]})


def test_a_code_measurer_needs_a_record():
    assert "MD0326" in _refused({k: v for k, v in CODE.items() if k != "record"})


def test_a_tool_measurer_has_no_record():
    assert "MD0326" in _refused({**TOOL, "record": "sequence"})


@pytest.mark.parametrize("missing", ["uses", "output"])
def test_a_tool_measurer_names_its_tool_and_output(missing):
    assert "MD0326" in _refused({k: v for k, v in TOOL.items() if k != missing})


def test_a_code_measurer_names_no_tool():
    assert "MD0326" in _refused({**CODE, "uses": "nf-core/x@1", "output": "y"})


def test_runs_somewhere():
    assert "MD0326" in _refused({**CODE, "runs": []})


class _Port:
    def __init__(self, name):
        self.name = name


class _Contract:
    def __init__(self, ports):
        self.produces = [_Port(p) for p in ports]


class _Registry:
    def __init__(self, contracts):
        self.contracts = contracts

    def get(self, contract_id):
        if contract_id not in self.contracts:
            raise KeyError(contract_id)
        return self.contracts[contract_id]


def _catalogue() -> InspectionCatalogue:
    return InspectionCatalogue(measurers={"genome_length_fai": Measurer.model_validate(TOOL)})


def test_a_tool_measurer_naming_a_missing_contract_is_refused():
    usable, refused = _catalogue().check_tools(_Registry({}))
    assert usable.measurers == {}
    assert len(refused) == 1 and "MD0327" in refused[0] and "nf-core/samtools/faidx" in refused[0]


def test_a_tool_measurer_naming_a_missing_output_is_refused():
    registry = _Registry({"nf-core/samtools/faidx@1.21": _Contract(["sizes"])})
    usable, refused = _catalogue().check_tools(registry)
    assert usable.measurers == {}
    assert "MD0327" in refused[0] and "fai" in refused[0] and "sizes" in refused[0]


def test_a_tool_measurer_whose_tool_exists_stays():
    registry = _Registry({"nf-core/samtools/faidx@1.21": _Contract(["fai", "sizes"])})
    usable, refused = _catalogue().check_tools(registry)
    assert list(usable.measurers) == ["genome_length_fai"] and refused == []


def test_runs_has_one_spelling():
    measurer = Measurer.model_validate({**CODE, "runs": ["pipeline", "server", "server"]})
    assert measurer.runs == ["server", "pipeline"]
