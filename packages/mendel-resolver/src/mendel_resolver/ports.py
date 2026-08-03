"""The seam where AI plugs in. Plan 1 ships only the non-AI implementation."""

from typing import Protocol

from comeni_core.decision import Ambiguity, Resolution


class NoCandidatesError(ValueError):
    """Raised when an ambiguity has no options to choose between."""


class AmbiguityResolver(Protocol):
    """Resolves what the deterministic ladder could not.

    Implementations MUST be side-effect free with respect to the IR; they return
    a Resolution and the resolver records it.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution: ...


class FlagOnlyResolver:
    """Picks the first candidate and flags it. Never guesses cleverly.

    This keeps the whole pipeline runnable with no model available, and makes
    the flagged count an honest measure of how much the rules do not yet cover.
    """

    def resolve(self, ambiguity: Ambiguity) -> Resolution:
        if not ambiguity.candidates:
            raise NoCandidatesError(f"no candidates for {ambiguity.key()}")
        return Resolution(
            chosen=ambiguity.candidates[0],
            reason=(
                f"no rule covered {ambiguity.subject!r}; selected the first of "
                f"{len(ambiguity.candidates)} candidates without judgement — please review"
            ),
            confidence=0.0,
            resolved_by="flag-only",
        )
