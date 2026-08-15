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
        "collections", "collections.abc", "enum", "operator", "pathlib", "re", "typing",
        "pydantic", "yaml", "comeni_core", "mendel_resolver",
    },
}
# `re` was added 2026-08-14 for `rules._computed_over` (MD0300, audit A118), and this note
# exists because the guard is supposed to make an addition something somebody argues for.
#
# It is stdlib, does no I/O, and executes no caller-supplied code — `re` compiles patterns,
# it does not evaluate them as expressions, which is the distinction that matters here: the
# whole point of MD0300 is to keep an *expression* out of declared data, so implementing it
# with something that evaluates expressions would be self-defeating. `mendel-compiler`
# already allows it (`modulespec.py` parses `main.nf` with it), so this is a package catching
# up rather than a new capability in the pure set.
#
# The alternative considered and rejected: hand-rolled string scanning, to leave the
# allowlist untouched. Rejected because the check has to distinguish `read_length-1` from
# `paired-end` — a false positive kills a legitimate rule with a diagnostic nobody can turn
# off — and that precision is exactly what a hand-rolled scanner gets subtly wrong.
#
# `enum` was added 2026-08-15 for `premises.PremiseOrigin` (Plan 1.15 Task 1, audit A108),
# and this note exists for the same reason the one above does.
#
# It is stdlib, does no I/O, executes nothing caller-supplied, and reaches no module this
# file cannot see. `comeni-core` has allowed it since the guard was written, and every closed
# vocabulary in this repository is a `StrEnum` — `Tier`, `ValueSource`, `MeasurementKind`,
# `Via`. `PremiseOrigin` is one more of those; this is the first time `mendel-resolver` has
# needed to *declare* a vocabulary rather than read one from `comeni-core`, which is why the
# entry was not already here.
#
# The alternative considered and rejected: string constants. Rejected because an undeclared
# origin then becomes representable — `origin="mesured"` is a live value rather than an
# error — and because `premises._BY_SOURCE` is deliberately total over `ValueSource` and read
# with `[]`, so a new member trips rather than defaulting. That tripwire needs both sides to
# be enums. Same argument as A38's `Via` guard, which earned itself in Plan 1.14.

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

# A58. An allowlist over module *names* says nothing about what a listed module can do.
# PyYAML's non-safe loaders are arbitrary code execution — `!!python/object/apply:`
# instantiates any importable callable — and `yaml.unsafe_load` is a single-link attribute on
# an allowlisted module, so nothing above fires: the rule below it triggers only when the
# attribute is itself a module name, and `unsafe_load` is not one.
#
# This closes `yaml`'s surface. It does not close pydantic's, and this file does not claim to:
# cost-raising, not a proof, exactly as invariant 1 says. The general rule is that a closed
# allowlist holds only if each allowlisted module's own surface is also closed.
BANNED_ATTRIBUTES = {
    "yaml": frozenset(
        {
            "load", "unsafe_load", "full_load", "load_all", "unsafe_load_all", "full_load_all",
            "Loader", "UnsafeLoader", "FullLoader",
        }
    ),
}

# The single place a loader may be named. Every other file in the pure packages reads YAML
# through it — `mendel-compiler` included, which only ever calls `yaml.safe_dump` — which is
# what makes the ban above cost nothing. A path, not a module name: an exemption that matched
# a *spelling* would be A60's shape.
ATTRIBUTE_EXEMPT_PATH = "packages/comeni-core/src/comeni_core/yaml_strict.py"


def _bound_modules(tree: ast.AST) -> dict[str, str]:
    """Local name → the module it was bound from. `import yaml as y` gives `{"y": "yaml"}`.

    A58 needs the module behind a name, not the set of names: a rule keyed on the spelling
    `yaml.` would be defeated by an alias, which is exactly A60's shape one rule over.
    """
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                bound[alias.asname or root] = root
    return bound


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
    modules = _bound_modules(tree)
    exempt = str(where) == ATTRIBUTE_EXEMPT_PATH
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
            # A58, third route. `from yaml import unsafe_load` binds the loader as a bare
            # name, so the attribute rule below never sees an attribute to check.
            #
            # No exemption on this route, deliberately. `yaml_strict.py` spells its loader as
            # `yaml.load(..., Loader=...)` — the attribute form — so an `if not exempt` here
            # would be a branch no file takes, and an inert guard is what A14 is about. If
            # that file is ever refactored to a bare-name import, the right answer is to keep
            # the attribute form rather than to widen this.
            banned = BANNED_ATTRIBUTES.get(node.module.split(".")[0], frozenset())
            found += [
                f"{where} imports `{node.module}.{alias.name}` — an allowlisted module's "
                "unsafe surface. Read YAML through `comeni_core.yaml_strict`, the one file "
                "that may name a loader"
                for alias in node.names
                if alias.name in banned
            ]
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
            # A58. Resolved through `modules` rather than matched on the spelling `yaml.`,
            # so `import yaml as y` is caught by the same rule — A60 is what a
            # spelling-matched check looks like when it fails.
            if node.attr in BANNED_ATTRIBUTES.get(
                modules.get(node.value.id, ""), frozenset()
            ) and not exempt:
                found.append(
                    f"{where} reaches `{dotted}` — an allowlisted module's unsafe surface. "
                    "PyYAML's non-safe loaders instantiate any importable callable. Read "
                    "YAML through `comeni_core.yaml_strict`, the one file that may name a "
                    "loader"
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


def test_a_pure_package_cannot_name_an_unsafe_yaml_loader(tmp_path):
    """A58. `yaml` is on the allowlist and `yaml.unsafe_load` is arbitrary code execution:
    `!!python/object/apply:` instantiates any importable callable.

    It is a single-link attribute on an *allowlisted* module, so no rule above sees it — the
    `ast.Attribute` rule fires only when the attribute is itself a module name, and
    `unsafe_load` is not one. That is a whole axis the scan did not model, not the documented
    two-link/`getattr` gap: an allowlist over module names says nothing about what a listed
    module can do.
    """
    probe = tmp_path / "beacon.py"
    probe.write_text(
        "import yaml\n"
        "def go():\n"
        "    return yaml.unsafe_load("
        "'!!python/object/apply:os.system\\nargs: [id]\\n')\n"
    )
    assert _violations(probe, tmp_path), "yaml.unsafe_load reached os.system with the scan green"


def test_an_aliased_yaml_loader_is_caught_too(tmp_path):
    """A60 is that the dynamic-importer check matches a *spelling*. This rule must not have
    the same shape, so it resolves the local name to the module it was bound from."""
    probe = tmp_path / "beacon.py"
    probe.write_text("import yaml as y\ndef go():\n    return y.unsafe_load('!!python/none')\n")
    assert _violations(probe, tmp_path), "an aliased loader walked past the check"


def test_the_strict_loader_is_the_one_exemption():
    """`yaml_strict.py` names `yaml.load` and a `Loader=` on purpose — it is the single place
    a loader may be spelled, and every other file in the pure packages reads through it.
    That is what makes the ban cost nothing."""
    root = pathlib.Path(__file__).parent.parent
    assert _violations(root / ATTRIBUTE_EXEMPT_PATH, root) == []


def test_a_loader_imported_as_a_bare_name_is_caught(tmp_path):
    """A58, third route. `from yaml import unsafe_load` binds the loader as a bare name and
    calls it with no attribute access anywhere — so the attribute rule has nothing to see.
    Three spellings, one capability; the check has to be on the capability."""
    probe = tmp_path / "beacon.py"
    probe.write_text("from yaml import unsafe_load\ndef go():\n    return unsafe_load('x')\n")
    assert _violations(probe, tmp_path), "a bare-name loader import walked past the check"
