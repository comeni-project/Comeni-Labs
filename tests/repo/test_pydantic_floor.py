"""A package that uses `Field(exclude_if=...)` declares a pydantic that honours it (issue 234).

Before 2.12, pydantic accepts `exclude_if` with a deprecation warning and ignores it, so an empty
field is written: a self-hoster on an older pydantic would emit a different `pipeline.yml` from
the same goal (invariants 10 and 13). Checked against 2.9.2, 2.10.6, 2.11.7 (ignored) and 2.12.0.
"""

import re
import tomllib

from support.paths import ROOT

HONOURED_FROM = (2, 12)


def test_every_package_using_exclude_if_requires_a_pydantic_that_honours_it():
    packages = ROOT / "packages"
    users = sorted(
        {
            packages / path.relative_to(packages).parts[0]
            for path in packages.glob("*/src/**/*.py")
            if "exclude_if" in path.read_text()
        }
    )
    assert users, "no package uses exclude_if; this test has nothing to hold"
    for package in users:
        deps = tomllib.loads((package / "pyproject.toml").read_text())["project"]["dependencies"]
        floor = next(
            (re.match(r"pydantic>=(\d+)\.(\d+)", d) for d in deps if d.startswith("pydantic>=")),
            None,
        )
        assert floor, f"{package.name} uses exclude_if and declares no pydantic floor"
        assert (int(floor[1]), int(floor[2])) >= HONOURED_FROM, (
            f"{package.name} uses exclude_if but allows pydantic {floor[1]}.{floor[2]}"
        )
