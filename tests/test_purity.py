"""Invariant 1: the pure packages import no web framework, HTTP client or LLM library.

CLAUDE.md sells telemetry safety on this guard being *structural* — "the pure packages
cannot import an HTTP client, so telemetry can only live in `mendel-api`". For that claim
to hold, the guard has to cover the standard library, where the transports actually live,
and the dynamic import forms, which name their target at runtime.

An audit on 2026-08-03 defeated the first version with four lines:

    import urllib.request, socket, http.client
    importlib.import_module("httpx").post(...)
    __import__("openai").OpenAI()

All of it passed, because the banned list held only third-party names and the walk looked
only at import statements.
"""

import ast
import pathlib

# Two shapes, because the packages genuinely differ. `comeni-core` and `mendel-resolver`
# import almost nothing, so their permitted set can be *closed* — an allowlist has no
# unknown unknowns, and a banlist can only ever forbid what somebody thought of, which is
# exactly how the stdlib transports went unnoticed until the 2026-08-03 audit.
#
# `mendel-compiler` cannot be closed: it must run Nextflow, so it needs `subprocess`, and
# `subprocess` can shell out to `curl`. Pretending otherwise would put a hole inside a set
# whose shape implies there is none. An honest banlist is better than a dishonest allowlist.
CLOSED_PACKAGES = {
    "comeni-core": {
        "collections", "collections.abc", "datetime", "enum", "hashlib", "pathlib",
        "typing", "pydantic", "yaml", "comeni_core",
    },
    "mendel-resolver": {
        "collections", "collections.abc", "operator", "pathlib", "typing",
        "pydantic", "yaml", "comeni_core", "mendel_resolver",
    },
}

BANLIST_PACKAGES = ["mendel-compiler"]

BANNED_PREFIXES = (
    # web frameworks
    "fastapi", "starlette", "django", "flask",
    # third-party clients
    "httpx", "requests", "aiohttp",
    # model libraries
    "litellm", "openai", "anthropic",
    # persistence and queueing
    "sqlalchemy", "arq",
    # stdlib transports — a pure package has no business opening a socket, and
    # urllib.request is every bit an HTTP client.
    "urllib", "http", "socket", "ssl", "ftplib", "smtplib", "telnetlib", "asyncio",
    "xmlrpc", "webbrowser",
)

# Naming a module at runtime defeats any import-statement check.
DYNAMIC_IMPORTERS = ("__import__", "import_module")


def _violations(path: pathlib.Path, root: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text())
    where = path.relative_to(root)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Call):
            called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if called in DYNAMIC_IMPORTERS:
                found.append(f"{where} calls {called}() — imports must be statically visible")
            continue
        else:
            continue
        found += [f"{where} imports {n}" for n in names if n.split(".")[0] in BANNED_PREFIXES]
    return found


def _outside_allowlist(path: pathlib.Path, root: pathlib.Path, allowed: set[str]) -> list[str]:
    tree = ast.parse(path.read_text())
    where = path.relative_to(root)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        else:
            continue
        found += [
            f"{where} imports {n}, which is not on this package's allowlist"
            for n in names
            if n.split(".")[0] not in allowed
        ]
    return found


def test_pure_packages_import_nothing_impure():
    root = pathlib.Path(__file__).parent.parent
    violations: list[str] = []
    for pkg, allowed in CLOSED_PACKAGES.items():
        for py in sorted((root / "packages" / pkg / "src").rglob("*.py")):
            violations += _violations(py, root)
            violations += _outside_allowlist(py, root, allowed)
    for pkg in BANLIST_PACKAGES:
        for py in sorted((root / "packages" / pkg / "src").rglob("*.py")):
            violations += _violations(py, root)
    assert violations == [], "Pure packages must not import I/O or model libraries:\n" + "\n".join(
        violations
    )
