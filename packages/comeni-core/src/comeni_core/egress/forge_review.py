"""Payloads for a curator reviewing a specific forge candidate revision."""

from enum import StrEnum

from comeni_core.egress.base import EgressPayload
from comeni_core.review.question import Excerpt
from comeni_core.spell.marks import DiagnosticCode, Digest, Text


class ReviewRole(StrEnum):
    """Author of a forge-review turn: curator or model."""

    CURATOR = "curator"
    MODEL = "model"


class ReviewTurn(EgressPayload):
    """One forge-review conversation turn, including its role and text."""

    role: ReviewRole
    content: Text


class ForgeReviewRequest(EgressPayload):
    """Candidate revision, proposed content, diagnostic codes, and review conversation."""

    revision: Digest
    candidate: Text
    validation: list[DiagnosticCode] = []
    evidence: list[Excerpt] = []
    turns: list[ReviewTurn] = []
