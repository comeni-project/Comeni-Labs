"""Pipeline measurers become generated steps the router can route like any other (#465)."""

import pathlib

from comeni_core.declared.inspection import InspectionCatalogue, Measurer
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.measure_steps import RUNNER_IMAGE, contracts_for, steps_for
from mendel_resolver.router import route

ROOT = pathlib.Path(__file__).parents[3]
LOADED = layers.load(ROOT / "registry")


def test_one_step_per_format_carries_every_code_measurer_of_its_record():
    contracts = {c.id: c for c in contracts_for(LOADED.inspection, LOADED.registry)}
    fastq = contracts["comeni/measure/fastq@1.1.0"]
    assert [p.type_id for p in fastq.consumes] == ["fastq.reads"]
    assert sorted(p.type_id for p in fastq.produces) == [
        "measurement.paired", "measurement.quality_encoding", "measurement.read_length",
    ]
    assert fastq.roles == ["measurement"] and fastq.container == RUNNER_IMAGE
    assert fastq.nf_process == "MEASURE_FASTQ"
    assert fastq.nf_include == "modules/comeni/measure/fastq/main"
    assert fastq.provenance.drafted_by == "generated"
    assert "read_length@1.0.0" in fastq.provenance.source


def test_a_server_only_measurer_has_no_step():
    only_server = LOADED.inspection.measurers["read_length"].model_copy(update={"runs": ["server"]})
    catalogue = LOADED.inspection.model_copy(
        update={"measurers": {**LOADED.inspection.measurers, "read_length": only_server}})
    (fastq,) = [c for c in contracts_for(catalogue, LOADED.registry) if "fastq" in c.id]
    assert "measurement.read_length" not in {p.type_id for p in fastq.produces}


def test_a_tool_measurer_is_a_step_over_the_tool_output():
    tool = Measurer.model_validate({
        "id": "genome_length_star", "version": "1.0.0", "measures": "genome_length",
        "by": "tool", "uses": "nf-core/star/genomegenerate@2.7.11b", "output": "index",
        "entry": "piece/x.py", "runs": ["pipeline"],
    })
    catalogue = InspectionCatalogue(measurers={"genome_length_star": tool})
    (step,) = steps_for(catalogue, LOADED.registry)
    assert step.contract.id == "comeni/measure/genome_length_star@1.0.0"
    assert [p.type_id for p in step.contract.consumes] == ["genome.index.star"]
    assert [p.type_id for p in step.contract.produces] == ["measurement.genome_length"]
    assert step.measurers == (tool,) and step.format is None


def test_the_steps_are_in_a_stable_order():
    first = [c.id for c in contracts_for(LOADED.inspection, LOADED.registry)]
    assert first == sorted(first)


def test_the_router_reaches_a_measurement():
    registry = LOADED.registry.with_contracts(contracts_for(LOADED.inspection, LOADED.registry))
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["measurement.read_length"])
    plan = route(goal, registry, LOADED.rules, None, premises={}, absent_roles=frozenset())
    assert [s.contract_id for s in plan.steps] == ["comeni/measure/fastq@1.1.0"]


def test_the_loaded_registry_is_left_alone():
    """Docs, conformance and the registry browser never list a generated step."""
    assert not [c for c in LOADED.registry.all() if c.id.startswith("comeni/measure/")]
