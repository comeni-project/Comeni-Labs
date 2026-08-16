"""One page per tool, and a tool is what the ids say it is — not what the folders say.

comeni-registry#1 removed the directory's meaning on purpose: a file declares what it is and
the loader never reads its path. Grouping documentation by folder would put path-as-meaning
straight back in, one layer up, in the first thing built after that issue closed.

comeni-registry#2.
"""

from pathlib import Path

from mendel_compiler import tool_docs
from mendel_resolver import layers

ROOT = Path(__file__).parent.parent.parent.parent


def _layers():
    return layers.load([ROOT / "registry"])


def test_a_three_segment_id_groups_under_its_first_two():
    """`nf-core/star/align` and `nf-core/star/genomegenerate` are one tool."""
    tools = tool_docs.tools_of(_layers().registry)
    assert "nf-core/star" in tools
    assert [c.id for c in tools["nf-core/star"]] == [
        "nf-core/star/align@1.11.0",
        "nf-core/star/genomegenerate@1.11.0",
    ]


def test_a_two_segment_id_is_its_own_tool():
    """`nf-core/fastqc` has no third segment. Dropping the last one would say `nf-core`,
    which would collapse every nf-core module onto a single page."""
    tools = tool_docs.tools_of(_layers().registry)
    assert [c.id for c in tools["nf-core/fastqc"]] == ["nf-core/fastqc@0.12.1"]


def test_a_one_segment_key_is_its_own_page_rather_than_a_refusal():
    """No contract has one today, and an in-house `sortmerna@4.3.6` is not obviously wrong,
    so this forbids nothing. Spec §3.1."""
    assert tool_docs._tool_of("sortmerna@4.3.6") == "sortmerna"


def test_the_registry_groups_into_the_eight_pages_the_spec_names():
    tools = tool_docs.tools_of(_layers().registry)
    assert sorted(tools) == [
        "comeni/profile",
        "nf-core/fastqc",
        "nf-core/hisat2",
        "nf-core/multiqc",
        "nf-core/samtools",
        "nf-core/star",
        "nf-core/subread",
        "nf-core/trimgalore",
    ]
