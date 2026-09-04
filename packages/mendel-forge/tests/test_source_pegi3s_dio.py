"""PEGiS's central metadata and its classification ontology.

**The split between `dio.obo` and `dio.diaf` is what these tests are about.** The first defines
the hierarchical filter vocabulary; the second performs the many-to-many tool assignments. A
parser that conflated them would still pass a test asserting `fastqc` has a category, and would
fail every test here about hierarchy, identity or provenance.

Fixtures carry the real properties the upstream data has: `fastqc` directly under
`DIO:0000036` (`Quality`), `seda` with more than one classification, and two distinct terms both
displayed as `Alignment` under different branches.
"""

from pathlib import Path

import pytest
from mendel_forge.sources.dio import (
    FACT_FIELDS,
    Entry,
    normalise,
    parse_diaf,
    parse_metadata,
    parse_obo,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sources"

TOOLS = ("fastqc", "clustalw", "seda", "prodigal", "orphanimage")


def _obo():
    return parse_obo((FIXTURES / "pegi3s_dio.obo").read_text())


def _diaf(ontology, tools=TOOLS):
    return parse_diaf((FIXTURES / "pegi3s_dio.diaf").read_text(), ontology.terms, tools)


# ── metadata.json ──────────────────────────────────────────────────────────────────────


def test_metadata_is_an_array_indexed_by_name():
    entries, warnings = parse_metadata((FIXTURES / "pegi3s_metadata.json").read_text())
    assert set(entries) == {"fastqc", "clustalw", "seda"}
    assert entries["fastqc"].name == "fastqc"
    assert warnings == ()


def test_metadata_carries_the_declared_fields_in_order():
    entries, _ = parse_metadata((FIXTURES / "pegi3s_metadata.json").read_text())
    facts = dict(entries["fastqc"].facts())
    assert facts["status"] == "OK"
    assert facts["manual_url"].startswith("https://")
    assert facts["input_data_type"] == "FASTQ, BAM"
    assert "gui_command" not in facts, "an empty gui_command became a value"
    assert facts["invocation_general"].startswith("docker run")
    assert [name for name, _ in entries["fastqc"].facts()] == sorted(
        (name for name, _ in entries["fastqc"].facts()),
        key=FACT_FIELDS.index,
    ), "facts are not in the declared field order"


def test_an_absent_field_is_absent_rather_than_invented():
    """§3: do not invent values for absent fields."""
    entries, _ = parse_metadata((FIXTURES / "pegi3s_metadata.json").read_text())
    facts = dict(entries["clustalw"].facts())
    assert "manual_url" not in facts
    assert "invocation_general" not in facts


def test_an_explicitly_empty_field_reads_as_unknown():
    """`bug_found: ""` upstream is an unknown, not a claim that the string is empty."""
    entries, _ = parse_metadata((FIXTURES / "pegi3s_metadata.json").read_text())
    facts = dict(entries["fastqc"].facts())
    assert "bug_found" not in facts
    assert "comments" not in facts


def test_a_false_boolean_reads_as_unknown_and_a_true_one_is_kept():
    entries, _ = parse_metadata((FIXTURES / "pegi3s_metadata.json").read_text())
    fastqc = dict(entries["fastqc"].facts())
    seda = dict(entries["seda"].facts())
    assert "gui" not in fastqc, "gui: false became a value"
    assert seda["gui"] == "true"


def test_a_list_field_is_rendered_canonically():
    entries, _ = parse_metadata((FIXTURES / "pegi3s_metadata.json").read_text())
    assert dict(entries["fastqc"].facts())["recommended"] == "0.11.9"


def test_an_unknown_upstream_key_is_tolerated():
    """PEGiS extends `metadata.json` on its own schedule. Refusing a sync because a field was
    added would make every future improvement upstream an outage here."""
    entries, warnings = parse_metadata('[{"name": "x", "something_new": "value"}]')
    assert set(entries) == {"x"}
    assert warnings == ()


def test_malformed_metadata_warns_rather_than_raising():
    entries, warnings = parse_metadata("not json at all")
    assert entries == {}
    assert warnings and warnings[0].code == "MF0205"


def test_a_metadata_object_that_is_not_an_array_warns():
    entries, warnings = parse_metadata('{"name": "x"}')
    assert entries == {}
    assert "not an array" in warnings[0].detail


def test_a_duplicated_metadata_name_keeps_the_first_and_says_so():
    entries, warnings = parse_metadata('[{"name": "x", "status": "a"}, {"name": "x"}]')
    assert dict(entries["x"].facts())["status"] == "a"
    assert any("more than once" in w.detail for w in warnings)


# ── dio.obo ────────────────────────────────────────────────────────────────────────────


def test_terms_and_their_parents_parse():
    ontology, _ = _obo()
    quality = ontology.get("DIO:0000036")
    assert quality is not None
    assert quality.name == "Quality"
    assert quality.definition == "Quality assessment of short reads."
    assert quality.parents == ("DIO:0000010",)


def test_a_parent_reference_drops_its_obo_annotation():
    """OBO writes `is_a: DIO:0000004 ! Sequences`. Keeping the comment would make the parent id
    a different string after a cosmetic rename, reparenting the whole subtree."""
    ontology, _ = _obo()
    assert ontology.get("DIO:0000010").parents == ("DIO:0000004",)


def test_a_root_term_has_no_parents():
    ontology, _ = _obo()
    assert ontology.get("DIO:0000001").parents == ()
    assert set(ontology.roots()) == {"DIO:0000001", "DIO:0000050"}


def test_a_typedef_stanza_is_skipped_rather_than_refused():
    """`[Typedef]` is legal OBO and carries no filter meaning."""
    ontology, warnings = _obo()
    assert "part_of" not in ontology.terms
    assert not any("part_of" in w.detail for w in warnings)


def test_ancestry_is_nearest_first():
    ontology, _ = _obo()
    assert ontology.ancestors("DIO:0000036") == (
        "DIO:0000010",
        "DIO:0000004",
        "DIO:0000001",
    )


def test_the_breadcrumb_reads_root_first():
    ontology, _ = _obo()
    assert ontology.path("DIO:0000036") == (
        "Data_type",
        "Sequences",
        "Short_reads",
        "Quality",
    )


def test_two_terms_with_the_same_name_stay_distinct():
    """The property that makes the display name unusable as a key.

    PEGiS has more than one `Alignment`. Keying on the name merges them into one filter with
    two meanings, and a tool then appears under a branch nobody assigned it to.
    """
    ontology, _ = _obo()
    first, second = ontology.get("DIO:0000051"), ontology.get("DIO:0000052")
    assert first.name == second.name == "Alignment"
    assert first.id != second.id
    assert first.parents != second.parents
    assert ontology.path("DIO:0000051") != ontology.path("DIO:0000052")
    assert ontology.path("DIO:0000051") == ("Analysis", "Alignment")
    assert ontology.path("DIO:0000052") == ("Data_type", "Sequences", "Alignment")


def test_a_term_with_several_parents_keeps_all_of_them():
    ontology, _ = parse_obo(
        "[Term]\nid: DIO:1\nname: A\n\n"
        "[Term]\nid: DIO:2\nname: B\n\n"
        "[Term]\nid: DIO:3\nname: C\nis_a: DIO:1 ! A\nis_a: DIO:2 ! B\n"
    )
    assert ontology.get("DIO:3").parents == ("DIO:1", "DIO:2")
    assert set(ontology.ancestors("DIO:3")) == {"DIO:1", "DIO:2"}


def test_a_cycle_terminates_rather_than_recursing_forever():
    """Defensive: an OBO file is hand-maintained and `A is_a B`, `B is_a A` is one edit away.
    A naive walk would recurse until the process died."""
    ontology, _ = parse_obo(
        "[Term]\nid: DIO:1\nname: A\nis_a: DIO:2\n\n[Term]\nid: DIO:2\nname: B\nis_a: DIO:1\n"
    )
    assert set(ontology.ancestors("DIO:1")) == {"DIO:2"}
    assert ontology.path("DIO:1")


def test_a_dangling_parent_is_reported():
    ontology, warnings = parse_obo("[Term]\nid: DIO:1\nname: A\nis_a: DIO:404 ! Missing\n")
    assert ontology.get("DIO:1").parents == ("DIO:404",)
    assert any(w.code == "MF0206" and "DIO:404" in w.detail for w in warnings)


def test_a_duplicated_term_id_keeps_the_first_and_says_so():
    ontology, warnings = parse_obo(
        "[Term]\nid: DIO:1\nname: First\n\n[Term]\nid: DIO:1\nname: Second\n"
    )
    assert ontology.get("DIO:1").name == "First"
    assert any(w.code == "MF0206" for w in warnings)


def test_a_stanza_with_no_id_is_reported_not_fatal():
    ontology, warnings = parse_obo("[Term]\nname: Nameless\n\n[Term]\nid: DIO:1\nname: A\n")
    assert set(ontology.terms) == {"DIO:1"}
    assert any("declares no id" in w.detail for w in warnings)


# ── dio.diaf ───────────────────────────────────────────────────────────────────────────


def test_the_two_column_mapping_parses():
    ontology, _ = _obo()
    assignments, _ = _diaf(ontology)
    assert assignments.for_tool("fastqc") == ("DIO:0000036",)


def test_a_tool_with_several_classifications_keeps_all_of_them():
    ontology, _ = _obo()
    assignments, _ = _diaf(ontology)
    assert assignments.for_tool("seda") == ("DIO:0000052", "DIO:0000060")


def test_a_repeated_identical_assignment_is_deduplicated_silently():
    """The fixture lists `DIO:0000060 seda` twice. A harmless upstream duplicate is not
    something a reader needs told about."""
    ontology, _ = _obo()
    assignments, warnings = _diaf(ontology)
    assert assignments.for_tool("seda").count("DIO:0000060") == 1
    assert not any("DIO:0000060" in w.detail for w in warnings)


def test_an_unknown_ontology_id_warns_and_does_not_crash():
    ontology, _ = _obo()
    assignments, warnings = _diaf(ontology)
    assert "DIO:0009999" not in assignments.for_tool("fastqc")
    assert any(w.code == "MF0205" and "DIO:0009999" in w.detail for w in warnings)


def test_an_unknown_tool_warns_and_creates_nothing():
    """§7: a fabricated entry would be a tool somebody can click and never run."""
    ontology, _ = _obo()
    assignments, warnings = _diaf(ontology)
    assert "nosuchtool" not in assignments.by_tool
    assert any(w.code == "MF0207" and "nosuchtool" in w.detail for w in warnings)


def test_a_tool_with_no_assignment_has_none():
    ontology, _ = _obo()
    assignments, _ = _diaf(ontology)
    assert assignments.for_tool("prodigal") == ()


def test_comments_and_blank_lines_are_skipped():
    ontology, _ = _obo()
    _, warnings = _diaf(ontology)
    assert not any("line 1" in w.detail for w in warnings), "the header comment was parsed"


def test_a_malformed_line_is_reported_and_the_rest_still_parse():
    ontology, _ = _obo()
    assignments, warnings = parse_diaf(
        "DIO:0000036\tfastqc\ngarbage\nDIO:0000051\tclustalw\n",
        ontology.terms,
        TOOLS,
    )
    assert assignments.for_tool("fastqc") == ("DIO:0000036",)
    assert assignments.for_tool("clustalw") == ("DIO:0000051",)
    assert any(w.code == "MF0205" for w in warnings)


def test_a_whitespace_separated_line_is_still_read():
    """A hand-edited file loses tabs to an editor, and refusing the whole line would drop a
    real assignment over a formatting slip."""
    ontology, _ = _obo()
    assignments, _ = parse_diaf("DIO:0000036   fastqc\n", ontology.terms, TOOLS)
    assert assignments.for_tool("fastqc") == ("DIO:0000036",)


def test_a_line_not_beginning_with_a_dio_id_is_refused():
    ontology, _ = _obo()
    assignments, warnings = parse_diaf("fastqc\tDIO:0000036\n", ontology.terms, TOOLS)
    assert assignments.by_tool == {}
    assert any("does not begin with" in w.detail for w in warnings)


def test_tool_names_are_matched_case_insensitively():
    ontology, _ = _obo()
    assignments, _ = parse_diaf("DIO:0000036\tFastQC\n", ontology.terms, TOOLS)
    assert assignments.for_tool("fastqc") == ("DIO:0000036",)


def test_normalisation_does_no_more_than_case_and_trim():
    """Anything cleverer — stripping punctuation, collapsing separators — joins two genuinely
    different tools and produces a classification nobody assigned."""
    assert normalise(" FastQC ") == "fastqc"
    assert normalise("bwa-mem") != normalise("bwa_mem")


def test_an_entry_with_no_name_is_refused():
    with pytest.raises(ValueError):
        Entry(name="   ")
