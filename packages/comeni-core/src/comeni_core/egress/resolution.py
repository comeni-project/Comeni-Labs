"""Typed context for resolving an open pipeline choice."""

from comeni_core.egress.base import EgressPayload
from comeni_core.review.question import Excerpt
from comeni_core.spell.marks import ContractId, EdgeRef, Line, NodeId, StateName, Subject, TypeId

CandidateRef = ContractId | EdgeRef | None
"""Contract ID, upstream output reference, or an unspecified parameter candidate."""


class AmbiguityRequest(EgressPayload):
    """Unresolved pipeline choice and the typed context offered to the resolver.

    Candidates may be contract IDs, upstream output references, or None.
    Evidence, required states, and explanatory text describe the open question.
    """

    node_id: NodeId
    subject: Subject
    what: Line = ""
    why_open: Line = ""
    candidates: list[CandidateRef] = []
    closed: bool = True
    evidence: list[Excerpt] = []
    states: list[StateName] = []
    """States required of the candidate being chosen."""
    tier_hint: int | None = None
    type_id: TypeId = ""
    required: list[StateName] = []
