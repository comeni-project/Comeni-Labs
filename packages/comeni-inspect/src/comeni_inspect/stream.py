"""Reading through a codec without trusting it: a cap on what comes out, a cut head ends quietly."""

import gzip
import io
import zlib


class TooLarge(Exception):
    """A decompression bomb: the cap reached from an input at least `BOMB_RATIO` times smaller."""


BOMB_RATIO = 100
"""How much more may come out than went in before reaching the cap means a bomb. FASTQ unpacks
4-6x; gzip's own limit is about 1000x, which is what a bomb is built to reach."""


class SourceFailed(Exception):
    """The codec's stream failed in a way that is not corruption: the codec's fault, named."""


class Capped(io.RawIOBase):
    """Reads through `inner` up to `cap` bytes; a stream cut mid-way ends quietly.

    **A head is always cut.** A 4 MB head of a gzip file ends mid-stream every time, so
    `EOFError` from the decompressor is the normal end of a head, never an error. Only
    `zlib.error` and `gzip.BadGzipFile` (corruption) reach the caller.

    **Reaching the cap is the end of the head too** (issue 221): an ordinary gzipped FASTQ head
    unpacks 4-6x, past a 16 MB cap from a 4 MB head, and refusing it refused ordinary files.
    The cap still bounds what is read, and `capped` says it was reached. Only an input that
    reached it at `BOMB_RATIO` or more is a bomb, `TooLarge`.
    """

    def __init__(self, inner, cap: int, name: str = "the file", given: int | None = None):
        self.inner, self.cap, self.seen, self.name = inner, cap, 0, name
        self.given = given
        """How many bytes went in, when known; a bomb is judged by the ratio to it."""
        self.capped = False

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        try:
            chunk = self.inner.read(len(buffer))
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
    """`prefix`, then the rest of `inner`: a window read whole and put back in front."""

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
