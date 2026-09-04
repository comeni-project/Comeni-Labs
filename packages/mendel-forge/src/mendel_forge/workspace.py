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
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict

from mendel_forge.scaffold import Scaffold

if TYPE_CHECKING:  # `bundle` imports nothing from here, and this keeps it that way
    from mendel_forge.bundle import ScaffoldBundle

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

    def changed_at(self, name: str) -> datetime:
        """When this draft was last written, in UTC.

        **Timezone-aware on purpose.** It is compared against a stored visit time, and a
        naive datetime raises `TypeError` at that comparison rather than where it was made.
        """
        path = self._dir(name) / "draft.json"
        if not path.exists():
            raise ValueError(
                coded("MF0008", f"no draft named {name!r}")
                + f"\n  drafts: {', '.join(self.names()) or '(none)'}"
            )
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)

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

    # ── the adaptation bundle ──────────────────────────────────────────────────────────

    def write_bundle(self, bundle: "ScaffoldBundle") -> Path:
        """Write one adaptation's directory, and hand back its root.

        **This is the only thing in `mendel-forge` that writes a bundle**, and `bundle.py`
        composes one without touching a filesystem at all. The split is not tidiness: the
        write-boundary guard names exactly two files that may write, and a third would be a
        real weakening of a claim about the whole package — so the composition stays where it
        cannot need one.

        **Every path is re-validated here**, even though `bundle.joined` already validated it.
        `ScaffoldBundle` is a Pydantic model and a Pydantic model can be built by
        `model_validate` from JSON that never went through `joined` — so the guarantee at the
        moment of writing is this check, not the one that happened when somebody used the
        constructor properly.

        **Refuses to overwrite.** An adaptation's source bundle is immutable by design; a second
        write into a directory that exists is either a duplicate job (which `forge_state.claim`
        should already have refused) or a revision that has taken the wrong id, and both are
        better as a refusal than as a silently merged directory.
        """
        root = self.root / "forge" / bundle.adaptation_id
        if root.exists():
            raise ValueError(
                coded("MF0010", f"an adaptation directory already exists at {root.name}")
                + "\n  a source bundle is immutable — a new attempt is a new revision inside it"
            )
        for relative, text in (*bundle.files(), (bundle.manifest_path(), _manifest(bundle))):
            target = self._inside(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        return root

    def _inside(self, relative: str) -> Path:
        """`self.root` joined with a workspace-relative path, refusing anything that escapes.

        **One check, and it used to be two.** The first version also inspected the string for
        `..` and a leading `/` before resolving, with a docstring saying the two halves caught
        different mistakes. Deleting that half changed no test — because it does not. `resolve()`
        normalises `..` lexically *and* follows a symlink pointing out of the workspace, so the
        containment comparison strictly contains the string check.

        That is the fifth pair of mechanisms in this codebase presented as defence in depth
        where one was carrying the whole claim, after `SourceSnapshot.classified`,
        `pegi3s.ALIASES`, `row_version`, and this. The way to tell an earning pair from a hiding
        one is to delete each half separately and watch what fails: `joined` and this genuinely
        differ — that one prevents a bad path being *composed*, and this refuses one that
        arrived through `model_validate` and never went near a constructor.
        """
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root.resolve()):
            raise ValueError(coded("MF0008", f"{relative!r} resolves outside the workspace"))
        return target


def _manifest(bundle: "ScaffoldBundle") -> str:
    """The bundle's own record, without its file contents.

    **`files()` is excluded and that is the point of a manifest**: repeating every file's text
    inside a document that sits beside those files doubles the directory and gives a reader two
    copies that can disagree. What it carries is the addressing — which paths exist, in which
    area — plus the digests that say what the whole thing was built from.
    """
    return (
        json.dumps(
            {
                **bundle.model_dump(mode="json", exclude={"deterministic", "source_files"}),
                "files": [path for path, _ in bundle.files()],
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )
