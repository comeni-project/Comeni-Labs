"""Resolver port for ambiguities left by deterministic routing and parameter rules."""

from typing import Protocol

from comeni_core.plan.decision import Ambiguity, Resolution


class NoCandidatesError(ValueError):
    """Raised when an ambiguity has no options to choose between."""


class AmbiguityResolver(Protocol):
    """Resolves what the deterministic ladder could not.

    Implementations MUST be side-effect free with respect to the IR; they return
    a Resolution and the resolver records it.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution: ...


class FlagOnlyResolver:
    """Pick the first candidate deterministically and leave the decision flagged.

    This fallback keeps resolution available without an external decision provider while making
    unresolved rule coverage visible to reviewers.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        if not ambiguity.candidates:
            raise NoCandidatesError(f"no candidates for {ambiguity.key()}")
        return Resolution(
            value=ambiguity.candidates[0],
            why=(
                f"nothing decided {ambiguity.subject!r}; selected the first of "
                f"{len(ambiguity.candidates)} candidates without judgement — please review"
            ),
            confidence=0.0,
            by="flag-only",
        )
