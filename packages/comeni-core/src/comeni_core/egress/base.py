"""Shared validation settings for outbound payloads."""

from pydantic import BaseModel, ConfigDict


class EgressPayload(BaseModel):
    """Base for outbound payloads: reject unknown fields and field reassignment.

    Nested collections are not deeply immutable. Transport and access policy
    are handled by the caller, not by this model.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
