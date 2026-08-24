"""wiener-core must never read a clock.

`docs/design/wiener.md` §6.1: backoff, give-up-after and the heartbeat all need to know what
time it is, and reading a clock inside the pure core would break §6's claim in the first week —
the same run would replay to different decisions depending on when you replayed it.

Time enters as a field (`at_ms`) or as an explicit `now_ms` parameter. Never otherwise.

**Why this is a separate file from `test_purity.py`.** The purity allowlist works on module
names, and `datetime` is on `wiener-core`'s list because `admit()` must parse an ISO-8601
`utcTime` into `at_ms`. An allowlist cannot express *this name but not that attribute of it*,
which is the same gap A1 exploited from the other direction — so the distinction between
`datetime` the class and `datetime.now` the reading needs its own scan.

**The plan's version of this guard caught one spelling of three.** It matched
`ast.Attribute` whose `.value` is a bare `ast.Name`, which sees `datetime.now()` after
`from datetime import datetime` — and misses `import datetime; datetime.datetime.now()`,
where the value is another `Attribute`, and `from time import time; time()`, where there is no
attribute at all. Both were watched failing before this was widened; the ledger has the
messages.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1] / "packages/wiener-core/src/wiener_core"

CLOCK_ROOTS = {"datetime", "time"}
"""The modules a reading can come from. `datetime` is also a class inside its own module, which
is what makes `datetime.datetime.now()` and `datetime.now()` both live spellings."""

CLOCK_READS = {"now", "utcnow", "today", "monotonic", "monotonic_ns",
               "time", "time_ns", "perf_counter", "perf_counter_ns"}

BARE_IMPORTS = CLOCK_READS - {"today"}
"""Names that, imported directly, can be called with no attribute access at all —
`from time import monotonic` and then `monotonic()`. Importing one is the offence, because
after that the call is indistinguishable from any other."""


def _root_name(node: ast.expr) -> str | None:
    """The leftmost name of an attribute chain: `datetime.datetime.now` -> `datetime`."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _offences() -> list[str]:
    found: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in CLOCK_READS:
                if _root_name(node) in CLOCK_ROOTS:
                    found.append(f"{path.name}:{node.lineno} reads {node.attr}")
            elif isinstance(node, ast.ImportFrom) and node.module in CLOCK_ROOTS:
                for alias in node.names:
                    if alias.name in BARE_IMPORTS:
                        found.append(
                            f"{path.name}:{node.lineno} imports {node.module}.{alias.name}"
                        )
    return found


def test_the_scan_reached_the_sources():
    """A scan that reaches nothing reports nothing and passes — A67, and the reason this file
    has a guard of its own before it has an assertion."""
    assert list(ROOT.rglob("*.py")), f"no Python under {ROOT} — this scan is running on air"


def test_wiener_core_never_reads_a_clock():
    offences = _offences()
    assert not offences, (
        "wiener-core read a clock:\n  " + "\n  ".join(offences) +
        "\nTime enters as data — a field on the event, or an explicit now_ms parameter. "
        "A run that replays to different decisions depending on when you replay it is not "
        "the thing docs/design/wiener.md §6 claims. See §6.1."
    )
