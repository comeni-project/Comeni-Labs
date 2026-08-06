"""Invariant 1, asserted against behaviour instead of syntax. Audit A1.

`tests/test_purity.py` is a static AST scan over import *statements*. It never reasons
about modules reached as attributes of allowed ones, and `exec` is a builtin needing no
import at all. A module in `comeni-core` importing only `pathlib` and `typing` — both
allowlisted — reached `os.system` via `pathlib.os`, `socket` via `typing.sys.modules`, and
any stdlib module at all via `exec`, and **delivered a serialised `Goal` over TCP** while
`tests/test_purity.py` reported 1 passed.

This file is the version that resists cleverness: it watches what a real build *does*.
An audit hook sees the call however the callee was named, so `pathlib.os.system` and
`os.system` are the same event, and there is no spelling that avoids it.

Neither file supersedes the other. The static scan is fast, runs on every file including
ones no test exercises, and names the offending line. This one covers only the code a
build reaches, but covers it regardless of how it was written. **Two partial guards, and
the honest claim is their union** — which is why `CLAUDE.md` says the pure packages *do
not* reach the network rather than that they cannot.

## Why `exec` and `compile` are not watched here

The plan asked for them. Measured against a real build, they fire from
`mendel_compiler/emit.py` — Jinja2 compiles a template into a code object and execs it,
which is what a template engine is. Flagging that would be a false positive on the
compiler's ordinary work, and a guard that cries wolf is a guard people delete. `exec`,
`eval` and `compile` written *in our own source* are caught statically instead, in
`test_purity.py`, where Jinja's runtime behaviour cannot be confused with ours.
"""

import pathlib
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).parent.parent
_PACKAGES = ("comeni-core", "mendel-resolver", "mendel-compiler")
PURE = [ROOT / "packages" / p / "src" for p in _PACKAGES]

WATCHED = frozenset(
    {
        # network
        "socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo",
        "urllib.Request", "ftplib.connect", "smtplib.connect", "smtplib.send",
        # process execution
        "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty",
    }
)
"""Unambiguous events: a pure package has no business doing any of these.

`subprocess.Popen` is watched even though `mendel-compiler` legitimately runs Nextflow —
the build under test runs **no gate**, so nothing here should spawn anything. Widening the
exemption instead would put a hole in the one package whose banlist already admits it
needs `subprocess`, and this is the check that would have to catch a misuse of it.
"""


def _offending_frames() -> list[str]:
    """Every frame in the current stack that lives inside a pure package.

    Any frame, not the innermost: at a `socket.connect` event the innermost frame belongs
    to the standard library's own `socket.py`, so innermost-only attribution would miss
    exactly the case that was demonstrated.
    """
    found = []
    frame = sys._getframe(1)
    while frame is not None:
        path = pathlib.Path(frame.f_code.co_filename)
        if any(str(path).startswith(str(pure)) for pure in PURE):
            found.append(str(path.relative_to(ROOT)))
        frame = frame.f_back
    return found


def test_the_attribution_rule_recognises_a_pure_package_frame():
    """The hook is only as good as this. Asserted directly so it cannot quietly become
    a function that never matches anything — which is how a guard passes while inert."""
    assert PURE and all(p.is_dir() for p in PURE)
    core = ROOT / "packages" / "comeni-core" / "src" / "comeni_core" / "ir.py"
    assert core.exists()
    assert any(str(core).startswith(str(pure)) for pure in PURE)
    assert not any(str(ROOT / "tests" / "x.py").startswith(str(pure)) for pure in PURE)


@pytest.mark.filterwarnings("ignore")
def test_a_real_build_opens_no_socket_and_spawns_no_process():
    """Resolve and emit the shipped spine with an audit hook armed.

    An audit hook cannot be uninstalled, so everything is imported before arming and the
    flag is cleared afterwards; the hook is inert outside the measured region.
    """
    from comeni_core.goal import Goal
    from mendel_compiler.emit import emit
    from mendel_resolver import layers
    from mendel_resolver.resolve import resolve

    violations: list[str] = []
    state = {"armed": False}

    def hook(event: str, args: object) -> None:
        if not state["armed"] or event not in WATCHED:
            return
        frames = _offending_frames()
        if frames:
            violations.append(f"{event} from {frames[0]}")

    sys.addaudithook(hook)

    loaded = layers.load(ROOT / "registry")
    goal = Goal.model_validate(yaml.safe_load((ROOT / "examples/rnaseq-goal.yml").read_text()))

    state["armed"] = True
    try:
        ir = resolve(goal, loaded.registry, loaded.rules, loaded.measurements)
        emit(ir, loaded.registry, loaded.vocabulary, loaded.measurements)
    finally:
        state["armed"] = False

    assert violations == [], (
        "a pure package opened a socket or spawned a process during a build:\n"
        + "\n".join(violations)
    )
