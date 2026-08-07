"""A resolved decision must select, not merely get recorded. Audit 2026-08-06, A8.

`router._choose` picked `ordered[0]` by id order, appended an `Ambiguity` to the plan, and
returned. The resolver was consulted afterwards, at the bottom of `resolve()`, purely to
fill in a `DecisionRecord` — `ir.nodes` and `ir.edges` were already built. `_source_for`
was worse: it called the resolver and then wrote `chosen=f"{chosen[0]}.{chosen[1]}"`,
overwriting the answer in the very statement that recorded it.

So `ReplayResolver` could replay a parameter and never a module choice, a `human_override`
on a producer was accepted and ignored, and — the serious one — a `DecisionRecord` could
state a choice the pipeline did not make. A published bundle is supposed to be the
auditable object; a reader had no way to notice it was wrong.

Nothing was wrong in *output*: `FlagOnlyResolver` returns the candidate the code already
picked, which is exactly why this survived. The tests here therefore use a resolver that
disagrees, because agreement is what hid it.
"""

import pytest
from comeni_core.decision import Ambiguity, DecisionRecord, Resolution
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.replay import ReplayResolver
from mendel_resolver.resolve import resolve
from mendel_resolver.rules import RuleTable

ALIGNER = """
id: audit/aligner-{tag}@1.0.0
nf_process: ALIGNER_{upper}
nf_include: modules/audit/aligner-{tag}/main
consumes: [{{name: reads, type_id: fastq.reads, state_required: []}}]
produces: [{{name: bam, type_id: alignment.bam, state: []}}]
priority: 0
provenance: {{source: audit, drafted_by: audit, approved_by: audit, approved_at: "2026-08-06"}}
"""


class _PicksLast:
    """Chooses the *last* candidate — disagrees with `router._choose`, which took `ordered[0]`.

    `FlagOnlyResolver` picks the first, which is what the router picked anyway. The two
    agreeing is precisely what hid A8, so every test here needs a resolver that does not.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        return Resolution(
            chosen=ambiguity.candidates[-1],
            reason="audit fixture: deliberately not the first candidate",
            confidence=1.0,
            resolved_by="audit",
        )


class _PicksFirst:
    """Chooses the *first* candidate — disagrees with `_source_for`, which took the last.

    The two sites defaulted in opposite directions: `_choose` kept `ordered[0]` and
    `_source_for` kept `equally_good[-1]`. So one fixture cannot disagree with both, and
    using `_PicksLast` on a source ambiguity silently agrees with the bug — which is how
    the first version of these tests passed against unfixed code.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        return Resolution(
            chosen=ambiguity.candidates[0],
            reason="audit fixture: deliberately not the last candidate",
            confidence=1.0,
            resolved_by="audit",
        )


@pytest.fixture
def tied(tmp_path):
    """Two aligners nothing distinguishes: a genuine tie, so tier 4 and a record."""
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "fastq.reads.yml").write_text("states: []\n")
    (vocab_dir / "alignment.bam.yml").write_text("states: []\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "a.yml").write_text(ALIGNER.format(tag="a", upper="A"))
    (contracts / "b.yml").write_text(ALIGNER.format(tag="b", upper="B"))
    vocabulary = Vocabulary.load(tmp_path)
    return Registry.load(contracts, vocabulary), RuleTable(), MeasurementRegistry()


def _goal():
    return Goal(have=[GoalInput(type_id="fastq.reads")], want=["alignment.bam"])


def test_a_resolver_that_disagrees_changes_which_module_is_selected(tied):
    """The capability itself. Plan 2 plugs a model into this port."""
    registry, rules, measurements = tied
    ir = resolve(_goal(), registry, rules, measurements, resolver=_PicksLast())

    assert [n.contract_id for n in ir.nodes] == ["audit/aligner-b@1.0.0"], (
        "the resolver chose aligner-b; the pipeline must contain aligner-b"
    )


def test_every_producer_record_names_the_contract_that_was_selected(tied):
    """The invariant, stated as a property rather than a scenario.

    Nothing forced `record.chosen` to equal the contract in `IRNode.selection`, so a
    published bundle could be internally inconsistent with no way for a reader to tell.
    """
    registry, rules, measurements = tied
    ir = resolve(_goal(), registry, rules, measurements, resolver=_PicksLast())

    selected = {node.selection.value for node in ir.nodes}
    producer_records = [d for d in ir.decisions if d.subject.startswith("producer:")]
    assert producer_records, "a tie must still emit a record"
    for record in producer_records:
        assert record.chosen in selected, (
            f"record says {record.chosen!r}, pipeline selected {sorted(selected)}"
        )


def test_a_tie_is_still_tier_4_and_still_flagged(tied):
    """Invariant 6: resolving a tier-4 choice does not clear it. A8 must not weaken this."""
    from comeni_core.ir import ReviewLevel, Tier

    registry, rules, measurements = tied
    ir = resolve(_goal(), registry, rules, measurements, resolver=_PicksLast())

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
    registry, rules, measurements = tied
    first = resolve(_goal(), registry, rules, measurements)
    record = next(d for d in first.decisions if d.subject.startswith("producer:"))
    assert record.chosen == "audit/aligner-a@1.0.0", "baseline picks the first by id order"

    corrected = record.model_copy(update={"human_override": "audit/aligner-b@1.0.0"})
    ir = resolve(
        _goal(), registry, rules, measurements, resolver=ReplayResolver([corrected])
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
                chosen="audit/aligner-nonexistent@9.9.9",
                reason="forged",
                confidence=1.0,
                resolved_by="audit",
            )

    registry, rules, measurements = tied
    ir = resolve(_goal(), registry, rules, measurements, resolver=_Forges())

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
                chosen=ambiguity.candidates[-1],
                reason="counting",
                confidence=1.0,
                resolved_by="audit",
            )

    registry, rules, measurements = tied
    counter = _Counts()
    resolve(_goal(), registry, rules, measurements, resolver=counter)
    assert len(counter.seen) == len(set(counter.seen)), counter.seen


DUAL = """
id: audit/dual@1.0.0
nf_process: DUAL
nf_include: modules/audit/dual/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces:
  - {name: bam, type_id: alignment.bam, state: []}
  - {name: bam_transcriptome, type_id: alignment.bam, state: []}
priority: 0
provenance: {source: audit, drafted_by: audit, approved_by: audit, approved_at: "2026-08-06"}
"""
COUNTER = """
id: audit/counter@1.0.0
nf_process: COUNTER
nf_include: modules/audit/counter/main
consumes: [{name: bam, type_id: alignment.bam, state_required: []}]
produces: [{name: counts, type_id: counts.matrix, state: []}]
priority: 0
provenance: {source: audit, drafted_by: audit, approved_by: audit, approved_at: "2026-08-06"}
"""


@pytest.fixture
def two_equally_good_sources(tmp_path):
    """One producer, two ports of the same type — the shape that makes `_source_for` choose.

    Two *contracts* would not do it: only one of them gets routed, so `produced` holds one
    candidate and the ambiguity never arises. That is why the first version of this test
    passed against the bug — it asserted over an empty loop. Real: STAR emits a genomic
    and a transcriptomic BAM, and which one a counter should read is a genuine question.
    """
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    for type_id in ("fastq.reads", "alignment.bam", "counts.matrix"):
        (vocab_dir / f"{type_id}.yml").write_text("states: []\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "dual.yml").write_text(DUAL)
    (contracts / "counter.yml").write_text(COUNTER)
    vocabulary = Vocabulary.load(tmp_path)
    return Registry.load(contracts, vocabulary)


def test_an_edge_record_names_the_edge_that_was_built(two_equally_good_sources):
    """Guards the fix rather than the bug — and that distinction is worth writing down.

    Pre-A8, `_source_for` recorded `f"{chosen[0]}.{chosen[1]}"` from the source it had
    already picked, so its record and its edge always agreed; the defect was that the
    resolver's answer was discarded, which is what
    `test_a_resolver_picks_which_port_feeds_a_consumer` catches. Verified: reverting
    `_source_for` fails that test and not this one.

    This exists because the fix introduces the *possibility* of disagreement — the record
    is now written after a `next(...)` that can fall back — and recording
    `resolution.chosen` instead of `chosen` would reopen on the edge side exactly what A8
    was on the producer side. It is a guard against the next version of this file.
    """
    goal = Goal(have=[GoalInput(type_id="fastq.reads")], want=["counts.matrix"])
    ir = resolve(
        goal,
        two_equally_good_sources,
        RuleTable(),
        MeasurementRegistry(),
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
    ir = resolve(
        goal,
        two_equally_good_sources,
        RuleTable(),
        MeasurementRegistry(),
        resolver=_PicksFirst(),
    )

    into_counter = [e for e in ir.edges if e.to_node == "counter"]
    # Candidates sort to ["dual.bam", "dual.bam_transcriptome"], so `_PicksFirst` answers
    # `dual.bam` — while the unfixed code kept `equally_good[-1]`, the transcriptomic one.
    # The two differ, which is the only reason this test can fail.
    assert [e.from_port for e in into_counter] == ["bam"]


def test_a_replayed_record_is_not_needed_for_this_to_hold(tied):
    """The default path must stay exactly as it was: first candidate, flagged, recorded."""
    registry, rules, measurements = tied
    ir = resolve(_goal(), registry, rules, measurements)

    assert [n.contract_id for n in ir.nodes] == ["audit/aligner-a@1.0.0"]
    record = next(d for d in ir.decisions if d.subject.startswith("producer:"))
    assert record.resolved_by == "flag-only"
    assert isinstance(record, DecisionRecord)
