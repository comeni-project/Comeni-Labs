"""Drafts on disk — the queue, and the boundary's near side.

**The workspace lives outside the registry.** A `proposals/` directory inside a layer
would put non-declared files where the loader globs and the digest allowlist walks, and
would make every draft a commit in the registry's history. Here, a draft is a directory
of ordinary JSON that the CLI reads, the HTTP layer serves and the Plan 3 GUI renders,
and `land.py` is the only thing that turns one into registry data.

JSON rather than YAML: this is machine state, not something a human hand-edits, and
`model_dump_json` round-trips a pydantic model exactly where a YAML dump has to be told
how to spell a frozenset.
"""

import json
import re
from pathlib import Path

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.scaffold import Scaffold

_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    scaffold: Scaffold
    module: str | None = None
    """The generated `main.nf`, for a source that ships none. `None` when the source did."""


class Workspace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: Path

    def _dir(self, name: str) -> Path:
        if not _NAME.match(name):
            raise ValueError(
                coded("MF0008", f"{name!r} is not a plain draft name")
                + "\n  letters, digits, hyphens and underscores only — it becomes a directory"
            )
        return self.root / name

    def save(self, draft: Draft) -> Path:
        directory = self._dir(draft.name)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "draft.json"
        path.write_text(draft.model_dump_json(indent=2) + "\n")
        return path

    def load(self, name: str) -> Draft:
        path = self._dir(name) / "draft.json"
        if not path.exists():
            raise ValueError(
                coded("MF0008", f"no draft named {name!r}")
                + f"\n  drafts: {', '.join(self.names()) or '(none)'}"
            )
        return Draft.model_validate(json.loads(path.read_text()))

    def names(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if (p / "draft.json").exists())

    def delete(self, name: str) -> None:
        path = self._dir(name) / "draft.json"
        path.unlink(missing_ok=True)
        path.parent.rmdir()
