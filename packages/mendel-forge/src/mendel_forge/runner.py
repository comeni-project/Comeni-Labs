"""What the forge needs from whatever runs a tool's test (forge MVP 4, spec §2).

**This narrow on purpose.** The browser stays the courier for anything a laboratory runs; a forge
test carries only a generated pipeline and public test data, so its result can be checked by the
server. A merged service later replaces one class, not its callers.
"""

from typing import Protocol

FINISHED = frozenset({"succeeded", "failed", "cancelled", "lost"})
"""The run phases that end a run; only `succeeded` can be green."""


class RunnerUnavailable(Exception):
    """The runner could not be reached or refused. The message is safe to show a person."""


class TestRunner(Protocol):
    __test__ = False  # pytest: a name, not a test class

    def submit(self, bundle: bytes, name: str, params: dict) -> str:
        """Start a run of `bundle` and return its id."""
        ...

    def state(self, run_id: str) -> str:
        """The run's phase."""
        ...

    def results(self, run_id: str) -> list[str]:
        """Every published file, as `<process>/<path>`."""
        ...
