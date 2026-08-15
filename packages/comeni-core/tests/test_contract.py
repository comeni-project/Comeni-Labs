import pathlib

import pytest
from comeni_core.declared.contract import ModuleContract
from comeni_core.declared.vocabulary import UnknownStateError, Vocabulary

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
    # `contracts/nf-core/fastqc.yml` sits two levels down from the directory that names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


def _v(root):
    """The layer's `vocabularies/` directory. `Vocabulary.load` takes the layer root."""
    directory = root / "vocabularies"
    directory.mkdir(exist_ok=True)
    return directory

CONTRACT_YAML = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes:
  - name: bam
    type_id: alignment.bam
    state_required: []
produces:
  - name: bam
    type_id: alignment.bam
    state: [coordinate_sorted]
params: []
priority: 0
container: quay.io/biocontainers/samtools:1.21--h50ea8bc_0
provenance:
  source: nf-core-meta-yml
  drafted_by: hand
  approved_by: rafael
  approved_at: "2026-08-02"
"""


@pytest.fixture
def vocab(tmp_path):
    (_v(tmp_path) / "alignment.bam.yml").write_text(
        _declared(
            _v(tmp_path) / "alignment.bam.yml",
            "states: [coordinate_sorted, name_sorted]\n"))
    return Vocabulary.load(tmp_path)


def test_loads_a_contract(tmp_path, vocab):
    path = tmp_path / "sort.yml"
    path.write_text(_declared(path, CONTRACT_YAML))
    contract = ModuleContract.load(path, vocab)
    assert contract.id == "nf-core/samtools/sort@1.21.0"
    assert contract.nf_process == "SAMTOOLS_SORT"
    assert contract.produces[0].state == frozenset({"coordinate_sorted"})
    assert contract.consumes[0].state_required == frozenset()


def test_rejects_contract_using_undeclared_state(tmp_path, vocab):
    path = tmp_path / "bad.yml"
    path.write_text(_declared(path, CONTRACT_YAML.replace("coordinate_sorted", "sorted_by_coord")))
    with pytest.raises(UnknownStateError, match="sorted_by_coord"):
        ModuleContract.load(path, vocab)


def test_input_port_defaults_preferred_to_empty(tmp_path, vocab):
    path = tmp_path / "sort.yml"
    path.write_text(_declared(path, CONTRACT_YAML))
    contract = ModuleContract.load(path, vocab)
    assert contract.consumes[0].state_preferred == frozenset()


def test_carries_the_container_reference(tmp_path, vocab):
    """The lockfile pins container digests; the contract is where the reference starts."""
    path = tmp_path / "sort.yml"
    path.write_text(_declared(path, CONTRACT_YAML))
    contract = ModuleContract.load(path, vocab)
    assert contract.container == "quay.io/biocontainers/samtools:1.21--h50ea8bc_0"


def test_container_is_optional(tmp_path, vocab):
    path = tmp_path / "no-container.yml"
    path.write_text(
        _declared(path, "\n".join(
            line for line in CONTRACT_YAML.splitlines() if not line.startswith("container:")
        ))
    )
    assert ModuleContract.load(path, vocab).container is None
