"""Every path `ARCHITECTURE.md` names exists.

The whole argument for grouping `comeni-core` by lifecycle stage is that a reader's document
and their directory agree — so the document naming a directory that is not there is the one
failure that would make the grouping pointless.

Prose that names a path is prose that goes stale. That is what `CLAUDE.md`'s two stale counts
were (A71, A72), what `registry.yml:kinds` was until Plan 1.15, and what
`check_registry_drift.py`'s hand-written `KINDS` was until it could not see `roles/`. The
answer each time was the same: derive it, or check it.

Issue #41.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).parent.parent
SOURCE = ROOT / "packages"
PATH = re.compile(r"`((?:comeni_core|mendel_resolver|mendel_compiler)/[\w./]+)`")

PACKAGE_OF = {
    "comeni_core": "comeni-core",
    "mendel_resolver": "mendel-resolver",
    "mendel_compiler": "mendel-compiler",
}


def _resolve(named: str) -> pathlib.Path:
    package = PACKAGE_OF[named.split("/")[0]]
    return SOURCE / package / "src" / named


def test_every_path_architecture_names_exists():
    named = sorted(set(PATH.findall((ROOT / "ARCHITECTURE.md").read_text())))
    assert named, (
        "ARCHITECTURE.md names no module path at all — §1's `Lives in` column is how a reader "
        "gets from a stage to a directory, and it has gone"
    )
    missing = [name for name in named if not _resolve(name).exists()]
    assert missing == [], (
        "ARCHITECTURE.md names paths that do not exist:\n  " + "\n  ".join(missing)
    )


def test_the_five_packages_are_all_named():
    """A stage whose directory the document does not name is a stage a reader cannot find."""
    text = (ROOT / "ARCHITECTURE.md").read_text()
    missing = [
        f"comeni_core/{group}/"
        for group in ("declared", "goal", "plan", "artifact", "spell")
        if f"comeni_core/{group}/" not in text
    ]
    assert missing == [], f"ARCHITECTURE.md does not name these packages: {missing}"
