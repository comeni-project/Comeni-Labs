"""Recorded model answers, so a contract test runs offline and forever.

**Keyed by a digest of the prompt, not by call order.** Order-keyed recordings break in the
worst way: a test that adds a call at the front re-points every later assertion at the wrong
answer, and every one of them still passes.

**An unrecorded prompt raises, naming the key and printing the prompt.** A recorded transport
that invented a default would let a test assert against a fixture for a different question,
which is the failure this exists to prevent.

`RecordingTransport` is the tool a developer runs by hand to capture a fixture. **No test uses
it** — `tests/guards/test_no_live_model.py` is what holds that.
"""

import hashlib
import json
from pathlib import Path

from mendel_ai.access import ModelAccess
from mendel_ai.client import Transport


def key_for(access: ModelAccess, prompt: str) -> str:
    """The model as well as the prompt: the same question to two models is two recordings."""
    digest = hashlib.sha256(f"{access.model}\n{prompt}".encode()).hexdigest()
    return digest[:16]


class RecordedTransport:
    """Replays a committed fixture. The transport every contract test uses."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._answers: dict[str, str] = json.loads(path.read_text())

    def send(self, access: ModelAccess, prompt: str) -> str:
        key = key_for(access, prompt)
        if key not in self._answers:
            raise KeyError(
                f"no recording for {key} in {self.path.name}. "
                f"Capture one with RecordingTransport, or check the prompt has not moved.\n"
                f"--- prompt ---\n{prompt}"
            )
        return self._answers[key]


class RecordingTransport:
    """Wraps a real transport and writes what it returns. **Run by hand, never by a test.**

    This is one of the two names `tests/guards/test_no_live_model.py` refuses to find in a test
    file, because reaching a provider from the suite has to be deliberate and visible.
    """

    def __init__(self, inner: Transport, path: Path) -> None:
        self.inner = inner
        self.path = path

    def send(self, access: ModelAccess, prompt: str) -> str:
        answer = self.inner.send(access, prompt)
        existing = json.loads(self.path.read_text()) if self.path.exists() else {}
        existing[key_for(access, prompt)] = answer
        self.path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")
        return answer
