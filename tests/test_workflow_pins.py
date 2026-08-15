"""Every action is pinned by SHA, and the pin is readable.

Two properties, both cheap and both learned the hard way on 2026-08-16, when the Actions were
found three to five majors behind — `actions/checkout` at v4 against v7, `astral-sh/setup-uv` at
v5 against v10 — printing a Node 20 deprecation warning on every run that nobody read.

**This does not check the Node runtime**, and the reason is worth stating: that would need a
network call to GitHub for each action's `action.yml`, and `make check` is deliberately offline.
The runtimes were verified by hand at the pinned SHAs — every one `node24`, including
`nf-core/setup-nextflow`'s composite internals, which is where the old warning actually came
from. **Bumping a pin is what re-opens that question**, and Dependabot's pull request is where it
gets asked, which is the right place for a check that needs the network.
"""

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
SHA = re.compile(r"^[0-9a-f]{40}$")


def _uses() -> list[tuple[str, str]]:
    """Every `uses:` in every workflow, as `(file, value)`."""
    found = []
    for path in WORKFLOWS:
        document = yaml.safe_load(path.read_text())
        for job in document["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    found.append((path.name, step["uses"]))
    return found


def test_there_are_workflows_to_check():
    """A scan that reaches nothing reports nothing and passes — the defect
    `test_architecture.py` was written with, in the same week."""
    assert len(WORKFLOWS) >= 2
    assert len(_uses()) >= 8


def test_every_action_is_pinned_by_commit_sha():
    loose = [
        f"{where}: {value}"
        for where, value in _uses()
        if not SHA.match(value.split("@")[-1].strip())
    ]
    assert loose == [], (
        "these resolve by tag or branch, which whoever controls the action can repoint:\n    "
        + "\n    ".join(loose)
    )


def test_every_pin_carries_the_version_it_came_from():
    """A bare forty-character SHA is unreadable, and unreadable pins are pins nobody updates.

    The comment is also what Dependabot rewrites when it bumps one, so it is load-bearing
    rather than courtesy.
    """
    bare = []
    for path in WORKFLOWS:
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if "uses:" in line and "@" in line and "#" not in line:
                bare.append(f"{path.name}:{number}: {line.strip()}")
    assert bare == [], (
        "these are pinned but do not say to what version:\n    " + "\n    ".join(bare)
    )
