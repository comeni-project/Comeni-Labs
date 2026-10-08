"""Payloads for interpreting and continuing an authoring conversation."""

from enum import StrEnum

from comeni_core.egress.base import EgressPayload
from comeni_core.goal.asked import Goal
from comeni_core.spell.marks import ContractId, Digest, NodeId, OptionId, Text


class AuthoringRole(StrEnum):
    """Author of a conversation turn: person or model."""

    PERSON = "person"
    MODEL = "model"


class AuthoringTurn(EgressPayload):
    """One authoring conversation turn, including its role and text."""

    role: AuthoringRole
    content: Text


class KnownStep(EgressPayload):
    """Draft step identity and contract reference supplied as authoring context."""

    node: NodeId
    contract: ContractId


class AuthoringRequest(EgressPayload):
    """Authoring prompt and conversation, with the goal, known steps, and option IDs.

    The registry digest identifies the declarations used to prepare this context.
    """

    prompt: Text
    turns: list[AuthoringTurn] = []
    goal: Goal | None = None
    steps: list[KnownStep] = []
    options: list[OptionId] = []
    registry: Digest | None = None
