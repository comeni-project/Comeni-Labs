"""A proposal becoming a filled scaffold and a filled module.

The claim under all of these is that a model's answer goes in through the same machinery a
curator's does, differing in one argument. A separate path would be a second set of rules about
what a legal fill is, and the two would drift in the direction that makes the model's work
easier to accept.
"""

import pytest
from comeni_core.review import ValueSource
from mendel_forge.ai import render
from mendel_forge.ai.schemas import Analysis, Answer, ModuleProposal, Proposal, Unresolved
from mendel_forge.hole_manifest import HoleKind, ScaffoldHole
from mendel_forge.modulegen import INPUT_HOLE, OUTPUT_HOLE, SCRIPT_HOLE


@pytest.mark.parametrize(
    "pointer,field",
    [
        ("/consumes/0/type_id", "consumes[0].type_id"),
        ("/produces/12/name", "produces[12].name"),
        ("/roles", "roles"),
        ("/nf_process", "nf_process"),
    ],
)
def test_a_pointer_becomes_the_field_name_the_scaffold_is_keyed_by(pointer, field):
    """The one place the two spellings meet. `bundle.derive` left them unconverted on purpose,
    with a note that this is where the conversion belongs — a hole id has to survive a channel
    being added upstream, and a field name has to be the key `assemble.contract_from` reads."""
    assert render.field_for(pointer) == field


def test_a_pointer_that_addresses_nothing_the_scaffold_has_is_refused():
    """Silently producing a field name from a malformed pointer would fill a key nothing reads,
    and the answer would then be missing from the contract with no error anywhere."""
    with pytest.raises(ValueError, match="not a pointer this scaffold can address"):
        render.field_for("/consumes/0/type_id/extra")


def _hole(hole_id="consumes.reads.type_id", pointer="/consumes/0/type_id", **overrides):
    base = {
        "id": hole_id,
        "pointer": pointer,
        "kind": HoleKind.TYPE,
        "question": "the semantic type",
        "why_open": "a suffix is not a type",
        "legal_values": ("fastq.reads",),
    }
    return ScaffoldHole(**{**base, **overrides})


class _Recorded:
    """A stand-in for `Scaffold` that records how `fill` was called.

    A real `Scaffold` needs an `Observation` and a registry to be interesting, and none of the
    claims here are about what a scaffold does with a value — they are about what `apply` hands
    it, which is exactly what a real one would hide behind a successful fill.
    """

    def __init__(self):
        self.calls = []

    def fill(self, field, value, how, *, by, why):
        self.calls.append({"field": field, "value": value, "how": how, "by": by, "why": why})
        return self


def _proposal(*answers, unresolved=(), module=None):
    return Proposal(
        analysis=Analysis(answers=answers, unresolved=unresolved), module=module
    )


def test_a_model_fill_is_recorded_as_a_model_fill():
    """`ValueSource.MODEL` is the whole difference from a curator's fill, and it is what keeps
    `human_override` meaning what it says. A pipeline an agent assembled must not read as one a
    person drew by hand."""
    scaffold = _Recorded()
    render.apply(
        scaffold,
        _proposal(Answer(hole_id="consumes.reads.type_id", value="fastq.reads")),
        holes=[_hole()],
        by="ollama/qwen2.5-coder",
    )
    (call,) = scaffold.calls
    assert call["how"] is ValueSource.MODEL
    assert call["by"] == "ollama/qwen2.5-coder"
    assert call["field"] == "consumes[0].type_id"


def test_an_answer_with_no_reason_still_records_where_it_came_from():
    """`why` is the citation beside a value, and an empty one is a value with no reason — which
    is exactly what Plan 1.14 spent a plan closing on the build path."""
    scaffold = _Recorded()
    render.apply(
        scaffold,
        _proposal(
            Answer(hole_id="consumes.reads.type_id", value="fastq.reads", evidence_ids=("E001",))
        ),
        holes=[_hole()],
        by="m",
    )
    assert "E001" in scaffold.calls[0]["why"]


def test_answers_are_applied_in_a_deterministic_order():
    """Two runs over the same proposal must produce the same scaffold. A dict's iteration order
    is insertion order, which here is whatever order the model happened to emit."""
    holes = [_hole("b.type_id", "/consumes/1/type_id"), _hole("a.type_id", "/consumes/0/type_id")]
    answers = (
        Answer(hole_id="b.type_id", value="fastq.reads"),
        Answer(hole_id="a.type_id", value="fastq.reads"),
    )
    scaffold = _Recorded()
    render.apply(scaffold, _proposal(*answers), holes=holes, by="m")
    assert [c["field"] for c in scaffold.calls] == ["consumes[0].type_id", "consumes[1].type_id"]


def test_an_unresolved_item_fills_nothing():
    """The hole stays open, which is what a curator then sees: the question, the model's
    `needed_evidence`, and the same *Ask* it had before. Filling it with a placeholder would
    turn a declined question into a settled value nobody chose."""
    scaffold = _Recorded()
    render.apply(
        scaffold,
        _proposal(unresolved=(Unresolved(hole_id="consumes.reads.type_id", needed_evidence="x"),)),
        holes=[_hole()],
        by="m",
    )
    assert scaffold.calls == []


def test_an_answer_with_no_hole_refuses_rather_than_being_skipped():
    """`admit()` should have caught it first; this is the second line, and it refuses rather
    than dropping — a silently skipped answer is a contract missing a field for no recorded
    reason."""
    with pytest.raises(ValueError, match="MF0402"):
        render.apply(
            _Recorded(),
            _proposal(Answer(hole_id="not.a.hole", value="fastq.reads")),
            holes=[_hole()],
            by="m",
        )


SKELETON = f"""process CLUSTALW_ALIGN {{
    container 'quay.io/biocontainers/clustalw@sha256:abc'

    input:
{INPUT_HOLE}

    output:
{OUTPUT_HOLE}

    script:
    \"\"\"
{SCRIPT_HOLE}
    \"\"\"
}}
"""


def test_a_filled_section_replaces_its_marker():
    """Substitution rather than regeneration. The skeleton carries the container reference and
    the process name that were *derived*, and a model returning whole module text could move
    either — the diff a reviewer reads would then be against nothing."""
    text = render.module_text(
        SKELETON,
        _proposal(module=ModuleProposal(script="clustalw2 -INFILE=$reads $args")),
    )
    assert "clustalw2 -INFILE=$reads $args" in text
    assert SCRIPT_HOLE not in text
    assert "sha256:abc" in text
    assert "CLUSTALW_ALIGN" in text


def test_an_unfilled_section_keeps_its_marker():
    """**An empty section must stay a marked hole.** An empty `script:` is a process that runs
    nothing and reports success, which a stub gate cannot see either — so the marker, and the
    `MF0005` it carries, has to survive."""
    text = render.module_text(SKELETON, _proposal(module=ModuleProposal(script="   ")))
    assert SCRIPT_HOLE in text
    assert render.still_open(text) == (SCRIPT_HOLE, INPUT_HOLE, OUTPUT_HOLE)


def test_a_partly_filled_module_reports_exactly_what_is_still_open():
    """A rung that scanned for two of three markers would pass a module whose outputs were
    still a guess, and it would pass silently."""
    text = render.module_text(
        SKELETON,
        _proposal(
            module=ModuleProposal(script="clustalw2", input_block="    path(reads)")
        ),
    )
    assert render.still_open(text) == (OUTPUT_HOLE,)


def test_a_proposal_with_no_module_leaves_the_skeleton_alone():
    """An nf-core source ships its own process, and §5.6 says the prompt must not emit
    replacement Nextflow. Returning the skeleton unchanged means the caller does not branch."""
    assert render.module_text(SKELETON, _proposal()) == SKELETON
