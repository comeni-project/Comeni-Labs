"""Declared data is read with `comeni_core.yaml_strict` (#575).

`yaml.safe_load` is PyYAML's pure-Python loader: 8 to 12 times slower than the C base the strict
loader uses, and it takes the second of two repeated keys silently, so a declared file can read
two ways. A source scan, because the readers are many and each is one line: a new one written the
easy way fails here, not in a file that reads two ways."""

import re

from support.paths import ROOT

ALLOWED = {
    "packages/comeni-inspect/src/comeni_inspect/harness.py":
        "the inspection child depends on pydantic and pyyaml only, not on comeni-core",
    "packages/wiener-api/src/wiener_api/terminal.py":
        "commands.yml ships inside the package; it is code's own file, not declared data",
}


def test_declared_data_is_not_read_with_plain_safe_load():
    sources = sorted((ROOT / "packages").glob("*/src/**/*.py"))
    assert sources, "no source scanned: this would check nothing"
    found = sorted(
        str(path.relative_to(ROOT)) for path in sources
        if re.search(r"\byaml\.safe_load\(", path.read_text())
    )
    assert [p for p in found if p not in ALLOWED] == []
    assert set(ALLOWED) <= set(found), "an allowlisted reader is gone: drop it from ALLOWED"


def test_the_strict_loader_refuses_a_repeated_key():
    """What the readers switched to: a mapping that declares a key twice is refused."""
    import pytest
    from comeni_core import yaml_strict

    with pytest.raises(yaml_strict.DuplicateKeyError):
        yaml_strict.loads("id: a\nid: b\n")
