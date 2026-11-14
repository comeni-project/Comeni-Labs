"""What a model must reply when proposing a rule (#462). Validated where it arrives: a reply
that does not fit is refused, never repaired into a proposal. It cannot set `cite`: the engine
cites the decisions a row was learned from."""

from pydantic import BaseModel, ConfigDict, JsonValue


class ProposedRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    when: dict[str, JsonValue] = {}
    then: JsonValue
    because: str


class ProposalReply(BaseModel):
    """`rows: []`, with `why`, means the answers hold no rule."""

    model_config = ConfigDict(extra="forbid")

    rows: list[ProposedRow] = []
    why: str
