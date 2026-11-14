"""A fact the pipeline wants is one Wiener reads from its measuring step (#487 review C1).

Wiener reads a run's measured facts closed: only measurements its own `pipeline.yml` declares.
A forge test's pipeline wants each drafted parser's `measurement.<id>`, and nothing confirms or
decides on it; read only through confirms and run-time settings, a correct parser looked as if
it reported nothing on a real Wiener.
"""

import json

from comeni_core.declared.tooltest import ToolTest
from mendel_forge.testing import build_test_pipeline
from mendel_resolver import layers
from support.paths import REGISTRY
from wiener_api.services import measured


def test_a_forge_tests_parser_fact_is_read(tmp_path):
    test = ToolTest(contract="nf-core/samtools/faidx@1.24", name="one", data_commit="abc",
                    inputs={"fasta": ["a/genome.fasta"]},
                    expect=[{"port": "fai", "pattern": "*.fai"}])
    pipeline = build_test_pipeline(test, layers.load(REGISTRY))
    assert "measurement.genome_length" in pipeline.intent.want
    (step,) = [s for s in pipeline.steps if s.module.contract_id.startswith("comeni/measure/")]
    folder = tmp_path / step.process.lower()
    folder.mkdir()
    (folder / "test.measured.json").write_text(json.dumps({"facts": {"genome_length": {
        "value": 29903, "coverage": "all", "by": ["genome_length_fai@1.0.0"]}}}))
    facts, _ = measured.read(tmp_path, pipeline)
    assert [(f.measurement, f.value) for f in facts] == [("genome_length", 29903)]
