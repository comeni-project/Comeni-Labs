"""Shared setup belongs in helpers rather than imported collected test modules."""

import ast

from support.paths import PACKAGES, TESTS


def test_tests_do_not_import_other_collected_test_modules():
    roots = [TESTS, *sorted(PACKAGES.glob("*/tests"))]
    files = [p for root in roots for p in root.rglob("*.py") if "fixtures" not in p.parts]
    assert files, "no test source found"
    imports = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            for module in modules:
                if any(part.startswith("test_") for part in module.split(".")):
                    imports.append(f"{path}:{node.lineno}: {module}")
    assert imports == [], "shared setup must be extracted from test modules:\n" + "\n".join(imports)
