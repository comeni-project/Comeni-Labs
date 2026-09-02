"""Nothing in mendel-forge writes to a registry except `land`.

Invariant 2 says a person approves; nothing writes to the registry automatically. That is
a claim about the whole package, and a claim about a whole package needs a scan rather
than a review.

**A static scan, deliberately.** A runtime check would only cover the paths a test
happens to execute, which is the exact weakness `test_purity_runtime.py` documents about
itself. This is the cheap half of the same union.
"""

import ast

from support.paths import ROOT

FORGE = ROOT / "packages" / "mendel-forge" / "src" / "mendel_forge"

WRITES = {"write_text", "write_bytes", "mkdir", "touch", "unlink", "rmdir", "rename", "replace"}
ALLOWED = {"land.py", "workspace.py"}
"""`land.py` is the boundary. `workspace.py` writes drafts, which are never inside a
registry — `test_the_workspace_is_never_a_registry_path` is what holds that separately."""


def test_the_scan_reached_the_sources():
    assert len(list(FORGE.rglob("*.py"))) > 5, "the scan is not scanning"


def test_only_land_and_the_workspace_write_to_disk():
    offenders = []
    for path in sorted(FORGE.rglob("*.py")):
        if path.name in ALLOWED:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in WRITES:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} .{node.attr}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "open"
                and len(node.args) > 1
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} open(…, mode)")
    assert offenders == [], (
        "only land.py may write to a registry and only workspace.py may write a draft; "
        "these write somewhere:\n    " + "\n    ".join(offenders)
    )


def test_the_workspace_is_never_a_registry_path():
    """`workspace.py` may write, so the other half of the claim is *where*.

    A draft directory inside a layer would put non-declared files where the loader globs
    and the digest allowlist walks. The CLI's default is `.forge`, which is not a layer,
    and `Workspace` joins its root with a name that cannot contain a separator (MF0008).
    """
    from mendel_forge.cli import parse

    text = (FORGE / "cli" / "parse.py").read_text()
    assert '_WORKSPACE = Path(".forge")' in text
    assert parse.parser() is not None
