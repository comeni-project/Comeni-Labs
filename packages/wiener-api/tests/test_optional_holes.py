"""Inputs a run may leave empty (#460): Wiener reads them from the artifact, never a contract.

A pipeline built with QUAST's reference optional has `params.fasta` as a null like any other
input, plus a channel marked optional. The run sheet offers it as optional and sends `""` when
it is left empty; the pipeline's own ternary then passes the empty placeholder.
"""

from wiener_api.services.artifacts import optional_holes, run_rules
from wiener_api.settings import settings


def _artifact(tmp_path, channels: str, steps: str = " []") -> str:
    settings.artifact_root = tmp_path
    (tmp_path / "a1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "a1" / "pipeline.yml").write_text(f"""version: 8
intent: {{want: [], constraints: {{}}}}
facts: {{inputs: [], measurements: []}}
registry: {{layers: [], displaced: [], unverified: []}}
ai: {{available: [], used: []}}
steps:{steps}
channels:
{channels}
input_form: direct
decisions: []
emitted: null
gate: null
""")
    return "a1"


def _channel(name: str, param: str, optional: bool) -> str:
    extra = "  optional: true\n  absent_width: 2\n" if optional else ""
    return (f"- name: {name}\n  param: {param}\n  scope: run\n  columns: [{name}]\n"
            f"  type_id: a.b\n  params: [{param}]\n"
            f"  expression: \"Channel.of(params.{param})\"\n  meta: []\n  test_data: []\n{extra}")


def test_the_optional_holes_are_the_optional_channels_params(tmp_path):
    artifact = _artifact(tmp_path, _channel("consensus", "consensus", False)
                         + _channel("fasta", "fasta", True))
    assert optional_holes(artifact) == {"fasta"}


def test_an_artifact_without_a_readable_pipeline_has_no_optional_holes(tmp_path):
    settings.artifact_root = tmp_path
    assert optional_holes("missing") == set()
    assert run_rules("missing") == []


STEP = """
- id: quast
  module: {contract_id: nf-core/quast@5.3.0, digest: "sha256:%s", container: null}
  process: QUAST
  include: modules/nf-core/quast/main
  why: {tier: 1, source: resolver, reason: "the only tool that makes it"}
  run_rules:
    - {given: [gff], requires: [fasta], says: "gff needs fasta"}
""" % ("0" * 64)


def test_the_run_rules_are_read_from_the_steps(tmp_path):
    artifact = _artifact(tmp_path, _channel("fasta", "fasta", True)
                         + _channel("gff", "gff", True), steps=STEP)
    assert run_rules(artifact) == [
        {"given": ["gff"], "requires": ["fasta"], "forbids": [], "says": "gff needs fasta"}]
