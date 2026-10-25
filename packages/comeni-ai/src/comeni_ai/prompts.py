"""Load, render, and identify versioned prompt files owned by callers.

Prompt files are committed product inputs. Their explicit ``.vN`` identifiers and rendered-text
digests let stored invocation records identify what was sent. Templates use ``{{name}}``
placeholders so embedded JSON braces remain ordinary text. This package owns these mechanics,
not the prompt text or domain vocabulary.
"""

import hashlib
import re
from pathlib import Path

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

__all__ = ["PromptId", "PromptTemplate", "Rendered", "UnknownPromptError"]

PromptId = str
"""A template filename without ``.md``, ending in an explicit ``.vN`` version."""

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

_ID = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*\.v\d+$")
"""Accepted lowercase, versioned prompt identifier syntax."""


DIVIDER = "<!-- then, per call -->"
"""Separator between a cacheable system prefix and per-call user content."""


class UnknownPromptError(ValueError):
    """No committed file carries that id, or its name is not a versioned one. `MA0008`."""


class Rendered(BaseModel):
    """One prompt, as it will be sent, with the identity of what produced it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_id: PromptId
    text: str
    digest: str
    """Hex SHA-256 digest of the rendered text, not the template body."""


class PromptTemplate(BaseModel):
    """One `<id>.md` under a caller's prompt directory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_id: PromptId
    body: str

    @classmethod
    def load(cls, directory: Path, prompt_id: PromptId) -> "PromptTemplate":
        if not _ID.match(prompt_id):
            raise UnknownPromptError(
                coded("MA0008", f"{prompt_id!r} is not a versioned prompt id")
                + "\n  spell it <name>.v<n> — a prompt with no version cannot be cited later"
            )
        path = directory / f"{prompt_id}.md"
        if not path.is_file():
            known = sorted(p.stem for p in directory.glob("*.md")) if directory.is_dir() else []
            raise UnknownPromptError(
                coded("MA0008", f"no prompt {prompt_id!r} under {directory}")
                + f"\n  known: {', '.join(known) or '(none)'}"
            )
        return cls(prompt_id=prompt_id, body=path.read_text())

    def render_split(self, values: dict[str, str]) -> tuple[str, str]:
        """Render and return ``(system, user)`` around the single required divider."""
        count = self.body.count(DIVIDER)
        if count != 1:
            raise ValueError(
                coded("MA0009", f"{self.prompt_id}: a split prompt has one divider, not {count}")
            )
        fixed, per_call = self.render(values).text.split(DIVIDER)
        return fixed.strip("\n"), per_call.strip("\n")

    def placeholders(self) -> set[str]:
        return set(_PLACEHOLDER.findall(self.body))

    def render(self, values: dict[str, str]) -> Rendered:
        """Substitute every placeholder and reject missing or surplus values."""
        wanted = self.placeholders()
        supplied = set(values)
        if wanted != supplied:
            raise UnknownPromptError(
                coded("MA0009", f"{self.prompt_id}: the values do not match the placeholders")
                + f"\n  missing: {sorted(wanted - supplied) or '(none)'}"
                + f"\n  surplus: {sorted(supplied - wanted) or '(none)'}"
            )
        text = _PLACEHOLDER.sub(lambda m: values[m.group(1)], self.body)
        return Rendered(
            prompt_id=self.prompt_id,
            text=text,
            digest=hashlib.sha256(text.encode()).hexdigest(),
        )
