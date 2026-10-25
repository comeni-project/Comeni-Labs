"""Record and replay model answers for offline contract tests.

Recordings use a digest of the model and prompt rather than call order. Missing recordings raise
with the expected key and prompt. Tests use :class:`RecordedTransport`; developers may run
:class:`RecordingTransport` manually to capture fixtures.
"""

import hashlib
import json
from pathlib import Path

from comeni_ai.access import ModelAccess
from comeni_ai.client import Transport


def key_for(access: ModelAccess, prompt: str) -> str:
    """The model as well as the prompt: the same question to two models is two recordings."""
    digest = hashlib.sha256(f"{access.model}\n{prompt}".encode()).hexdigest()
    return digest[:16]


class RecordedTransport:
    """Replay responses from a committed JSON fixture without network access."""

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
    """Wrap a real transport and write responses to a fixture during manual capture."""

    def __init__(self, inner: Transport, path: Path) -> None:
        self.inner = inner
        self.path = path

    def send(self, access: ModelAccess, prompt: str) -> str:
        answer = self.inner.send(access, prompt)
        existing = json.loads(self.path.read_text()) if self.path.exists() else {}
        existing[key_for(access, prompt)] = answer
        self.path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")
        return answer
