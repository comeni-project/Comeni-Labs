"""Committed prompt files, loaded and identified by version.

**A prompt is product code.** It is the thing that decides what a model is asked, so it is
reviewed, diffed and versioned like any other declaration — the same argument
`docs/design/declared-data.md` makes for the registry, applied one layer up. That means it
lives in a file its caller commits, not in an f-string somebody edits while debugging.

**Changing behaviour means adding `v2`, never editing `v1`.** A review record that names
`forge.analysis.v1` has to be able to reach the text that was actually sent; an id whose
content moved underneath it describes nothing. `PromptTemplate.digest` is what makes that
checkable rather than a convention — a rendered prompt carries the hash of exactly what
crossed the wire, so a stored invocation can be compared against a re-render and disagree
out loud.

**Substitution is `{{name}}` and deliberately not `str.format`.** Every prompt this system
sends carries a JSON Schema, and a schema is full of braces; `format` would raise `KeyError`
on the first `{"type": "object"}` it met. A placeholder syntax that cannot collide with the
payload is worth more than a familiar one.

**This package owns loading, rendering and identity. It owns no prompt text.** Mendel
contracts, roles and Nextflow instructions belong to the caller — `mendel-forge` keeps its
own `prompts/` directory. Shared infrastructure that accumulates every agent's prompts has
become a shared pile rather than a boundary.
"""

import hashlib
import re
from pathlib import Path

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

__all__ = ["PromptId", "PromptTemplate", "Rendered", "UnknownPromptError"]

PromptId = str
"""A template's filename without `.md` — `forge.analysis.v1`. An alias rather than a bare
`str` so a signature says which string it wants; the egress guard's rule that a payload
field is a declared shape is the same instinct one package down."""

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")

_ID = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*\.v\d+$")
"""Every id ends in an explicit `.vN`. An unversioned prompt id is the failure this module
exists to prevent, so it cannot be spelled."""


class UnknownPromptError(ValueError):
    """No committed file carries that id, or its name is not a versioned one. `MA0008`."""


class Rendered(BaseModel):
    """One prompt, as it will be sent, with the identity of what produced it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_id: PromptId
    text: str
    digest: str
    """sha256 of `text`, hex. **Of the rendered text, not the template** — two adaptations of
    the same tool share a template and must not share an invocation record."""


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

    def placeholders(self) -> set[str]:
        return set(_PLACEHOLDER.findall(self.body))

    def render(self, values: dict[str, str]) -> Rendered:
        """Substitute every `{{name}}`. **Missing and surplus are both refusals.**

        A missing placeholder would send the literal `{{dossier}}` to a provider, which is a
        prompt that reads as a bug report; a surplus value is a caller that thinks it supplied
        context and did not, which is the quieter of the two and the reason both are checked.
        """
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
