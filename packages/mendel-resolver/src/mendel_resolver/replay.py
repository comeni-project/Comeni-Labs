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

from comeni_core.decision import Ambiguity, DecisionRecord, Resolution
from comeni_core.marks import DecisionKey

from mendel_resolver.ports import AmbiguityResolver, FlagOnlyResolver


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
            self._records.setdefault(record.key, record)
        self._fallback = fallback or FlagOnlyResolver()
        self.replayed: list[DecisionKey] = []
        self.fresh: list[DecisionKey] = []

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        record = self._records.get(ambiguity.key())
        if record is not None and self._still_applies(record, ambiguity):
            self.replayed.append(ambiguity.key())
            return Resolution(
                chosen=_chosen(record),
                # The recorded reason, verbatim. Prefixing it with "replayed from a
                # recorded decision" was the plan's wording, and it cannot survive:
                # `reason` is emitted into `main.nf` as the comment above the parameter,
                # so prefixing it makes an upgraded pipeline differ from the published one
                # by exactly that string — and federation §4.1 says loading a locked
                # pipeline reproduces *byte-identical* Nextflow.
                #
                # Nothing is lost. The comment answers "why is this value what it is",
                # which replaying did not change. That this run replayed rather than
                # decided is a fact about the run, and it lives in `resolved_by`, in the
                # decision record, and in the count `mendel upgrade` prints.
                reason=record.reason,
                confidence=record.confidence,
                resolved_by="replay",
            )
        self.fresh.append(ambiguity.key())
        return self._fallback.resolve(ambiguity)

    @staticmethod
    def _still_applies(record: DecisionRecord, ambiguity: Ambiguity) -> bool:
        """Whether the world is close enough to when this was decided.

        Two ways it is not. The candidate set moved, so the record answers a question
        nobody is asking any more; or the choice itself is gone from the registry. Either
        way, replaying would assert a decision between options that no longer exist —
        worse than asking again, because it would look decided.
        """
        if list(record.candidates) != list(ambiguity.candidates):
            return False
        return _chosen(record) in ambiguity.candidates


def _chosen(record: DecisionRecord) -> object:
    """What this record actually decided: a human's override if there is one.

    Checked in one place because it is asked twice — once to validate the record still
    applies and once to answer with it — and the two answering differently is how an
    override could be validated and then not used.
    """
    return record.human_override if record.human_override is not None else record.chosen
