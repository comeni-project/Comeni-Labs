"""`qc.report::assembly`: a type and the states that make it more specific."""

import pytest
from comeni_core.declared.contract import Alternative, InputPort, OutputPort
from comeni_core.declared.signature import join, split
from comeni_core.goal.asked import RequiredStates


def test_a_plain_type_has_no_states():
    assert split("qc.report") == ("qc.report", frozenset())


def test_each_part_after_the_type_is_a_state():
    assert split("alignment.bam::coordinate_sorted::indexed") == (
        "alignment.bam", frozenset({"coordinate_sorted", "indexed"}),
    )


def test_writing_it_back_sorts_the_states():
    assert join("alignment.bam", frozenset({"indexed", "coordinate_sorted"})) == (
        "alignment.bam::coordinate_sorted::indexed"
    )
    assert join("qc.report", frozenset()) == "qc.report"


def test_one_set_of_states_has_one_spelling():
    assert join(*split("a.b::z::c")) == "a.b::c::z"


@pytest.mark.parametrize("bad", ["qc.report::", "::assembly", "qc.report::::assembly"])
def test_an_empty_part_is_refused(bad):
    with pytest.raises(ValueError, match="empty part"):
        split(bad)


def test_an_output_carries_its_states_in_the_type():
    port = OutputPort(name="tsv", type_id="qc.report::assembly")
    assert port.type_id == "qc.report"
    assert port.state == {"assembly"}


def test_an_input_carries_what_it_requires_in_the_type():
    port = InputPort(name="bam", type_id="alignment.bam::coordinate_sorted")
    assert port.type_id == "alignment.bam"
    assert port.state_required == {"coordinate_sorted"}


def test_an_alternative_carries_its_states_in_the_type():
    alternative = Alternative(type_id="alignment.bam::coordinate_sorted")
    assert alternative.states == {"coordinate_sorted"}


def test_the_same_port_in_either_spelling_is_identical():
    new = OutputPort(name="bam", type_id="alignment.bam::coordinate_sorted")
    old = OutputPort(name="bam", type_id="alignment.bam", state=["coordinate_sorted"])
    assert new == old
    assert new.model_dump() == old.model_dump()


def test_states_written_both_ways_are_refused():
    with pytest.raises(ValueError, match="both"):
        OutputPort(name="bam", type_id="alignment.bam::coordinate_sorted", state=["indexed"])


def test_a_goal_can_ask_for_a_kind_of_output():
    wanted = RequiredStates(type_id="counts.matrix::gene_level")
    assert wanted.type_id == "counts.matrix"
    assert wanted.states == ["gene_level"]


def test_an_output_can_say_its_file_formats():
    port = OutputPort(name="index", type_id="alignment.bai", format=["csi", "bai"])
    assert port.model_dump()["format"] == ["bai", "csi"]


def test_an_output_with_no_format_digests_as_before():
    assert "format" not in OutputPort(name="zip", type_id="qc.report").model_dump()
