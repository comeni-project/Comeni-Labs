"""Source evidence for a question, without a model or filesystem access."""

import re

from pydantic import BaseModel


class SourceLine(BaseModel):
    number: int
    text: str


def uses(script: str, name: str) -> list[SourceLine]:
    """Whole Groovy identifiers only: `reads` must not match `reads_index`."""
    pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?![\w$])")
    return [SourceLine(number=n, text=line) for n, line in enumerate(script.splitlines(), 1)
            if name and pattern.search(line)]
