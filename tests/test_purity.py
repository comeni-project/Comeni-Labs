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
import sys

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
    # Foreign function interface. `ctypes.CDLL("libc.so.6")` reaches `socket`, `connect` and
    # `send` without touching Python's socket module, so no Python-level audit event fires
    # and the runtime guard sees nothing either. A pure package has no legitimate FFI need —
    # unlike `subprocess`, which `mendel-compiler` genuinely requires — so unlike the rest of
    # this banlist there is no counter-case. Audit A17.
    "ctypes",
)

# Naming a module at runtime defeats any import-statement check.
DYNAMIC_IMPORTERS = ("__import__", "import_module")

# `exec` and `eval` need no import at all, and `compile` builds what they run. A pure
# package writing one of these is obtaining a module this file cannot see.
CODE_EXECUTORS = ("exec", "eval", "compile")

# Reaching a module as an *attribute* of an allowed one. `pathlib.os` is the `os` module,
# and `os.system` is process execution; `typing.sys.modules["socket"]` is a socket. Both
# were demonstrated by the 2026-08-06 audit against an unmodified tree, from a file
# importing only `pathlib` and `typing`.
#
# Legitimate submodule access, which is a dotted *name* rather than a way of reaching a
# module nobody imported.
DOTTED_ALLOWED = frozenset({"collections.abc", "os.path", "importlib.metadata"})


def _imported_names(tree: ast.AST) -> set[str]:
    """Every name bound to a module by an `import` in this file."""
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
    return bound


def _violations(path: pathlib.Path, root: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text())
    where = path.relative_to(root)
    bound = _imported_names(tree)
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
            elif called in CODE_EXECUTORS and isinstance(node.func, ast.Name):
                # `ast.Name` only: the *builtin*. `re.compile` is an `ast.Attribute` and is
                # an ordinary method call on a module that is already allowlisted — four of
                # them in `modulespec.py`, which is how this distinction got made.
                found.append(
                    f"{where} calls {called}() — it can obtain any module without an import, "
                    "which is what this file is meant to be able to see"
                )
            continue
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            # `pathlib.os`, `typing.sys`: a module reached through another module. Raising
            # the cost, **not closing the class** — an attribute chain two links long
            # (`a.b.c`) or one built with `getattr` still walks past this. The runtime
            # assertion in `test_purity_runtime.py` is the check that does not care how
            # the callee was spelled.
            dotted = f"{node.value.id}.{node.attr}"
            if (
                node.value.id in bound
                and node.attr in sys.stdlib_module_names
                and dotted not in DOTTED_ALLOWED
            ):
                found.append(
                    f"{where} reaches `{dotted}` — that is the `{node.attr}` module as an "
                    "attribute of an imported one, which no import statement declares"
                )
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
