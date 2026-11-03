"""Evidence is from source, with whole identifiers and stable line numbers."""

from mendel_forge.forging.context import uses
from support.paths import ROOT


def test_uses_does_not_match_a_longer_identifier():
    found = uses('path reads\npath reads_index\necho $reads\nreads2 = reads_index', 'reads')
    assert [(line.number, line.text) for line in found] == [(1, 'path reads'), (3, 'echo $reads')]


def test_uses_finds_a_real_module_emit():
    source = ROOT / 'packages/mendel-forge/tests/fixtures/nf-core/bwa/mem/main.nf'
    script = source.read_text()
    found = uses(script, 'bam')
    assert found
    assert any('emit:' in line.text for line in found)
    assert all(script.splitlines()[line.number - 1] == line.text for line in found)
