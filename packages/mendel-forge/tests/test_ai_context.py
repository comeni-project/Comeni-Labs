"""What goes in front of a model, in what order, and what is recorded when something cannot.

These are claims about the *composition*, with no model and no source anywhere in them. That
is the point of building this half first: everything here is checkable before a single
provider call exists, and it is where a prompt stack's defects actually live.
"""

import pytest
from mendel_forge.ai.context import (
    CHARS_PER_TOKEN,
    ORDER,
    Budget,
    Drop,
    Section,
    Segment,
    compose,
    render,
)


def _seg(section: Section, key: str, text: str = "body", **kw) -> Segment:
    return Segment(section=section, key=key, text=text, **kw)


def test_the_sections_are_the_ten_the_plan_names_in_its_order():
    """§5.3 numbers them 1 to 10 and the order is a claim about how a model reads — identity
    before evidence, the response schema second to last, and the task instruction last, where
    it is least likely to be lost behind six pages of vocabulary.

    Asserted literally rather than by count, because a count passes when two are swapped.
    """
    assert [s.value for s in ORDER] == [
        "identity",
        "evidence",
        "facts",
        "holes",
        "registry-version",
        "vocabulary",
        "exemplars",
        "existing-rules",
        "response-schema",
        "task",
    ]


def test_rendering_follows_section_order_not_composition_order():
    """The composer builds sections in whatever order is convenient — a caller that gathers
    exemplars before holes is not wrong, it is just reading a different data source first.
    Letting that reach the prompt would make the context depend on the shape of the code that
    assembled it."""
    out = render(
        [
            _seg(Section.TASK, "task", "LAST"),
            _seg(Section.IDENTITY, "identity", "FIRST"),
            _seg(Section.VOCABULARY, "types", "MIDDLE"),
        ]
    )
    assert out.index("FIRST") < out.index("MIDDLE") < out.index("LAST")


def test_two_composes_over_the_same_segments_render_the_same_bytes():
    """The dossier is stored as a review record and digested for the repair path. If it moved
    between two runs, `prompt_digest` would be a hash of the machine that built it."""
    segments = [
        _seg(Section.EVIDENCE, "E002"),
        _seg(Section.EVIDENCE, "E001"),
        _seg(Section.HOLES, "consumes.reads.type_id"),
    ]
    first = compose(segments, budget=10_000)
    second = compose(list(reversed(segments)), budget=10_000)
    assert first.render() == second.render()
    assert first.manifest.prompt_digest == second.manifest.prompt_digest


def test_an_exemplar_goes_before_any_prose():
    """§5.3's reduction order in one sentence: *drop low-ranked similar contracts first, then
    redundant prose*. `Drop` is an `IntEnum` so this is a sort rather than two branches that
    each have to remember which comes first."""
    big = "x" * 300
    kept = compose(
        [
            _seg(Section.EXEMPLARS, "an-exemplar", big, drop=Drop.EXEMPLAR),
            _seg(Section.EVIDENCE, "E001", big, drop=Drop.PROSE),
            _seg(Section.TASK, "task", big),
        ],
        budget=700,
    )
    assert [o.key for o in kept.manifest.omitted] == ["an-exemplar"]


def test_within_a_class_the_lowest_ranked_goes_first():
    """*Low-ranked* is the plan's word and the ranking is the caller's — this module does no
    scoring, because what makes a contract similar is Forge policy about ports."""
    big = "y" * 300
    kept = compose(
        [
            _seg(Section.EXEMPLARS, "weak", big, drop=Drop.EXEMPLAR, rank=1),
            _seg(Section.EXEMPLARS, "strong", big, drop=Drop.EXEMPLAR, rank=9),
            _seg(Section.TASK, "task", big),
        ],
        budget=700,
    )
    assert [o.key for o in kept.manifest.omitted] == ["weak"]
    assert "strong" in kept.render()


def test_an_omission_names_what_was_dropped_rather_than_counting():
    """A manifest saying *three exemplars were dropped* tells a reviewer that the model saw
    less than the record shows and gives them no way to find out what."""
    big = "z" * 400
    kept = compose(
        [
            _seg(Section.EXEMPLARS, "nf-core/samtools/sort", big, drop=Drop.EXEMPLAR),
            _seg(Section.TASK, "task", "small"),
        ],
        budget=100,
    )
    (only,) = kept.manifest.omitted
    assert only.key == "nf-core/samtools/sort"
    assert only.section is Section.EXEMPLARS
    assert "budget" in only.reason


def test_a_dossier_of_only_protected_sections_refuses_rather_than_truncating():
    """`MF0400`, and it is the load-bearing decision in this module.

    A model shown nine of eleven legal values does not know it was shown nine; it answers
    confidently from what it has and the answer passes every schema check on the way back. A
    truncated candidate set is indistinguishable in the response from a complete one.
    """
    with pytest.raises(ValueError, match="MF0400") as raised:
        compose([_seg(Section.HOLES, "a-hole", "q" * 500)], budget=50)
    assert "holes" in str(raised.value)


def test_the_refusal_names_the_sections_that_could_not_be_given_up():
    """A refusal that says only *it does not fit* leaves whoever reads it to guess which
    section is oversized, and the honest answer is usually an adapter defect upstream."""
    with pytest.raises(ValueError, match="MF0400") as raised:
        compose(
            [
                _seg(Section.HOLES, "a-hole", "q" * 300),
                _seg(Section.VOCABULARY, "types", "t" * 300),
            ],
            budget=50,
        )
    message = str(raised.value)
    assert "holes" in message and "vocabulary" in message


def test_the_digest_is_of_what_survived_rather_than_of_what_was_offered():
    """Otherwise a repair could assert *same dossier* against a hash of context that was
    dropped before the call, which is the one claim §5.7 rests on."""
    segments = [
        _seg(Section.TASK, "task", "keep me"),
        _seg(Section.EXEMPLARS, "dropped", "d" * 400, drop=Drop.EXEMPLAR),
    ]
    whole = compose(segments, budget=10_000)
    reduced = compose(segments, budget=100)
    assert whole.manifest.prompt_digest != reduced.manifest.prompt_digest
    assert reduced.manifest.prompt_digest == compose(
        [_seg(Section.TASK, "task", "keep me")], budget=10_000
    ).manifest.prompt_digest


def test_a_dropped_excerpt_is_not_a_citable_evidence_id():
    """`evidence_ids` reads the kept segments, not the source bundle. A citation of evidence
    that was dropped is exactly as unfollowable for a reviewer as one that was invented, and
    `MF0401` should refuse it either way."""
    reduced = compose(
        [
            _seg(Section.EVIDENCE, "E001", "a" * 400, drop=Drop.PROSE),
            _seg(Section.EVIDENCE, "E002", "b", drop=Drop.PROSE),
            _seg(Section.TASK, "task", "t"),
        ],
        budget=120,
    )
    assert reduced.evidence_ids() == frozenset({"E002"})


def test_a_segment_measures_the_heading_it_will_be_rendered_under():
    """Forty segments carry forty headings. A budget that ignores them is wrong by about a
    section, and it is wrong in the direction that overflows.

    The claim is that the sum is an **upper** bound on the rendered length. Charging each
    segment its own separator over-counts by one separator overall, which is the direction
    that cannot overflow — and it keeps `size()` independent of how many other segments
    survive the reduction, which is what lets it be the sort key that decides.
    """
    segments = [
        _seg(Section.IDENTITY, "identity", "abc"),
        _seg(Section.HOLES, "a-hole", "defgh"),
        _seg(Section.TASK, "task", "ij"),
    ]
    assert sum(s.size() for s in segments) >= len(render(segments))
    assert all(s.size() > len(s.text) for s in segments)


def test_a_key_with_stray_whitespace_is_refused():
    """The key is an address: it goes in the manifest, is cited in a review, and is matched
    when a prompt is regenerated. One with a trailing space matches nothing and looks
    identical to one that would."""
    with pytest.raises(ValueError, match="usable as an address"):
        _seg(Section.EVIDENCE, "E001 ")


def test_a_budget_holds_room_back_for_the_answer():
    """A context window is shared between the prompt and the response, and a dossier sized to
    the whole window leaves no room to be answered in."""
    assert Budget(tokens=10_000, reserved_for_response=2_000).characters() == (
        8_000 * CHARS_PER_TOKEN
    )


def test_a_budget_that_reserves_everything_refuses():
    """Rather than returning zero or a negative character count, which `compose` would report
    as `MF0400` — a refusal naming the wrong cause."""
    with pytest.raises(ValueError, match="leaves nothing"):
        Budget(tokens=1_000, reserved_for_response=1_000).characters()
