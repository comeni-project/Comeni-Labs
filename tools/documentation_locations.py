"""Resolve moved documentation and generate old site addresses without source stubs.

The location map preserves references in records that are deliberately left unchanged.
MkDocs creates forwarding pages in memory; only canonical pages live under docs/.
"""

import json
import posixpath
from pathlib import Path


def moved_docs(root: Path) -> dict[str, str]:
    """Read the explicit old-to-current mapping, or return none for an unrelated tree."""
    manifest = root / "tools" / "documentation_locations.json"
    return json.loads(manifest.read_text()) if manifest.is_file() else {}


def on_files(files, config):
    """Add search-excluded forwarding pages for moved and generated tool URLs."""
    from mkdocs.structure.files import File

    root = Path(__file__).resolve().parent.parent
    locations = moved_docs(root)
    for file in list(files):
        if file.src_uri.startswith("reference/tools/") and file.src_uri.endswith(".md"):
            locations["docs/" + file.src_uri.removeprefix("reference/")] = "docs/" + file.src_uri

    for old, new in locations.items():
        target = new.removeprefix("docs/")
        if files.get_file_from_path(target) is None:
            raise ValueError(f"Documentation address {old} targets a missing page: {new}")
        source = old.removeprefix("docs/")
        if files.get_file_from_path(source) is not None:
            raise ValueError(f"Old documentation address has a source page again: {old}")
        relative = posixpath.relpath(target, posixpath.dirname(source) or ".")
        content = (
            "---\nsearch:\n  exclude: true\n---\n\n"
            f"# Documentation moved\n\nContinue at [the current page]({relative}).\n"
        )
        files.append(File.generated(config, source, content=content))
    return files
