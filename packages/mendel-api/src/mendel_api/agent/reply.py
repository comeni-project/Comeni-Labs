"""An explicit answer to the person; only the loop gives it terminal semantics."""

from comeni_core.egress.agent import RepliedView
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mendel_api.agent.tools import Tool, ToolContext, register


class ReplyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        min_length=1,
        max_length=16000,
        description="Your answer",
    )

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("the reply must contain a message")
        return value.strip()


def reply(ctx: ToolContext, args: ReplyArgs) -> RepliedView:
    return RepliedView(message=args.message)


register(
    Tool(
        "reply",
        "Answer the person when finished. Ends your turn.",
        ReplyArgs,
        reply,
    )
)
