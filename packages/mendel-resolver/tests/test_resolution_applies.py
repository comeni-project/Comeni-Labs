"""Resolved producer and source decisions alter the plan and agree with their records."""

from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.plan.decision import Ambiguity, ProducerDecision, Resolution
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.replay import ReplayResolver
from mendel_resolver.resolve import resolve
from mendel_resolver.rules import RuleTable
from mendel_resolver_tests import (
    _goal,
    _PicksFirst,
    _PicksLast,
)
from mendel_resolver_tests import tied as tied
from mendel_resolver_tests import two_equally_good_sources as two_equally_good_sources


def test_a_resolver_that_disagrees_changes_which_module_is_selected(tied):
    """The capability itself. Plan 2 plugs a model into this port."""
    registry, rules, measurements, vocabulary = tied
    ir = resolve(
        _goal(), registry, rules, measurements, vocabulary=vocabulary, resolver=_PicksLast()
    )

    assert [n.contract_id for n in ir.nodes] == ["audit/aligner-b@1.0.0"], (
        "the resolver chose aligner-b; the pipeline must contain aligner-b"
    )


def test_every_producer_record_names_the_contract_that_was_selected(tied):
    """The invariant, stated as a property rather than a scenario.

    Nothing forced `record.chosen` to equal the contract in `IRNode.selection`, so a
    published bundle could be internally inconsistent with no way for a reader to tell.
    """
    registry, rules, measurements, vocabulary = tied
    ir = resolve(
        _goal(), registry, rules, measurements, vocabulary=vocabulary, resolver=_PicksLast()
    )

    selected = {node.selection.value for node in ir.nodes}
    producer_records = [d for d in ir.decisions if d.subject.startswith("producer:")]
    assert producer_records, "a tie must still emit a record"
    for record in producer_records:
        assert record.chosen in selected, (
            f"record says {record.chosen!r}, pipeline selected {sorted(selected)}"
        )


def test_a_tie_is_still_tier_4_and_still_flagged(tied):
    """Invariant 6: resolving a tier-4 choice does not clear it. A8 must not weaken this."""
    from comeni_core.plan.ir import ReviewLevel, Tier

    registry, rules, measurements, vocabulary = tied
    ir = resolve(
        _goal(), registry, rules, measurements, vocabulary=vocabulary, resolver=_PicksLast()
    )

    node = ir.nodes[0]
    assert node.selection.tier is Tier.AMBIGUOUS
    assert node.selection.review_level is ReviewLevel.REQUIRED
    assert any(item.endswith("(module)") for item in ir.needs_review())


def test_a_human_override_on_a_producer_reaches_the_pipeline(tied):
    """Federation §4.3's curation property, for a module choice rather than a parameter.

    "Change one thing and every untouched decision replays; only what you touched can
    move" was true for parameters and false here: the override was accepted, recorded,
    and discarded.
    """
    registry, rules, measurements, vocabulary = tied
    first = resolve(_goal(), registry, rules, measurements, vocabulary=vocabulary)
    record = next(d for d in first.decisions if d.subject.startswith("producer:"))
    assert record.chosen == "audit/aligner-a@1.0.0", "baseline picks the first by id order"

    corrected = record.model_copy(update={"human_override": "audit/aligner-b@1.0.0"})
    ir = resolve(
        _goal(),
        registry,
        rules,
        measurements,
        vocabulary=vocabulary,
        resolver=ReplayResolver([corrected]),
    )

    assert [n.contract_id for n in ir.nodes] == ["audit/aligner-b@1.0.0"]
    replayed = next(d for d in ir.decisions if d.subject.startswith("producer:"))
    assert replayed.chosen == "audit/aligner-b@1.0.0"
    assert replayed.resolved_by == "replay"


def test_a_resolver_naming_a_non_candidate_falls_back_rather_than_trusting(tied):
    """A forged answer must not reach the pipeline.

    `ReplayResolver._still_applies` already rejects a record whose candidate set moved —
    verified clean in the audit — and `_choose` keeps the same posture for a resolver that
    answers with something that is not on the list.
    """

    class _Forges:
        def resolve(self, ambiguity: Ambiguity) -> Resolution:
            return Resolution(
                value="audit/aligner-nonexistent@9.9.9",
                why="forged",
                confidence=1.0,
                by="audit",
            )

    registry, rules, measurements, vocabulary = tied
    ir = resolve(_goal(), registry, rules, measurements, vocabulary=vocabulary, resolver=_Forges())

    assert [n.contract_id for n in ir.nodes] == ["audit/aligner-a@1.0.0"]
    record = next(d for d in ir.decisions if d.subject.startswith("producer:"))
    assert record.chosen == "audit/aligner-a@1.0.0", "the record must name what was built"


def test_the_resolver_is_asked_once_per_ambiguity(tied):
    """A second call is a second chance to disagree — and, with a model, a second charge."""

    class _Counts:
        def __init__(self) -> None:
            self.seen: list[str] = []

        def resolve(self, ambiguity: Ambiguity) -> Resolution:
            self.seen.append(ambiguity.key())
            return Resolution(
                value=ambiguity.candidates[-1],
                why="counting",
                confidence=1.0,
                by="audit",
            )

    registry, rules, measurements, vocabulary = tied
    counter = _Counts()
    resolve(_goal(), registry, rules, measurements, vocabulary=vocabulary, resolver=counter)
    assert len(counter.seen) == len(set(counter.seen)), counter.seen


def test_an_edge_record_names_the_edge_that_was_built(two_equally_good_sources):
    """Guards the fix rather than the bug — and that distinction is worth writing down.

    Pre-A8, `_source_for` recorded `f"{chosen[0]}.{chosen[1]}"` from the source it had
    already picked, so its record and its edge always agreed; the defect was that the
    resolver's answer was discarded, which is what
    `test_a_resolver_picks_which_port_feeds_a_consumer` catches. Verified: reverting
    `_source_for` fails that test and not this one.

    This exists because the fix introduces the *possibility* of disagreement — the record
    is now written after a `next(...)` that can fall back — and recording
    `resolution.value` instead of `chosen` would reopen on the edge side exactly what A8
    was on the producer side. It is a guard against the next version of this file.
    """
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["counts.matrix"])
    registry, vocabulary = two_equally_good_sources
    ir = resolve(
        goal,
        registry,
        RuleTable(),
        MeasurementRegistry(),
        vocabulary=vocabulary,
        resolver=_PicksFirst(),
    )

    records = [d for d in ir.decisions if d.subject.startswith("source:")]
    assert records, "two equally good sources must emit a source decision"
    built = {f"{e.from_node}.{e.from_port}" for e in ir.edges}
    for record in records:
        assert record.chosen in built, (
            f"record says the edge came from {record.chosen!r}; built {sorted(built)}"
        )


def test_a_resolver_picks_which_port_feeds_a_consumer(two_equally_good_sources):
    """And the choice reaches the graph, not only the record."""
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["counts.matrix"])
    registry, vocabulary = two_equally_good_sources
    ir = resolve(
        goal,
        registry,
        RuleTable(),
        MeasurementRegistry(),
        vocabulary=vocabulary,
        resolver=_PicksFirst(),
    )

    into_counter = [e for e in ir.edges if e.to_node == "counter"]
    # Candidates sort to ["dual.bam", "dual.bam_transcriptome"], so `_PicksFirst` answers
    # `dual.bam` — while the unfixed code kept `equally_good[-1]`, the transcriptomic one.
    # The two differ, which is the only reason this test can fail.
    assert [e.from_port for e in into_counter] == ["bam"]


def test_a_replayed_record_is_not_needed_for_this_to_hold(tied):
    """The default path must stay exactly as it was: first candidate, flagged, recorded."""
    registry, rules, measurements, vocabulary = tied
    ir = resolve(_goal(), registry, rules, measurements, vocabulary=vocabulary)

    assert [n.contract_id for n in ir.nodes] == ["audit/aligner-a@1.0.0"]
    record = next(d for d in ir.decisions if d.subject.startswith("producer:"))
    assert record.resolved_by == "flag-only"
    assert isinstance(record, ProducerDecision)
