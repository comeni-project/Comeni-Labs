"""Payload for identifying declared types and measurements from a sample excerpt."""

from comeni_core.egress.base import EgressPayload
from comeni_core.spell.marks import Digest, SampleText


class CharacteriseRequest(EgressPayload):
    """Bounded sample excerpt and registry reference supplied for characterisation.

    The caller enforces the protection level before constructing or sending it.
    """

    excerpt: SampleText
    binary_before: bool = False
    """Whether binary content preceded the decoded text excerpt."""
    registry: Digest | None = None
