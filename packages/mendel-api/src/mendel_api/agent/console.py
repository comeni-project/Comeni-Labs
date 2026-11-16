"""The builder agent on Run → Console (#511): it reads what the person saw there, carried by the
page with their words, and suggests commands for the run's shell.

**Mendel never reaches Wiener** (A179): the page fetches the console's last lines from Wiener and
sends them with the message, and it runs a suggested read-only command and sends the output back
as the next message. A command that changes anything only the person runs. Paths in what the page
carries are shortened to their last two parts before they are stored or sent to a model.
"""

import re

from comeni_core.egress.agent import CommandView
from pydantic import BaseModel, Field

from mendel_api.agent.tools import Tool, ToolContext, register

_PATH = re.compile(r"(?<![\w.~-])(?:/[\w.@+-]+){3,}")


def shortened(text: str) -> str:
    """Absolute paths cut to `…/<last two parts>`: a log names a person's home and folders, and a
    model needs only which file."""
    return _PATH.sub(lambda m: "…/" + "/".join(m.group(0).rsplit("/", 2)[-2:]), text)


class ConsoleContext(BaseModel):
    """What the page carries from Run → Console with the person's words."""

    run: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    console: str = Field(default="", max_length=40000)
    shell: str = Field(default="", max_length=20000)

    def block(self, seq: int) -> dict:
        return {"id": f"console-{seq}", "kind": "console", "run": self.run,
                "console": shortened(self.console)[-12000:], "shell": shortened(self.shell)[-6000:]}


class SuggestArgs(BaseModel):
    command: str = Field(min_length=1, max_length=500)
    read_only: bool = Field(description="Only reads")
    because: str = Field(min_length=1, max_length=300)


def suggest_command(ctx: ToolContext, a: SuggestArgs) -> CommandView:
    return CommandView(command=" ".join(a.command.split()), read_only=a.read_only,
                       because=" ".join(a.because.split()))


register(Tool("suggest_command", "Run → Console: one shell command in the run's folder. "
              "Read-only ones run and come back; the person runs the rest.",
              SuggestArgs, suggest_command))
