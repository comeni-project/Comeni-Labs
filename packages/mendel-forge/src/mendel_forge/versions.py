"""A module's tool version: the conda package that is its tool (forge MVP design, answer 6).

**One rule for two readers.** `tests/registry/test_tool_versions.py` holds a registry id's version
to what its vendored module pins, and the catalogue reads nf-core's current version the same way;
if the two matched names differently, a tool could be *imported* by one and *unknown* by the
other.
"""

import re

import yaml

from mendel_forge.model import CondaPackage

PIN = re.compile(r"^(?:([\w-]+)::)?([\w.-]+)=([^\s=]+)$")
"""`bioconda::star=2.7.11b` or `pigz=2.8`. A `pip:` block or an unpinned name does not match."""


ECOSYSTEM_PREFIXES = ("r-", "bioconductor-", "perl-", "python-", "ncbi-")
"""How conda namespaces a package by its language or publisher: `r-ampir` is ampir. On
nf-core/modules at 810182d (2026-10-29) they take the modules without a readable version from
450 to 397 of 2,123; most of the rest have no `environment.yml` or install with `pip`."""


def same_name(a: str, b: str) -> bool:
    """`trimgalore` is `trim-galore`: case, `-` and `_` do not distinguish package names."""
    return _norm(a) == _norm(b)


def _norm(name: str) -> str:
    return re.sub(r"[-_]", "", name.lower())


def parse_packages(environment_yml: str) -> list[CondaPackage]:
    """Every pinned conda dependency, in file order."""
    data = yaml.safe_load(environment_yml) or {}
    found = (PIN.match(str(item)) for item in data.get("dependencies") or [])
    return [
        CondaPackage(channel=match.group(1), name=match.group(2), version=match.group(3))
        for match in found
        if match
    ]


def tool_version(
    packages: list[CondaPackage], module_path: str, tool_names: list[str]
) -> str | None:
    """The version of the one package named for the module's tool, else for `meta.yml`'s first
    tool. `None` when no package or several match: the first package is often `htslib`, and a
    guess would put a library's version on the tool."""
    candidates = [module_path.split("/")[0], *tool_names[:1]]
    for name in candidates:
        matching = [package for package in packages if _is(package.name, name)]
        if len(matching) == 1:
            return matching[0].version
        if matching:
            return None
    return None


def _is(package: str, tool: str) -> bool:
    bare = next((package[len(p):] for p in ECOSYSTEM_PREFIXES if package.lower().startswith(p)), "")
    return same_name(package, tool) or (bool(bare) and same_name(bare, tool))
