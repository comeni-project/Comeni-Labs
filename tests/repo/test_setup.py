"""The documented setup gives `make check` and `make dev` what they need."""

import re
import tomllib

from support.paths import ROOT


def test_the_documented_sync_installs_what_make_check_needs():
    """#333: `make check` builds the docs with mkdocs, which sits in the `docs` group, and the
    README's `uv sync` installed only the default groups. It failed on a fresh setup."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    defaults = set(project.get("tool", {}).get("uv", {}).get("default-groups", []))
    assert {"dev", "docs"} <= defaults


def test_dev_checks_for_buildx_before_it_builds():
    """#320: without `docker-buildx`, `make dev` got partway and stopped with a bare
    `--mount option requires BuildKit`. It checks first and says what to install."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    dev = re.search(r"^dev:([^#\n]*)", makefile, re.M)
    assert dev and "buildx-present" in dev.group(1).split()
    recipe = re.search(r"^buildx-present:.*\n((?:\t.*\n)+)", makefile, re.M)
    assert recipe and "docker buildx version" in recipe.group(1)
    assert "docker-buildx" in recipe.group(1)
