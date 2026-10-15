"""Shared pipeline validation levels.

The pipeline artifact records the strongest check it passed using this enum.
Checks are executed by mendel_compiler.gates. Keeping the enum in core lets
both packages share these names without core depending on the compiler.
"""

from enum import StrEnum


class Gate(StrEnum):
    """Validation checks, ordered from linting to execution on test data.

    LINT runs Nextflow's linter on the generated workflow.
    PREVIEW previews the workflow without executing its processes.
    STUB runs the workflow using substitute process commands.
    TEST runs the actual tools with test data.
    """

    LINT = "lint"
    PREVIEW = "preview"
    STUB = "stub"
    TEST = "test"
