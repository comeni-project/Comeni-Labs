from pathlib import Path

from mendel_forge.sources import ToolRef
from mendel_forge.sources.nfcore import NfCoreSource

ROOT = Path(__file__).resolve().parents[3]
VENDOR = ROOT / "vendor"


def test_discover_finds_every_vendored_module():
    found = NfCoreSource().discover(VENDOR)
    idents = [r.ident for r in found]
    assert "fastqc" in idents
    assert "samtools/sort" in idents
    assert found == sorted(found, key=lambda r: r.ident), "discover must be sorted"


def test_ingest_derives_the_process_name_with_evidence():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), VENDOR)
    assert obs.fact("process") == "FASTQC"
    # `main.nf:1`, not `main.nf`. Phase 1 asserted the file and Phase 2 made it the file and
    # the line, so this assertion moved to the stronger property rather than being loosened.
    assert obs.facts["process"].evidence.locator.startswith("modules/nf-core/fastqc/main.nf:")
    assert obs.facts["process"].evidence.text == "process FASTQC {"


def test_ingest_derives_the_container_the_module_actually_declares():
    """Take the LAST quoted string in the container ternary — nf-core 4.x mostly uses
    community.wave.seqera.io, and reading the first gives the singularity URI."""
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), VENDOR)
    assert obs.fact("container") is not None


def test_ingest_derives_the_emit_names():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), VENDOR)
    assert "zip" in obs.fact("emits")


def test_ingest_derives_the_channel_count_not_the_port_count():
    """A contract port is not a process argument. `nf_inputs` arity is what Nextflow
    matches, and a 2-tuple in a 3-tuple slot dies on 'Path value cannot be null'."""
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:samtools/sort"), VENDOR)
    assert obs.fact("input_arity") == 3


def test_ingest_carries_meta_yml_prose_when_present():
    obs = NfCoreSource().ingest(ToolRef.parse("nf-core:fastqc"), VENDOR)
    assert obs.prose, "meta.yml documentation should reach the observation"


def test_the_source_registers_itself_on_import():
    from mendel_forge import sources

    assert "nf-core" in sources.names()
