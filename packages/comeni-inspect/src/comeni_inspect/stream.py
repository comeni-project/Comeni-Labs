"""Reading through a codec without trusting it: a cap on what comes out, a cut head ends quietly."""

import io


class TooLarge(Exception):
    """More bytes came out than the cap allows: a decompression bomb, or simply too much."""


class Capped(io.RawIOBase):
    """Reads through `inner`, refusing past `cap` bytes; a stream cut mid-way ends quietly.

    **A head is always cut.** A 4 MB head of a gzip file ends mid-stream every time, so
    `EOFError` from the decompressor is the normal end of a head, never an error. Only
    `zlib.error` and `gzip.BadGzipFile` (corruption) reach the caller.
    """

    def __init__(self, inner, cap: int):
        self.inner, self.cap, self.seen = inner, cap, 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        try:
            chunk = self.inner.read(len(buffer))
        except EOFError:
            return 0
        self.seen += len(chunk)
        if self.seen > self.cap:
            raise TooLarge
        buffer[: len(chunk)] = chunk
        return len(chunk)
