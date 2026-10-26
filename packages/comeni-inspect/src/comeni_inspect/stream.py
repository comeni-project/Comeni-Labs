"""Bound decoded streams while preserving bytes available from a truncated sample head."""

import gzip
import io
import zlib


class TooLarge(Exception):
    """Report cap exhaustion caused by a suspiciously high expansion ratio."""


BOMB_RATIO = 100
"""Minimum output-to-input ratio that makes cap exhaustion an oversized input."""


class SourceFailed(Exception):
    """Report a codec-stream failure that is not recognized data corruption."""


class Capped(io.RawIOBase):
    """Read at most ``cap`` decoded bytes from ``inner``.

    A compressed sample head normally ends before its original stream, so decompressor
    ``EOFError`` ends the bounded read without discarding available bytes. Recognized corruption
    errors still reach the caller.

    Reaching the cap marks ``capped`` and ends an ordinary read. When the known compressed input is
    at least ``BOMB_RATIO`` times smaller than the cap, reaching it raises ``TooLarge`` instead.
    """

    def __init__(self, inner, cap: int, name: str = "the file", given: int | None = None):
        self.inner, self.cap, self.seen, self.name = inner, cap, 0, name
        self.given = given
        """Compressed input size, when known, used to assess the expansion ratio."""
        self.capped = False

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        try:
            # A buffered read may lose decoded bytes when filling the request raises EOFError.
            # read1 returns available output before asking the codec for another chunk.
            read = getattr(self.inner, "read1", self.inner.read)
            chunk = read(len(buffer))
        except EOFError:
            return 0
        except (zlib.error, gzip.BadGzipFile):
            raise
        except Exception as error:  # noqa: BLE001 — a codec's stream is code we did not write
            raise SourceFailed(f"{self.name} failed: {type(error).__name__}") from error
        if not isinstance(chunk, bytes | bytearray):
            raise SourceFailed(f"{self.name} failed: it gave {type(chunk).__name__}, not bytes")
        room = self.cap - self.seen
        if len(chunk) > room:
            if self.given is not None and self.cap >= self.given * BOMB_RATIO:
                raise TooLarge
            chunk, self.capped = chunk[:room], True
        self.seen += len(chunk)
        buffer[: len(chunk)] = chunk
        return len(chunk)


class Prefixed(io.RawIOBase):
    """Yield a previously read prefix before continuing with the underlying stream."""

    def __init__(self, prefix: bytes, inner):
        self.prefix, self.inner = prefix, inner

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        if self.prefix:
            size = min(len(buffer), len(self.prefix))
            buffer[:size], self.prefix = self.prefix[:size], self.prefix[size:]
            return size
        return self.inner.readinto(buffer)
