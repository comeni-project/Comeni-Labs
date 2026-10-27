"""Amendments, the blueprint diff and alternatives (§14.3 of the consultant build): a change is
applied to the goal, and an alternative is shown as the whole pipeline it gives."""

from comeni_core.goal.asked import Goal, ProducerPin, Site
from comeni_core.goal.profile import DataProfile
from mendel_authoring.alternatives import alternatives_of
from mendel_authoring.amend import ChooseTool, SetFact
from mendel_authoring.diff import diff_of

ALIGNMENT = Site(type_id="alignment.bam")


class Unroutable(ValueError):
    """Stands in for the resolver's `UnroutableError`: the pure package does not import it."""


STAR_BP = {
    "fastqc": "nf-core/fastqc@0.12.1",
    "star_genomegenerate": "nf-core/star/genomegenerate@2.7.11b",
    "star_align": "nf-core/star/align@2.7.11b",
    "featurecounts": "nf-core/subread/featurecounts@2.1.1",
}
HISAT2_BP = {
    "fastqc": "nf-core/fastqc@0.12.1",
    "hisat2_build": "nf-core/hisat2/build@2.2.2",
    "hisat2_align": "nf-core/hisat2/align@2.2.2",
    "featurecounts": "nf-core/subread/featurecounts@2.1.1",
}


def test_alternative_retains_the_same_resolved_blueprint(blueprint_of):
    before = blueprint_of(STAR_BP, {"star_align": ALIGNMENT})
    after = blueprint_of(HISAT2_BP)
    calls = []

    def resolve(goal):
        calls.append(goal)
        return after

    options = alternatives_of(before, Goal(), "star_align",
                              [HISAT2_BP["hisat2_align"]], resolve, (Unroutable,))
    assert len(options) == 1 and len(calls) == 1
    assert getattr(options[0], "blueprint", None) == after
    assert options[0].diff.added == ["hisat2_build", "hisat2_align"]


def test_a_swap_names_what_it_adds_and_removes(blueprint_of):
    d = diff_of(blueprint_of(STAR_BP), blueprint_of(HISAT2_BP))
    assert d.added == ["hisat2_build", "hisat2_align"]
    assert d.removed == ["star_genomegenerate", "star_align"]
    assert d.sentence() == (
        "adds hisat2_build, hisat2_align; removes star_genomegenerate, star_align"
    )


def test_the_same_step_with_another_tool_is_a_change_not_an_add(blueprint_of):
    other = dict(STAR_BP, featurecounts="nf-core/htseq/count@2.0.5")
    d = diff_of(blueprint_of(STAR_BP), blueprint_of(other))
    assert d.swapped == [("featurecounts", "nf-core/htseq/count@2.0.5")]
    assert not d.added and not d.removed and not d.empty


def test_choose_tool_replaces_the_pin_at_its_site():
    goal = ChooseTool(pin=ProducerPin(site=ALIGNMENT, contract="lab/a@1")).apply(Goal())
    goal = ChooseTool(pin=ProducerPin(site=ALIGNMENT, contract="lab/b@1")).apply(goal)
    assert [p.contract for p in goal.constraints.producers] == ["lab/b@1"]


def test_set_fact_swaps_in_the_profile_it_carries():
    """The shell builds the profile through the measurement registry (invariant 15)."""
    profile = DataProfile()
    fact = SetFact(measurement="read_length", value=150, profile=profile)
    assert fact.apply(Goal()).profile is profile


def test_an_alternative_that_cannot_be_built_is_shown_with_its_reason(blueprint_of):
    def resolve(goal):
        if goal.constraints.producers[-1].contract == "lab/bad@1":
            raise Unroutable("lab/bad@1 needs genome.gtf, which nothing makes")
        return blueprint_of(HISAT2_BP)

    alts = alternatives_of(
        blueprint_of(STAR_BP, {"star_align": ALIGNMENT}), Goal(), "star_align",
        ["nf-core/star/align@2.7.11b", "lab/good@1", "lab/bad@1"], resolve, (Unroutable,),
    )
    assert [(a.id, a.contract, a.refused is None) for a in alts] == [
        ("alt_1", "lab/good@1", True),
        ("alt_2", "lab/bad@1", False),
    ]
    assert "adds hisat2_build" in alts[0].diff.sentence()
    assert "genome.gtf" in alts[1].refused
    assert alts[0].amendment.pin == ProducerPin(site=ALIGNMENT, contract="lab/good@1")


def test_an_alternative_that_changes_nothing_is_dropped(blueprint_of):
    same = blueprint_of(STAR_BP, {"star_align": ALIGNMENT})
    assert alternatives_of(same, Goal(), "star_align", ["lab/inert@1"], lambda g: same,
                           (Unroutable,)) == []


def test_a_step_with_no_site_has_no_alternatives(blueprint_of):
    assert alternatives_of(blueprint_of(STAR_BP), Goal(), "star_align", ["lab/a@1"],
                           lambda g: blueprint_of(HISAT2_BP), (Unroutable,)) == []
