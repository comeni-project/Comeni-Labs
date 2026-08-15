"""Replaying recorded decisions instead of re-asking.

Federation §4.3: load a curated Goal, change one thing, and every untouched decision
replays from its record — only what you touched can move. Invariant 9 already says records
are replayed rather than re-asked; this is the class that does it.
"""

import pytest
from comeni_core.plan.decision import ParamAsked, ParamDecision
from mendel_resolver.replay import ReplayResolver


def _ambiguity(subject="aligner", node="star_align"):
    return ParamAsked(node_id=node, subject=subject, candidates=["a", "b"])


def _record(ambiguity, chosen="b", **kwargs):
    return ParamDecision(
        key=ambiguity.key(),
        subject=ambiguity.subject,
        candidates=ambiguity.candidates,
        chosen=chosen,
        reason="recorded earlier",
        confidence=0.0,
        resolved_by="flag-only",
        **kwargs,
    )


def test_a_recorded_decision_replays_rather_than_being_re_asked():
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity)])
    resolution = resolver.resolve(ambiguity)
    assert resolution.chosen == "b"
    assert resolver.replayed == [ambiguity.key()]


def test_a_human_override_wins_over_the_original_choice():
    """The whole point of `human_override`: a person disagreed, and that must stick."""
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, chosen="b", human_override="a")])
    assert resolver.resolve(ambiguity).chosen == "a"


def test_a_replayed_resolution_says_it_was_replayed():
    ambiguity = _ambiguity()
    resolution = ReplayResolver([_record(ambiguity)]).resolve(ambiguity)
    assert resolution.resolved_by == "replay"


def test_a_replayed_reason_is_the_recorded_one_verbatim():
    """`reason` is emitted into `main.nf` as the comment above the parameter, so anything
    added to it here makes an upgraded pipeline differ from the published one — and
    federation §4.1 says loading a locked pipeline reproduces byte-identical Nextflow.

    The plan asked for a "replayed from a recorded decision:" prefix and also for
    byte-identical emission. Those cannot both hold. The reason explains why the value is
    what it is, which replaying did not change; that this run replayed lives in
    `resolved_by`. `tests/test_upgrade.py` is the other half of this pair.
    """
    ambiguity = _ambiguity()
    resolution = ReplayResolver([_record(ambiguity)]).resolve(ambiguity)
    assert resolution.reason == "recorded earlier"


def test_an_unrecorded_decision_falls_through_to_the_fallback():
    resolver = ReplayResolver([])
    resolution = resolver.resolve(_ambiguity())
    assert resolution.resolved_by == "flag-only"
    assert resolver.fresh == [_ambiguity().key()]


def test_a_record_whose_candidates_changed_is_not_replayed():
    """The registry moved underneath the record. Replaying would assert a choice between
    options that no longer exist, which is worse than asking again.

    The claim is unchanged; the list it lands in is. This asserted `in resolver.fresh` until
    Plan 1.10 Task 9 split the two, and that assertion was the merge — it said a question
    somebody had already answered was one nobody had.
    """
    ambiguity = _ambiguity()
    stale = _record(ambiguity)
    resolver = ReplayResolver([stale])
    widened = ParamAsked(
        node_id="star_align", subject="aligner", candidates=["a", "b", "c"]
    )
    assert resolver.resolve(widened).resolved_by == "flag-only"
    assert widened.key() in resolver.stale
    assert widened.key() not in resolver.fresh


def test_a_record_whose_choice_is_no_longer_a_candidate_is_not_replayed():
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, chosen="gone")])
    assert resolver.resolve(ambiguity).resolved_by == "flag-only"


def test_a_human_override_that_is_no_longer_a_candidate_is_not_replayed():
    """An override is still a choice between options, and the options moved. Replaying a
    person's answer to a question that no longer exists is not honouring it."""
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, chosen="a", human_override="gone")])
    assert resolver.resolve(ambiguity).resolved_by == "flag-only"


def test_replay_is_deterministic_over_duplicate_keys():
    """Two records for one key is a corrupt bundle. First wins, and it is documented."""
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, chosen="a"), _record(ambiguity, chosen="b")])
    assert resolver.resolve(ambiguity).chosen == "a"


def test_no_candidates_still_raises():
    from mendel_resolver.ports import NoCandidatesError

    empty = ParamAsked(node_id="n", subject="s", candidates=[])
    with pytest.raises(NoCandidatesError):
        ReplayResolver([]).resolve(empty)


def test_replay_drops_into_resolve_in_place_of_the_default():
    """Substitutability, proved by substituting rather than by a type check.

    `AmbiguityResolver` is not `@runtime_checkable`, and making it so purely to let a test
    call `isinstance` would be changing the port to suit the test. Running a real build
    through it is the stronger claim anyway: the payoff Plan 1 bought by declaring the
    protocol is that this costs one class and no resolver changes.
    """
    import pathlib

    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    root = pathlib.Path(__file__).parents[3]
    loaded = layers.load(root / "registry")
    goal = Goal(
        have=[GoalInput(type_id=t) for t in ("fastq.reads", "annotation.gtf", "genome.fasta")],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )

    replayer = ReplayResolver([])
    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=replayer,
    )
    assert ir.nodes, "a ReplayResolver with no records must still build"

    # Everything it could not replay is recorded as fresh, and the pipeline that came out
    # is the same one FlagOnlyResolver produces — replay changes provenance, not routing.
    baseline = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )
    assert [n.contract_id for n in ir.nodes] == [n.contract_id for n in baseline.nodes]
    assert replayer.replayed == []


def test_replaying_a_previous_run_reproduces_its_choices():
    """The federation §4.3 property, end to end: feed a build its own decision records
    and every one of them replays instead of being decided again."""
    import pathlib

    from mendel_resolver import layers
    from mendel_resolver.goal import Goal, GoalInput
    from mendel_resolver.resolve import resolve

    root = pathlib.Path(__file__).parents[3]
    loaded = layers.load(root / "registry")
    goal = Goal(
        have=[GoalInput(type_id=t) for t in ("fastq.reads", "annotation.gtf", "genome.fasta")],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
        profile=loaded.measurements.profile({"read_length": 150, "strandedness": "reverse"}),
    )
    first = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
    )
    assert first.decisions, "the spine must make at least one flagged decision to replay"

    replayer = ReplayResolver(first.decisions)
    second = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=replayer,
    )

    assert sorted(replayer.replayed) == sorted(d.key for d in first.decisions)
    assert replayer.fresh == []
    assert second.model_dump_json() != "" and [n.contract_id for n in second.nodes] == [
        n.contract_id for n in first.nodes
    ]


# --- Plan 1.10 Task 9: stale is not orphaned, and neither may be silent ----------------
#
# `_still_applies` returning False is a *deliberate* re-ask, and it stays — replaying would
# assert a decision between options that no longer exist, which is worse than asking again
# because it would look decided. What was wrong is that it vanished into a `fresh` count
# with no statement that somebody's answer had been discarded.


def test_a_stale_record_is_reported_as_stale_rather_than_as_fresh():
    """`fresh` means "nobody had answered this". A record that existed and no longer applies
    is a different event, and merging the two makes the honest one unreadable."""
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity)])
    widened = ParamAsked(node_id="star_align", subject="aligner", candidates=["a", "b", "c"])

    assert resolver.resolve(widened).resolved_by == "flag-only"
    assert resolver.stale == [widened.key()]
    assert resolver.replayed == []
    assert resolver.fresh == [], "it was not fresh — there was a record, and it was dropped"


def test_a_stale_human_override_is_called_out_separately():
    """Discarding a resolver's recorded choice is ordinary; discarding a person's answer is
    not. Both are re-asked, and only one is worth interrupting somebody about."""
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, chosen="a", human_override="a")])
    widened = ParamAsked(node_id="star_align", subject="aligner", candidates=["c", "d"])

    resolver.resolve(widened)
    assert resolver.stale == [widened.key()]
    assert resolver.stale_overrides == [widened.key()]


def test_a_stale_record_with_no_override_is_stale_but_not_an_override():
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity)])
    resolver.resolve(ParamAsked(node_id="star_align", subject="aligner", candidates=["c"]))
    assert resolver.stale and resolver.stale_overrides == []


def test_an_override_for_a_question_never_asked_is_orphaned():
    """`resolve()` is never called for a step that is gone, so no resolver hook can see it.

    Derived from what this resolver was *asked*, rather than by diffing two pipelines. The
    diff was the plan's sketch and it is the weaker mechanism: a comparison enumerates the
    fields it knows about, so it can disagree with what resolution actually did — which is
    root D, and audit A28 in particular.
    """
    ambiguity = _ambiguity()
    gone = ParamAsked(node_id="hisat2_align", subject="seq_platform", candidates=["a", "b"])
    resolver = ReplayResolver([
        _record(ambiguity, human_override="a"),
        _record(gone, human_override="illumina"),
    ])
    resolver.resolve(ambiguity)

    assert resolver.orphaned == ["hisat2_align.seq_platform"]


def test_a_replayed_override_is_not_orphaned():
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, human_override="a")])
    resolver.resolve(ambiguity)
    assert resolver.orphaned == []


def test_a_stale_override_is_not_also_orphaned():
    """The two categories must not double-count: it *was* asked, and the answer no longer
    fits. Reporting it twice under two headings is how a reviewer learns to skim both."""
    ambiguity = _ambiguity()
    resolver = ReplayResolver([_record(ambiguity, chosen="a", human_override="a")])
    resolver.resolve(ParamAsked(node_id="star_align", subject="aligner", candidates=["c"]))
    assert resolver.stale_overrides and resolver.orphaned == []


def test_a_recorded_choice_with_no_override_is_never_orphaned():
    """Only a *human's* answer can be orphaned. A resolver's recorded choice for a step that
    no longer exists is nothing at all — nobody is owed a report that the machine's opinion
    about a deleted step went unused."""
    resolver = ReplayResolver([_record(_ambiguity(node="hisat2_align"))])
    assert resolver.orphaned == []


def test_replay_still_emits_the_recorded_reason_verbatim():
    """The constraint every change to this file has to survive: `reason` reaches the artifact,
    and federation §4.1 requires an upgraded pipeline to reproduce byte-identical Nextflow."""
    ambiguity = _ambiguity()
    resolution = ReplayResolver([_record(ambiguity)]).resolve(ambiguity)
    assert resolution.reason == "recorded earlier"
