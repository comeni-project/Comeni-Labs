import ast
import pathlib

PURE_PACKAGES = ["comeni-core", "mendel-resolver", "mendel-compiler"]
BANNED_PREFIXES = (
    "fastapi", "starlette", "django", "flask",
    "httpx", "requests", "aiohttp",
    "litellm", "openai", "anthropic",
    "sqlalchemy", "arq",
)


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_pure_packages_import_nothing_impure():
    root = pathlib.Path(__file__).parent.parent
    violations = []
    for pkg in PURE_PACKAGES:
        for py in (root / "packages" / pkg / "src").rglob("*.py"):
            for imported in _imports(py):
                if imported.split(".")[0] in BANNED_PREFIXES:
                    violations.append(f"{py.relative_to(root)} imports {imported}")
    assert violations == [], "Pure packages must not import I/O or model libraries:\n" + "\n".join(
        violations
    )
