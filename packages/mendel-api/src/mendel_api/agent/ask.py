"""The builder agent asks the person (#463). The question ends the agent's turn; the person's
answer, clicked or typed, starts the next. Over MCP the question goes back to the client, whose
own user answers it."""

from secrets import token_hex
from typing import Literal

from comeni_core.egress.agent import AskedView
from pydantic import BaseModel, Field

from mendel_api.agent.tools import Tool, ToolContext, register


class AskArgs(BaseModel):
    question: str = Field(min_length=1, max_length=400,
                          description="The question, in plain words, as the person reads it")
    shape: Literal["options", "number", "yes_no", "upload", "text"] = Field(
        description="How it is answered: buttons, a number, yes or no, a file, or words")
    options: list[str] = Field(default_factory=list, max_length=8,
                               description="For options: the choices, each a few words")
    unit: str = Field(default="", max_length=20, description="For a number: its unit, e.g. bp")
    type_id: str | None = Field(default=None, description="For an upload: the type of the file")


def ask(ctx: ToolContext, a: AskArgs) -> AskedView:
    if a.shape == "options" and len(a.options) < 2:
        raise ValueError("MI0204: a question with options offers at least two")
    return AskedView(id=token_hex(8), question=" ".join(a.question.split()), shape=a.shape,
                     options=[" ".join(o.split())[:120] for o in a.options], unit=a.unit,
                     type_id=a.type_id)


register(Tool("ask", "Ask the person something only they know, such as whether they have a "
              "file or what their reads are like. Ends your turn; their answer starts the next.",
              AskArgs, ask))
