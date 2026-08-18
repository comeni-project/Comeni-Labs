"""Replaying recorded decisions instead of re-asking.

Invariant 9: records are replayed on rerun rather than re-asking the model. That is how
determinism survives having a model available at all — and applied to a *downloaded*
pipeline it is the property that makes curation worth doing (federation §4.3):

    Load a curated Goal, change one thing, and every untouched decision replays from its
    record. Only what you touched can move.

This is one more `AmbiguityResolver`, not a new subsystem. That is the payoff for having
declared the port in Plan 1: the thing that makes editing a curated pipeline safe costs
one class and no changes to the resolver.
"""

from collections.abc import Sequence

from comeni_core.plan.decision import Ambiguity, DecisionRecord, Resolution
from comeni_core.plan.tiers import ValueSource
from comeni_core.spell.marks import DecisionKey

from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver


def _replayed_reason(record: DecisionRecord) -> str:
    """The reason a replayed decision carries.

    A person's own words where they wrote any; otherwise a sentence saying a person answered
    and gave none. Never the resolver's pre-answer text, which describes the moment before
    the decision was made. A77, A111.
    """
    if getattr(record, "human_override", None) is None:
        return record.reason
    return getattr(record, "override_reason", "") or (
        "answered by a human, who gave no reason"
    )


def _canonical_key(record: DecisionRecord) -> str:
    """A pre-1.13 producer key carried the winning module's node id in front. Audit A126.

    Normalised at **ingest** rather than matched at lookup, because the key is used in three
    places and matching only the lookup would leave the other two disagreeing: `_asked`
    collects the keys questions were asked under, and `orphaned()` is the complement of that
    against `_records`. A legacy record found by a lenient lookup would still be reported
    orphaned by the sweep — the exact bug A126 is, re-entering through the fix for it.

    An artifact written before 1.13 is still a valid file and must still replay. Rewriting
    the key here means every downstream comparison sees one spelling and nothing else has to
    know this migration happened.
    """
    if record.subject.startswith("producer:") and record.key.endswith(f".{record.subject}"):
        return record.subject
    return record.key


class ReplayResolver:
    """Answers from a prior run's records; asks the fallback for anything new."""

    def __init__(
        self,
        records: Sequence[DecisionRecord],
        fallback: AmbiguityResolver | None = None,
    ) -> None:
        # First wins. Two records for one key is a corrupt bundle rather than a choice,
        # and picking arbitrarily between them would be the coin flip invariant 8 forbids.
        self._records: dict[str, DecisionRecord] = {}
        for record in records:
            self._records.setdefault(_canonical_key(record), record)
        self._fallback = fallback or FlagOnlyResolver()
        self._asked: set[str] = set()
        self.replayed: list[DecisionKey] = []
        self.fresh: list[DecisionKey] = []
        self.stale: list[DecisionKey] = []
        """A record existed for this key and no longer fits, so it was re-asked.

        **Not `fresh`.** `fresh` means nobody had answered this before; a discarded record is
        a different event, and merging the two made the honest one unreadable. `upgrade`
        reported "1 newly asked" for a question somebody had already answered.
        """
        self.stale_overrides: list[DecisionKey] = []
        """The subset of `stale` where the discarded record carried a **human's** answer.

        Both are re-asked and both are right to be. Only one is worth interrupting somebody
        about: a resolver's recorded choice being reconsidered is ordinary, and a person's
        answer being thrown away is not.
        """

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        key = ambiguity.key()
        # Every question this run actually faced. `orphaned` is the complement, and reading
        # it off what was asked is what makes it impossible to disagree with what happened.
        self._asked.add(key)
        record = self._records.get(key)
        if record is not None and self._still_applies(record, ambiguity):
            self.replayed.append(key)
            return Resolution(
                value=_chosen(record),
                # **A person's reason where there is one, the record's otherwise.**
                #
                # Prefixing it with "replayed from a recorded decision" was the plan's
                # wording and was rejected on the grounds that `reason` is emitted into
                # `main.nf` as a comment, so a prefix would break federation §4.1's
                # byte-identity. **That justification expired.** No reason string has
                # reached `main.nf` or `nextflow.config` since Plan 1.10 — verified, and it
                # is audit A111. The conclusion survives its reasoning: the reason answers
                # "why is this value what it is", which replaying did not change, and that
                # this run replayed lives in `resolved_by` and in the count `upgrade` prints.
                #
                # What was wrong is narrower and worse. `record.reason` on an *overridden*
                # decision is the flag-only resolver's text — "selected the first of 1
                # candidates without judgement — please review" — which describes what
                # happened **before** the person arrived. So the artifact carried
                # `source: human` beside a sentence saying nobody had judged it, and asked a
                # reader to review something already reviewed. A77, A111.
                why=_replayed_reason(record),
                confidence=record.confidence,
                by="replay",
                # Who settled it, which `resolved_by` cannot say: the implementation
                # replaying a person's answer is still `replay`. Set only when the record
                # carries an override, so a replayed *resolver* choice stays a resolver
                # choice and keeps its review flag.
                how=(
                    ValueSource.HUMAN
                    if record.human_override is not None
                    else ValueSource.RESOLVER
                ),
            )
        if record is not None:
            # Re-asking is right, and `_still_applies` defends why. Doing it in silence is
            # not: the answer that was dropped is exactly the thing a person needs told.
            self.stale.append(key)
            if record.human_override is not None:
                self.stale_overrides.append(key)
        else:
            self.fresh.append(key)
        return self._fallback.resolve(ambiguity)

    @property
    def orphaned(self) -> list[DecisionKey]:
        """Human answers to questions this run never asked. Meaningful once resolution ends.

        `resolve()` is never called for a step that is gone, so no resolver hook can see one
        — it needs a sweep, and the sweep is the complement of what was asked. Two causes,
        both meaning *your edit no longer applies to anything*: the step is gone, or the value
        stopped being a question because a rule now covers it.

        Derived from `_asked` rather than by comparing two pipelines, which was the plan's
        sketch and is the weaker mechanism. A comparison enumerates the fields it knows
        about, so it can disagree with what resolution actually did — that is root D, and A28
        exactly: `mendel upgrade` said "re-resolves identically" while `main.nf` had moved.

        **Only an override can be orphaned.** A resolver's recorded choice for a step that no
        longer exists is nothing at all; nobody is owed a report that the machine's opinion
        about a deleted step went unused.
        """
        return sorted(
            key
            for key, record in self._records.items()
            if record.human_override is not None and key not in self._asked
        )

    @staticmethod
    def _still_applies(record: DecisionRecord, ambiguity: Ambiguity) -> bool:
        """Whether the world is close enough to when this was decided.

        Two ways it is not. The candidate set moved, so the record answers a question
        nobody is asking any more; or the choice itself is gone from the registry. Either
        way, replaying would assert a decision between options that no longer exist —
        worse than asking again, because it would look decided.

        **The membership half does not apply where there is no domain to be a member of.**
        A parameter's candidate list is literally `[None]` — a placeholder, because a `Param`
        has no declared legal values until Plan 2 Task 11 — so *every* human override on a
        parameter failed this check and was discarded in silence. Measured, not theorised:
        a record with `human_override="illumina"` came back `chosen=None`, `resolved_by=
        "flag-only"`, counted as newly asked. The whole override mechanism was dead for the
        one kind of decision that has no other way to be answered.

        `resolve.py`'s tier-4 site already documents this asymmetry from the other side and
        for the same reason. Keyed on the placeholder rather than on the kind, so the check
        turns itself back on the day a parameter gets a real domain.
        """
        if list(record.candidates) != list(ambiguity.candidates):
            return False
        if list(ambiguity.candidates) == [None]:
            return True
        return _chosen(record) in ambiguity.candidates


def _chosen(record: DecisionRecord) -> object:
    """What this record actually decided: a human's override if there is one.

    Checked in one place because it is asked twice — once to validate the record still
    applies and once to answer with it — and the two answering differently is how an
    override could be validated and then not used.
    """
    return record.human_override if record.human_override is not None else record.chosen
