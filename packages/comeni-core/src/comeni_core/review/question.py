"""Define review questions, offered candidates, and supporting source excerpts.

The models describe an open decision without deciding whether it blocks a particular workflow.
Containers in the authoring and resolution layers own that policy. Keeping this module independent
of :mod:`comeni_core.plan` also prevents a dependency cycle with plan decision models.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from comeni_core.spell.marks import Text

_NO_EXTRAS = ConfigDict(extra="forbid")


class Excerpt(BaseModel):
    """A quoted source span and a stable pointer that lets a reviewer find it.

    File locators are relative to the source root; URLs are also accepted. The model is frozen
    because excerpts can cross an egress boundary and must not change after review.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    locator: Text
    """Relative ``file:line`` locator or URL for the quoted source."""

    text: Text
    """The quoted source text."""


class Candidate(BaseModel):
    """One offered answer and an optional note describing its origin."""

    model_config = _NO_EXTRAS

    value: str
    note: str = ""


class Question(BaseModel):
    """Describe what is being decided, the legal candidates, and the available evidence."""

    model_config = _NO_EXTRAS

    subject: str
    """Stable identifier for the field or concept being decided."""

    what: str = ""
    """Reader-facing description of the value being requested."""

    why_open: str = ""
    """Why a rule or deterministic resolver could not answer the question."""

    candidates: list[Candidate] = Field(default_factory=list)
    """Known answers. An empty list means that no candidates are known."""

    closed: bool = True
    """Whether candidates are exhaustive rather than suggestions."""

    evidence: list[Excerpt] = Field(default_factory=list)
    """Source excerpts a reviewer can use to judge the answer."""

    def legal(self, value: Any) -> bool:
        """Return whether ``value`` is allowed by this question's candidate policy.

        Open questions and questions without candidates accept any value. Collection-valued
        answers are checked member by member against a closed candidate set. Plan subclasses may
        narrow candidates to declared identifier strings, so both strings and ``Candidate``
        instances are supported.
        """
        if not self.candidates or not self.closed:
            return True
        allowed = {c.value if isinstance(c, Candidate) else c for c in self.candidates}
        if isinstance(value, list | set | frozenset | tuple):
            return all(member in allowed for member in value)
        return value in allowed
