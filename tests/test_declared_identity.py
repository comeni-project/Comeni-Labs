"""A declared file says what it is and what it is called, rather than the path saying it.

comeni-registry#1: contracts, rules and vocabularies were split into one directory per kind,
because the directory was how the loader knew what a file *was*. Two kinds went further and took
their **identity** from the filename — `_parse_type` read `type_id` from `path.name`, and
measurements did the same — so a type could not be moved or renamed without being renamed.

Contracts already carried `id:`, and rules are keyed on the decision's target rather than the
file. Three of five kinds were already path-independent and nobody had noticed.

**This task is additive.** `kind:` is accepted and ignored; `id:` wins over the filename when
present and the filename still works when it is not. That is what lets the registry be migrated
one file at a time while every commit stays green.
"""

import pathlib

from mendel_resolver import layers

ROOT = pathlib.Path(__file__).parent.parent

CONTRACT = """\
declares: contract
id: nf-core/fastqc@0.12.1
roles: [qc_per_sample]
nf_process: FASTQC
nf_include: modules/nf-core/fastqc/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces: [{name: zip, type_id: qc.report, state: []}]
params: []
priority: 0
nf_inputs: [{ports: [reads]}]
container: quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0
provenance:
  source: nf-core-meta-yml
  drafted_by: hand
  approved_by: test
  approved_at: "2026-08-16"
"""


def _layer(root: pathlib.Path) -> pathlib.Path:
    layer = root / "registry"
    for kind in ("contracts", "vocabularies", "rules", "measurements", "roles"):
        (layer / kind).mkdir(parents=True)
    (layer / "registry.yml").write_text("name: test-layer\n")
    (layer / "roles" / "roles.yml").write_text("roles: [qc_per_sample]\n")
    (layer / "vocabularies" / "fastq.reads.yml").write_text("states: [trimmed]\n")
    (layer / "vocabularies" / "qc.report.yml").write_text("states: []\n")
    return layer


def test_a_contract_may_declare_what_it_is(tmp_path):
    """`extra="forbid"` is why this test exists: without accepting `kind:`, adding it to a
    registry file would fail to load, and the migration could not be incremental."""
    layer = _layer(tmp_path)
    (layer / "contracts" / "fastqc.yml").write_text(CONTRACT)
    assert layers.load(layer).registry.contracts


def test_a_vocabulary_may_declare_its_own_id(tmp_path):
    """The identity moves off the filename, which is what makes the file portable."""
    layer = _layer(tmp_path)
    (layer / "vocabularies" / "anything-at-all.yml").write_text(
        "declares: vocabulary\nid: genome.index.star\nstates: []\n"
    )
    assert "genome.index.star" in layers.load(layer).vocabulary.types


def test_a_vocabulary_without_an_id_still_uses_its_filename(tmp_path):
    """Both work until Task 3, which is what keeps every commit of the migration green."""
    layer = _layer(tmp_path)
    (layer / "vocabularies" / "genome.index.star.yml").write_text("states: []\n")
    assert "genome.index.star" in layers.load(layer).vocabulary.types


def test_a_measurement_may_declare_its_own_id(tmp_path):
    layer = _layer(tmp_path)
    (layer / "measurements" / "whatever.yml").write_text(
        "declares: measurement\nid: read_length\nkind: integer\n"
        "per_sample: true\nminimum: 1\nunit: bp\ndescription: 'test'\ncite: 'test'\n"
    )
    loaded = layers.load(layer)
    # The id comes from the file, not from `whatever.yml`, which is the whole point.
    assert "read_length" in loaded.measurements.ids()


def test_the_real_registry_still_loads():
    """The thing every other test rests on."""
    assert layers.load(ROOT / "registry").registry.contracts
