"""Loading declared data refuses with a code, a file name and a fix — `MD0001`–`MD0009`.

Issue #49. Every other stage of a build refuses with a code, a subject and a fix; loading
refused with a Pydantic traceback naming a model class and a field path. That names what shape
was expected, not which of thirty-seven files is the wrong shape, and the file name is exactly
the part a traceback loses.

**Every test asserts the file name as well as the code.** A code that names only a model would
be the same defect wearing a number.
"""

import pathlib

import pytest
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

CONTRACT = """\
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

# One file per type, named for the type id — `_parse_type` takes the id from the filename.
TYPES = {"fastq.reads": "states: [trimmed]\nentry_channel: \"Channel.empty(params.{param})\"\n",
         "qc.report": "states: []\n"}

ROLES = "declares: role\nroles: [qc_per_sample]\n"


def _layer(root: pathlib.Path) -> pathlib.Path:
    """A minimal layer that loads cleanly, for each test to break one way."""
    layer = root / "registry"
    for kind in ("contracts", "vocabularies", "rules", "measurements", "roles"):
        (layer / kind).mkdir(parents=True)
    for type_id, body in TYPES.items():
        (layer / "vocabularies" / f"{type_id}.yml").write_text(
            _declared(layer / "vocabularies" / f"{type_id}.yml", body)
        )
    # At the layer root, so nothing above it names a kind — it declares explicitly.
    (layer / "roles.yml").write_text(ROLES)
    (layer / "registry.yml").write_text(_declared(layer / "registry.yml", "name: test-layer\n"))
    return layer


def _refusal(layer: pathlib.Path) -> str:
    """The refusal message, with the temporary path scrubbed out.

    **Scrubbed because pytest names `tmp_path` after the test that asked for it.** A message
    quoting the layer path therefore contains the string `MD0004` inside
    `/tmp/pytest-of-…/test_MD0004_a_layer_contains_0/registry`, so `assert "MD0004" in
    message` passed before the code existed. Two of these nine tests were green on a first
    run for exactly that reason, which is the same shape as a guard checking a name against
    itself (A68).
    """
    with pytest.raises(Exception) as caught:
        layers.load(layer)
    return str(caught.value).replace(str(layer), "<layer>").replace(str(layer.parent), "<tmp>")


def test_the_baseline_layer_loads():
    """Every test below breaks this layer one way. If it does not load, they prove nothing."""
    import tempfile

    layer = _layer(pathlib.Path(tempfile.mkdtemp()))
    (layer / "contracts" / "fastqc.yml").write_text(
        _declared(layer / "contracts" / "fastqc.yml", CONTRACT)
    )
    assert layers.load(layer).registry.contracts


def test_MD0001_a_declared_file_is_not_valid_yaml(tmp_path):
    layer = _layer(tmp_path)
    (layer / "contracts" / "broken.yml").write_text(
        _declared(layer / "contracts" / "broken.yml", "id: [unclosed\n")
    )
    message = _refusal(layer)
    assert "MD0001" in message
    assert "broken.yml" in message


def test_MD0002_a_declared_file_does_not_match_its_schema(tmp_path):
    layer = _layer(tmp_path)
    (layer / "contracts" / "wrong.yml").write_text(
        _declared(layer / "contracts" / "wrong.yml", "id: nf-core/x@1.0.0\n")
    )
    message = _refusal(layer)
    assert "MD0002" in message
    assert "wrong.yml" in message


def test_a_misfiled_document_is_caught_by_what_it_declares(tmp_path):
    """`MD0003` used to catch this and is retired — comeni-registry#1.

    A `.yml` in a misspelled directory was refused because *nothing read it*: the directory was
    how a file said what it was, so `contract/` for `contracts/` made it invisible (A26). Now a
    file says what it is, so a misspelled directory is not an error at all — the file loads from
    wherever it sits. What is caught instead is a file that declares nothing.

    That is the trade the spec named: the layout could not be wrong before, and now it cannot
    matter. A misfiled document is detected by its missing declaration rather than prevented by
    its position.
    """
    layer = _layer(tmp_path)
    (layer / "contract").mkdir()
    (layer / "contract" / "typo.yml").write_text(CONTRACT)
    message = _refusal(layer)
    assert "MD0010" in message and "typo.yml" in message


def test_a_declared_file_in_a_misspelled_directory_simply_loads(tmp_path):
    """The other half, which is the point of the change rather than its cost."""
    layer = _layer(tmp_path)
    (layer / "contract").mkdir()
    (layer / "contract" / "typo.yml").write_text("declares: contract\n" + CONTRACT)
    assert layers.load(layer).registry.contracts

def test_MD0004_a_layer_contains_a_symlink(tmp_path):
    layer = _layer(tmp_path)
    outside = tmp_path / "outside.yml"
    outside.write_text(_declared(outside, CONTRACT))
    (layer / "contracts" / "link.yml").symlink_to(outside)
    message = _refusal(layer)
    assert "MD0004" in message
    assert "link.yml" in message


def test_MD0005_a_layer_holds_no_declared_data(tmp_path):
    empty = tmp_path / "registry"
    empty.mkdir()
    message = _refusal(empty)
    assert "MD0005" in message
    assert "git submodule update --init" in message


def test_MD0006_a_key_declared_twice_in_one_layer(tmp_path):
    layer = _layer(tmp_path)
    (layer / "contracts" / "one.yml").write_text(
        _declared(layer / "contracts" / "one.yml", CONTRACT)
    )
    (layer / "contracts" / "two.yml").write_text(
        _declared(layer / "contracts" / "two.yml", CONTRACT)
    )
    message = _refusal(layer)
    assert "MD0006" in message
    assert "one.yml" in message and "two.yml" in message


def test_MD0007_add_states_carrying_other_fields(tmp_path):
    layer = _layer(tmp_path)
    (layer / "vocabularies" / "fastq.reads.yml").write_text(
        _declared(
            layer / "vocabularies" / "fastq.reads.yml",
            "add_states: [deduped]\nentry_channel: \"Channel.empty(params.{param})\"\n")
    )
    message = _refusal(layer)
    assert "MD0007" in message
    assert "fastq.reads.yml" in message


def test_MD0008_add_states_for_a_type_no_layer_declares(tmp_path):
    layer = _layer(tmp_path)
    (layer / "vocabularies" / "no.such.type.yml").write_text(
        _declared(layer / "vocabularies" / "no.such.type.yml", "add_states: [x]\n")
    )
    message = _refusal(layer)
    assert "MD0008" in message
    assert "no.such.type" in message


def test_MD0009_a_contract_requires_an_undeclared_state(tmp_path):
    layer = _layer(tmp_path)
    (layer / "contracts" / "fastqc.yml").write_text(
        _declared(
            layer / "contracts" / "fastqc.yml",
            CONTRACT.replace("state_required: []", "state_required: [nonexistent]"))
    )
    message = _refusal(layer)
    assert "MD0009" in message
    assert "nonexistent" in message
