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

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/fastqc.contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body

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


TYPE = "declares: vocabulary\nid: fastq.reads\nstates: [trimmed]\n"
REPORT = "declares: vocabulary\nid: qc.report\nstates: []\n"
ROLES = "declares: role\nroles: [qc_per_sample]\n"


def _layer(root: pathlib.Path) -> pathlib.Path:
    layer = root / "registry"
    for kind in ("contracts", "vocabularies", "rules", "measurements", "roles"):
        (layer / kind).mkdir(parents=True)
    (layer / "registry.yml").write_text(_declared(layer / "registry.yml", "name: test-layer\n"))
    (layer / "roles.yml").write_text(_declared(layer / "roles.yml", ROLES))
    (layer / "vocabularies" / "fastq.reads.yml").write_text(
        _declared(layer / "vocabularies" / "fastq.reads.yml", TYPE)
    )
    (layer / "vocabularies" / "qc.report.yml").write_text(
        _declared(layer / "vocabularies" / "qc.report.yml", REPORT)
    )
    return layer


def test_a_contract_may_declare_what_it_is(tmp_path):
    """`extra="forbid"` is why this test exists: without accepting `kind:`, adding it to a
    registry file would fail to load, and the migration could not be incremental."""
    layer = _layer(tmp_path)
    (layer / "contracts" / "fastqc.yml").write_text(
        _declared(layer / "contracts" / "fastqc.yml", CONTRACT)
    )
    assert layers.load(layer).registry.contracts


def test_a_vocabulary_may_declare_its_own_id(tmp_path):
    """The identity moves off the filename, which is what makes the file portable."""
    layer = _layer(tmp_path)
    (layer / "vocabularies" / "anything-at-all.yml").write_text(
        _declared(
            layer / "vocabularies" / "anything-at-all.yml",
            "declares: vocabulary\nid: genome.index.star\nstates: []\n")
    )
    assert "genome.index.star" in layers.load(layer).vocabulary.types


def test_a_vocabulary_without_an_id_is_refused(tmp_path):
    """The filename fallback existed only to make the migration incremental, and it is gone.

    Once a file may live anywhere, the filename is a poor name for a type:
    `align.type.yml` inside a tool folder would silently declare a type called `align.type`.
    """
    layer = _layer(tmp_path)
    (layer / "vocabularies" / "genome.index.star.yml").write_text(
        _declared(
            layer / "vocabularies" / "genome.index.star.yml",
            "declares: vocabulary\nstates: []\n")
    )
    assert "MD0012" in _refusal(layer)


def test_a_measurement_may_declare_its_own_id(tmp_path):
    layer = _layer(tmp_path)
    (layer / "measurements" / "whatever.yml").write_text(
        _declared(
            layer / "measurements" / "whatever.yml",
            "declares: measurement\nid: read_length\nkind: integer\n"
        "per_sample: true\nminimum: 1\nunit: bp\ndescription: 'test'\ncite: 'test'\n")
    )
    loaded = layers.load(layer)
    # The id comes from the file, not from `whatever.yml`, which is the whole point.
    assert "read_length" in loaded.measurements.ids()


def test_the_real_registry_still_loads():
    """The thing every other test rests on."""
    assert layers.load(ROOT / "registry").registry.contracts


# --- the loader reads the file, not the folder ---

def _flat(root: pathlib.Path, **files: str) -> pathlib.Path:
    """A layer with no structure at all: everything in one folder."""
    layer = root / "flat"
    layer.mkdir(parents=True)
    (layer / "registry.yml").write_text(_declared(layer / "registry.yml", "name: flat\n"))
    for name, body in files.items():
        (layer / f"{name}.yml").write_text(_declared(layer / f"{name}.yml", body))
    return layer


def test_a_layer_may_be_arranged_any_way_at_all(tmp_path):
    """The point of the whole change. One flat folder, no kind directories, and it loads."""
    layer = _flat(tmp_path, anything=CONTRACT, whatever=TYPE, other=REPORT, jobs=ROLES)
    assert layers.load(layer).registry.contracts


def test_deeply_nested_is_just_as_good(tmp_path):
    """The convention this project documents groups by tool; the loader must not care."""
    layer = tmp_path / "nested"
    (layer / "tools" / "nf-core" / "fastqc").mkdir(parents=True)
    (layer / "shared").mkdir()
    (layer / "registry.yml").write_text(_declared(layer / "registry.yml", "name: nested\n"))
    (layer / "tools" / "nf-core" / "fastqc" / "align.contract.yml").write_text(
        _declared(
            layer / "tools" / "nf-core" / "fastqc" / "align.contract.yml",
            CONTRACT))
    (layer / "shared" / "types.yml").write_text(_declared(layer / "shared" / "types.yml", TYPE))
    (layer / "shared" / "report.yml").write_text(_declared(layer / "shared" / "report.yml", REPORT))
    (layer / "shared" / "roles.yml").write_text(_declared(layer / "shared" / "roles.yml", ROLES))
    assert layers.load(layer).registry.contracts


def test_moving_a_file_changes_what_the_layer_digests_to(tmp_path):
    """Two layers, same bytes, different folders: they *load* identically and *digest*
    differently.

    Both are intended and it is worth stating so nobody "fixes" the second. The layout is free
    because nothing reads it; the digest still covers names because a layer is distributed as a
    unit and moving a file is a change to that unit.
    """
    from comeni_core.artifact.digest import digest_of_directory

    one = _flat(tmp_path / "a", thing=CONTRACT, t=TYPE, r=REPORT, j=ROLES)
    two = tmp_path / "b" / "flat"
    (two / "deep").mkdir(parents=True)
    (two / "registry.yml").write_text(_declared(two / "registry.yml", "name: flat\n"))
    (two / "deep" / "thing.yml").write_text(_declared(two / "deep" / "thing.yml", CONTRACT))
    for name, body in (("t", TYPE), ("r", REPORT), ("j", ROLES)):
        (two / f"{name}.yml").write_text(_declared(two / f"{name}.yml", body))

    assert layers.load(one).registry.contracts == layers.load(two).registry.contracts
    assert digest_of_directory(one) != digest_of_directory(two)


def test_MD0010_a_declared_file_must_say_what_it_is(tmp_path):
    layer = _flat(tmp_path, anything=CONTRACT, whatever=TYPE, other=REPORT, jobs=ROLES)
    (layer / "mystery.yml").write_text(_declared(layer / "mystery.yml", "some: mapping\n"))
    message = _refusal(layer)
    assert "MD0010" in message and "mystery.yml" in message


def test_MD0011_a_declared_file_must_name_a_kind_that_exists(tmp_path):
    layer = _flat(tmp_path, anything=CONTRACT, whatever=TYPE, other=REPORT, jobs=ROLES)
    (layer / "typo.yml").write_text(_declared(layer / "typo.yml", "declares: contrat\nid: x\n"))
    message = _refusal(layer)
    assert "MD0011" in message and "typo.yml" in message and "contrat" in message


def test_MD0012_a_vocabulary_must_declare_its_id(tmp_path):
    """Once the folder means nothing, so does the filename — `fastq.reads.yml` in a tool
    folder would silently declare a type nobody asked for."""
    layer = _flat(tmp_path, anything=CONTRACT, whatever=TYPE, other=REPORT, jobs=ROLES)
    (layer / "nameless.yml").write_text(
        _declared(
            layer / "nameless.yml",
            "declares: vocabulary\nstates: []\n"))
    message = _refusal(layer)
    assert "MD0012" in message and "nameless.yml" in message


def _refusal(layer: pathlib.Path) -> str:
    import pytest

    with pytest.raises(Exception) as caught:
        layers.load(layer)
    return str(caught.value).replace(str(layer), "<layer>")
