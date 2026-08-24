# packages/wiener-api/tests/test_tenancy.py
"""Every table carries `lab_id`; every query lives in `repository.py`; every query function
takes one. Three assertions, and the middle one is the one that cannot be forgotten past."""

import ast
import inspect
from pathlib import Path

SRC = Path(__file__).parents[1] / "src/wiener_api"
REPOSITORY = SRC / "repository.py"
SCOPED = {"Run", "RunEventRow", "RunTask", "RunArtifact"}
QUERY_CALLS = {"select", "query", "get", "delete", "update"}


def test_every_table_carries_lab_id():
    import wiener_api.models as m

    for name in sorted(SCOPED):
        cols = {c.name for c in getattr(m, name).__table__.columns}
        assert "lab_id" in cols, f"{name} has no lab_id: {sorted(cols)}"


def test_no_query_is_built_outside_the_repository():
    """The rule is *where*, not *what*. `sa.select(Run)`, `select(Run.id)` and
    `session.get(Run, id)` are all queries and all spelled differently; what they have in
    common is the file they are allowed to be in."""
    offences: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == REPOSITORY:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name not in QUERY_CALLS:
                continue
            mentions = ast.dump(node)
            if any(f"'{model}'" in mentions for model in SCOPED):
                offences.append(f"{path.relative_to(SRC)}:{node.lineno} — {name}()")
    assert not offences, (
        "a query on a tenant-scoped table was built outside repository.py:\n  "
        + "\n  ".join(offences)
        + "\nEvery query is scoped to one laboratory — docs/design/wiener.md §7.1, A177."
    )


def test_every_repository_function_takes_a_lab_id():
    import wiener_api.repository as repo

    for name, fn in vars(repo).items():
        if name.startswith("_") or not callable(fn) or fn.__module__ != repo.__name__:
            continue
        params = list(inspect.signature(fn).parameters)
        assert params[:2] == ["session", "lab_id"], (
            f"{name}{inspect.signature(fn)} — a repository function takes the session and the "
            "laboratory it is scoped to, in that order, so an unscoped query cannot be spelled."
        )
