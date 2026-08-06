"""The validation-gate vocabulary. The names only — never how one is run.

`PublishBundle` records which gate a pipeline passed (audit A4), and `comeni-core` must
not depend on `mendel-compiler`, so the enum lives here. The **command lines** stay in
`mendel_compiler.gates`, because those are how a gate is run and the core has no business
knowing that a gate is a subprocess, let alone which one.

Same move `Goal` and `DataProfile` made, with the same shim at the old location. The
precedent for a closed vocabulary living in the core is already in `egress.py`, which
declares `ErrorCategory` for the same reason: a payload may only name things the core can
define.
"""

from enum import StrEnum


class Gate(StrEnum):
    """Cheapest first. Each is strictly more evidence than the one above it.

    The ladder matters to a reader of a published bundle rather than only to a build:
    `lint` proves the file parses, and only `test` runs the tools on real data. nf-core
    stubs never read their inputs, so a contract pointing a channel at the wrong upstream
    output passes conformance, `lint`, `preview` and `stub` alike — audit A4. A bundle
    that records `stub` is not a bundle that was checked less carefully; it is a bundle
    whose wiring nothing has checked at all.
    """

    LINT = "lint"
    PREVIEW = "preview"
    STUB = "stub"
    TEST = "test"
