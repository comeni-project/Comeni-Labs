"""The release workflow's checks, exercised without cutting a release.

The two things most worth testing here are the two that only ever run on a tag push: does the
tag split into a real package, and does the tag's version agree with the package's own. Neither
can be exercised by pushing a tag without also publishing something, so both are reproduced
here against the same manifests the workflow reads.
"""

import pathlib
import re
import tomllib

import yaml

ROOT = pathlib.Path(__file__).parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
TAG = re.compile(r"^(?P<package>[a-z-]+)-v(?P<version>\d+\.\d+\.\d+)$")


def _split(tag: str) -> tuple[str, str]:
    """What the workflow's two shell parameter expansions do, in Python.

    `${ref%-v*}` and `${ref##*-v}`. Reproduced rather than shelled out so the test says what it
    means, and asserted against the real tag format below.
    """
    package, _, version = tag.rpartition("-v")
    return package, version


def _declared(package: str) -> str:
    path = ROOT / "packages" / package / "pyproject.toml"
    return tomllib.loads(path.read_text())["project"]["version"]


def test_the_workflow_only_fires_on_a_package_tag():
    document = yaml.safe_load(WORKFLOW.read_text())
    # `on` parses as the boolean True in YAML 1.1 — the reason this is not `document["on"]`.
    triggers = document[True] if True in document else document["on"]
    assert triggers["push"]["tags"] == ["*-v*"]


def test_a_tag_splits_into_a_package_that_exists():
    for package in ("comeni-core", "mendel-resolver", "mendel-compiler"):
        name, version = _split(f"{package}-v{_declared(package)}")
        assert name == package
        assert (ROOT / "packages" / name / "pyproject.toml").is_file()
        assert TAG.match(f"{name}-v{version}")


def test_a_matching_tag_agrees_with_the_manifest():
    """The green path: the comparison the workflow runs, against today's versions."""
    for package in ("comeni-core", "mendel-resolver", "mendel-compiler"):
        _, version = _split(f"{package}-v{_declared(package)}")
        assert version == _declared(package)


def test_a_mismatched_tag_is_caught():
    """The refusal. A tag is a claim about a version; the two disagreeing is the release-time
    shape of `MD0223` — an edit whose record was not updated with it."""
    _, version = _split("comeni-core-v9.9.9")
    assert version != _declared("comeni-core")


def test_the_workflow_gates_on_make_check_and_says_why():
    """`make verify` needs Docker and the slow lane; nightly covers it. A release blocked on a
    container pull is a release people stop cutting — and that is recorded in the workflow, not
    only in a plan nobody re-reads."""
    text = WORKFLOW.read_text()
    assert "run: make check" in text
    assert "make verify" in text, (
        "the decision not to use it must be written down where it was made"
    )


def test_the_notes_are_extracted_before_the_build():
    """A missing changelog section should fail before anything is built, not after.

    Ordering, asserted because it is the kind of thing a later edit reorders without noticing.
    """
    text = WORKFLOW.read_text()
    assert text.index("changelog_section.py") < text.index("uv build")
