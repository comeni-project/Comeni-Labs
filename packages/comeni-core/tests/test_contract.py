import pytest
from comeni_core.contract import ModuleContract
from comeni_core.vocabulary import UnknownStateError, Vocabulary


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
    (_v(tmp_path) / "alignment.bam.yml").write_text("states: [coordinate_sorted, name_sorted]\n")
    return Vocabulary.load(tmp_path)


def test_loads_a_contract(tmp_path, vocab):
    path = tmp_path / "sort.yml"
    path.write_text(CONTRACT_YAML)
    contract = ModuleContract.load(path, vocab)
    assert contract.id == "nf-core/samtools/sort@1.21.0"
    assert contract.nf_process == "SAMTOOLS_SORT"
    assert contract.produces[0].state == frozenset({"coordinate_sorted"})
    assert contract.consumes[0].state_required == frozenset()


def test_rejects_contract_using_undeclared_state(tmp_path, vocab):
    path = tmp_path / "bad.yml"
    path.write_text(CONTRACT_YAML.replace("coordinate_sorted", "sorted_by_coord"))
    with pytest.raises(UnknownStateError, match="sorted_by_coord"):
        ModuleContract.load(path, vocab)


def test_input_port_defaults_preferred_to_empty(tmp_path, vocab):
    path = tmp_path / "sort.yml"
    path.write_text(CONTRACT_YAML)
    contract = ModuleContract.load(path, vocab)
    assert contract.consumes[0].state_preferred == frozenset()


def test_carries_the_container_reference(tmp_path, vocab):
    """The lockfile pins container digests; the contract is where the reference starts."""
    path = tmp_path / "sort.yml"
    path.write_text(CONTRACT_YAML)
    contract = ModuleContract.load(path, vocab)
    assert contract.container == "quay.io/biocontainers/samtools:1.21--h50ea8bc_0"


def test_container_is_optional(tmp_path, vocab):
    path = tmp_path / "no-container.yml"
    path.write_text(
        "\n".join(
            line for line in CONTRACT_YAML.splitlines() if not line.startswith("container:")
        )
    )
    assert ModuleContract.load(path, vocab).container is None
