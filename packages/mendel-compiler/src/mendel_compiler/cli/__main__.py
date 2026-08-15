"""`python -m mendel_compiler.cli`.

A module is executable with `-m`; a package is not, without this. `cli` became a package in
issue #41 and four tests run it that way — `test_output_is_identical_across_hash_seeds` needs a
subprocess because it sets `PYTHONHASHSEED`, and the conformance tests want the real exit code
rather than a return value.

The console script in `pyproject.toml` points at `main` directly and never reaches here, which
is why the failure showed up only in the tests: the entry point everybody uses was fine.
"""

from mendel_compiler.cli import main

raise SystemExit(main())
