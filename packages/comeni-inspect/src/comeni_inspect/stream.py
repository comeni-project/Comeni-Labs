"""Reading through a codec without trusting it: a cap on what comes out, a cut head ends quietly."""

import gzip
import io
import zlib


class TooLarge(Exception):
    """More bytes came out than the cap allows: a decompression bomb, or simply too much."""


class SourceFailed(Exception):
    """The codec's stream failed in a way that is not corruption: the codec's fault, named."""


class Capped(io.RawIOBase):
    """Reads through `inner`, refusing past `cap` bytes; a stream cut mid-way ends quietly.

    **A head is always cut.** A 4 MB head of a gzip file ends mid-stream every time, so
    `EOFError` from the decompressor is the normal end of a head, never an error. Only
    `zlib.error` and `gzip.BadGzipFile` (corruption) reach the caller.
    """

    def __init__(self, inner, cap: int, name: str = "the file"):
        self.inner, self.cap, self.seen, self.name = inner, cap, 0, name

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
        self.seen += len(chunk)
        if self.seen > self.cap:
            raise TooLarge
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
