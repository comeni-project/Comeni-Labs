"""Which facts each tool's code reads, read from the code (#338)."""

import shutil

from mendel_compiler import conformance
from mendel_resolver import layers
from support.paths import ROOT


def _read(root):
    loaded = layers.load(root)
    return conformance.facts_read(loaded.registry, loaded.modules, loaded.measurements)


def test_the_spine_tools_read_what_their_code_reads():
    got = _read(ROOT / "registry")
    assert got, "the shipped registry has contracts"
    by_tool = {cid.split("@")[0]: facts for cid, facts in got.items()}
    assert by_tool["nf-core/subread/featurecounts"] == {"paired", "strandedness"}
    assert by_tool["nf-core/hisat2/align"] == {"paired", "strandedness"}
    assert by_tool["nf-core/star/align"] == {"paired"}
    assert by_tool["nf-core/trimgalore"] == {"paired"}
    assert by_tool["nf-core/fastqc"] == frozenset()


def test_a_tool_whose_source_is_missing_is_none(tmp_path):
    """Review Focus 1: nothing is assumed about a module nobody could read."""
    shutil.copytree(ROOT / "registry", tmp_path / "registry")
    (tmp_path / "registry/tools/nf-core/subread/featurecounts/module/main.nf").unlink()
    got = _read(tmp_path / "registry")
    assert next(v for k, v in got.items() if "featurecounts" in k) is None
