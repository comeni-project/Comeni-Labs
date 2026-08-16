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


def test_a_page_names_every_contract_and_its_process():
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert "# nf-core/star" in page
    assert "`nf-core/star/align@1.11.0`" in page
    assert "STAR_ALIGN" in page
    assert "`nf-core/star/genomegenerate@1.11.0`" in page


def test_a_page_records_ports_with_their_states():
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/samtools", tools["nf-core/samtools"], loaded)
    assert "alignment.bam" in page
    assert "coordinate_sorted" in page


def test_a_page_carries_the_provenance_rather_than_dropping_it():
    """Contracts cite papers and the data is CC-BY. A generated page that drops attribution
    is the one thing this registry's licence exists to prevent."""
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert "approved_by" in page
    assert "drafted_by" in page


def test_a_page_says_when_a_tool_declares_no_parameters():
    """An empty section is a fact — 'this tool settles nothing' — and a page that silently
    omits it reads as though the generator forgot."""
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/multiqc", tools["nf-core/multiqc"], loaded)
    assert "Parameters" in page


def test_a_multi_state_port_renders_in_sorted_order():
    """`--check` compares bytes, and these pages are **committed** — so an unsorted frozenset
    would make CI red on a machine whose `PYTHONHASHSEED` differs from the one that generated
    them. Worse than a reordered diff, and invisible on the machine that wrote it.

    **Constructed rather than taken from the registry, because no port there carries more
    than one state**, and a one-element set has only one order. Against real data this guard
    cannot fail, which would make it inert — A36's shape exactly, and the same answer: invent
    the second case in the test.
    """
    many = frozenset({"name_sorted", "coordinate_sorted", "indexed", "deduplicated"})
    rendered = tool_docs._states(many)
    assert rendered == "`coordinate_sorted`, `deduplicated`, `indexed`, `name_sorted`"


def test_rendering_is_stable_across_two_calls():
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    first = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    second = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert first == second


def test_a_page_says_it_is_generated():
    """`--check` refuses a hand edit, so the page has to tell a reader that before they make
    one. A generated file with no banner is an invitation to lose work."""
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert page.splitlines()[0].startswith("<!--")
    assert "mendel docs" in page.splitlines()[0]


def test_an_absent_tier_hint_is_a_dash_rather_than_the_word_None():
    """`None` is a real answer — the contract offers no hint — but a page a biologist reads
    should not contain a Python literal."""
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert "| None |" not in page
    assert "`star_ignore_sjdbgtf` | — |" in page


def test_a_type_with_one_producer_is_listed_on_that_tools_page():
    loaded = _layers()
    assert tool_docs.sole_types(loaded)["nf-core/star"] == ["genome.index.star"]
    assert tool_docs.sole_types(loaded)["nf-core/subread"] == ["counts.matrix"]


def test_a_type_two_tools_produce_is_listed_on_neither():
    """`alignment.bam` comes from both star and hisat2, so it is not either one's to claim."""
    loaded = _layers()
    owned = tool_docs.sole_types(loaded)
    for tool in ("nf-core/star", "nf-core/hisat2"):
        assert "alignment.bam" not in owned.get(tool, [])


def test_a_tool_a_rule_pins_says_so():
    """A contract selected by a tier-3 implementation rule is one whose selection is not
    free, and a reader deciding whether to use it should be told."""
    loaded = _layers()
    assert tool_docs.rules_naming(loaded)["nf-core/star"]


def test_a_tool_no_rule_names_has_no_entry():
    loaded = _layers()
    assert tool_docs.rules_naming(loaded).get("nf-core/multiqc") in (None, [])


def test_the_page_shows_both_cross_references():
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/star", tools["nf-core/star"], loaded)
    assert "genome.index.star" in page
    assert "Types only this tool produces" in page
    assert "Rules that select this tool" in page


def test_a_tool_owning_no_type_says_none_rather_than_omitting_the_section():
    """A missing section reads as a generator that forgot. An explicit 'None.' is a fact."""
    loaded = _layers()
    tools = tool_docs.tools_of(loaded.registry)
    page = tool_docs.render("nf-core/fastqc", tools["nf-core/fastqc"], loaded)
    assert "Types only this tool produces" in page
