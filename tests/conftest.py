"""Puts `tests/` on `sys.path`, so a file in any subdirectory can `from support...` import.

pytest already does this for the directory holding a `conftest.py`, under the default
`prepend` import mode. It is spelled out anyway so that running one file directly —
`uv run pytest tests/emit/test_counts.py` from a different working directory, or a file
opened by an editor's test runner — resolves the same way the suite does.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))
