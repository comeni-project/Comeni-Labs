"""The image's package list is hand-maintained, and it has now been wrong three times.

`uv sync --frozen --all-packages` resolves the whole workspace, so **every** member's
`pyproject.toml` has to be in the layer-cached COPY block — including members the served API
never imports. A missing line fails with `Distribution not found at: file:///app/packages/<x>`,
which is a clear message about a fact nobody can see from the Dockerfile alone.

It went wrong for `mendel-ai`, then for `dag-core` — whose comment says *"a missing line here
fails the build with `Distribution not found`, which is how this was found"* — and then for
`comeni-vendor` in Plan 5A, in a phase whose whole subject was deleting a directory the same
file copied.

**`make check` cannot see any of this.** Its lane builds no image, so the only thing that has
ever caught it is somebody running `docker build`, which is why it recurs. This is the
`test_every_package_is_classified` shape applied to a second hand-maintained list: it makes a
new package fail here rather than in a build somebody runs a week later.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).parent.parent
DOCKERFILE = (ROOT / "Dockerfile").read_text()

COPIED = re.compile(r"^COPY packages/([\w-]+)/pyproject\.toml", re.M)


def _members() -> set[str]:
    return {p.name for p in (ROOT / "packages").iterdir() if (p / "pyproject.toml").is_file()}


def test_every_workspace_member_reaches_the_image():
    """The one that has failed three times."""
    missing = sorted(_members() - set(COPIED.findall(DOCKERFILE)))
    assert missing == [], (
        "these packages are in the workspace and not in the Dockerfile's COPY block. "
        "`uv sync --all-packages` resolves the whole workspace, so the build dies with "
        f"`Distribution not found at: file:///app/packages/<x>`:\n  {missing}"
    )


def test_the_dockerfile_names_no_package_that_does_not_exist():
    """The other direction, and it is the quieter failure: a COPY of a path that is not there
    fails the build too, but a *renamed* package leaves a line that looks maintained."""
    stray = sorted(set(COPIED.findall(DOCKERFILE)) - _members())
    assert stray == [], f"the Dockerfile copies packages that do not exist: {stray}"


def test_the_scan_found_something():
    """A regex that matches nothing reports no missing packages and passes.

    The same guard-of-the-guard `test_purity.py` carries, and for the same reason: this file's
    failure mode is silence in the direction nobody investigates.
    """
    assert len(COPIED.findall(DOCKERFILE)) > 5, "the COPY pattern has drifted from the Dockerfile"
    assert len(_members()) > 5, "packages/ was not read"


def test_a_package_that_needs_its_readme_gets_it():
    """`uv sync` fails without `readme =`'s target, so a package declaring one needs it copied.

    Not every member does — `mendel-api` and the Wiener packages copy only their manifest — so
    this reads each `pyproject.toml` rather than assuming.
    """
    wrong = []
    for name in sorted(_members()):
        manifest = (ROOT / "packages" / name / "pyproject.toml").read_text()
        if "readme = " not in manifest:
            continue
        if f"packages/{name}/README.md" not in DOCKERFILE:
            wrong.append(name)
    assert wrong == [], (
        "these packages declare `readme =` and the Dockerfile does not copy their README, so "
        f"`uv sync` cannot read the manifest it just copied:\n  {wrong}"
    )
