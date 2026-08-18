"""A tier-4 producer question says what it is about, and cites its candidates.

Before Plan 2.5 a reviewer facing a routing tie got a list of contract ids and nothing to
judge them on — no statement of what was being decided, no reason it was open, no evidence.
The forge carried all three on every `Hole` from its first day. That asymmetry is the spec's
§7.1, and closing it is the point of making `Ambiguity` a `Question`.

The `tied` fixture is imported rather than rebuilt: two aligners nothing distinguishes is
exactly the shape this is about, and a second copy of it would drift.
"""

from comeni_core.plan.decision import ProducerAsked
from comeni_core.plan.tiers import Tier
from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver
from mendel_resolver.resolve import resolve
from test_resolution_applies import _goal, tied  # noqa: F401  (pytest fixture)


class _Captures(FlagOnlyResolver):
    """Answers exactly as the shipped resolver does, and keeps what it was asked.

    Subclassing rather than reimplementing: the question under test is what the *router*
    puts into an ambiguity, so the answer must stay the shipped one or the pipeline that
    gets built is not the one this is reasoning about.
    """

    def __init__(self) -> None:
        self.asked: list[ProducerAsked] = []

    def resolve(self, ambiguity):
        if isinstance(ambiguity, ProducerAsked):
            self.asked.append(ambiguity)
        return super().resolve(ambiguity)


def _producer_question(tied) -> ProducerAsked:  # noqa: F811
    registry, rules, measurements, vocabulary = tied
    captured = _Captures()
    ir = resolve(
        _goal(), registry, rules, measurements, vocabulary=vocabulary, resolver=captured
    )
    assert ir.nodes, "the fixture must build something for there to be a question about"
    assert captured.asked, "two tied aligners must produce a producer question"
    return captured.asked[0]


def test_a_producer_question_says_what_it_is_about(tied):  # noqa: F811
    """`what` and `why_open` were empty on every build-path question until Plan 2.5.

    A model behind door 2 given a bare candidate list is the configuration the forge
    measured at 69%.
    """
    asked = _producer_question(tied)

    assert "alignment.bam" in asked.what
    assert asked.why_open, "a tier-4 question with no stated reason is the 69% prompt"
    assert "8" in asked.why_open or "coin flip" in asked.why_open, (
        "the reason should name invariant 8 — a tie is ambiguity, not a coin flip"
    )


def test_a_producer_question_cites_every_candidate(tied):  # noqa: F811
    """One excerpt per candidate, each readable on its own.

    `text` carries the registry's *own* reason for ranking a contract where it does, which
    is what `priority_because` is for and what audit A128 is about when it is empty.
    """
    asked = _producer_question(tied)

    assert len(asked.evidence) == len(asked.candidates)
    for excerpt in asked.evidence:
        assert excerpt.locator, "an excerpt with no locator is a claim, not a citation"
        assert excerpt.text, "an excerpt with no text is a citation a reviewer cannot read"
    cited = " ".join(e.locator for e in asked.evidence)
    for candidate in asked.candidates:
        assert candidate in cited, f"{candidate} is offered but not cited"


def test_the_candidates_still_bind(tied):  # noqa: F811
    """`closed` is inherited from `Question` and a routing tie is a closed choice — the
    answer must be one of the tied contracts. The forge measured that opening a closed
    field was the worst configuration tested."""
    asked = _producer_question(tied)

    assert asked.closed is True
    assert not asked.legal("audit/aligner-that-does-not-exist@9.9.9")


def test_the_tie_is_still_tier_four(tied):  # noqa: F811
    """Evidence is for the reviewer, not a way of settling the question. Invariant 6."""
    registry, rules, measurements, vocabulary = tied
    ir = resolve(
        _goal(), registry, rules, measurements, vocabulary=vocabulary,
        resolver=FlagOnlyResolver(),
    )

    node = next(n for n in ir.nodes if n.contract_id.startswith("audit/aligner"))
    assert node.selection.tier is Tier.AMBIGUOUS


def test_the_resolver_port_is_unchanged(tied):  # noqa: F811
    """`_Captures` is an `AmbiguityResolver`, checked by call rather than by isinstance —
    the port is a plain Protocol, so isinstance would only see the method name."""
    resolver: AmbiguityResolver = _Captures()
    assert resolver.resolve is not None
