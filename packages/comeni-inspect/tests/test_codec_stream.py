"""Bounded codec reads preserve available bytes without accepting corrupt or oversized data."""

import gzip
import io
import random
import zlib

import pytest
from comeni_inspect.stream import Capped, SourceFailed, TooLarge


@pytest.mark.parametrize("buffer_size", [17, 8192, 131072])
@pytest.mark.parametrize("cut", ["body", "trailer"])
def test_truncated_gzip_preserves_every_available_decoded_byte(buffer_size, cut):
    payload = random.Random(303).randbytes(300_000)
    compressed = gzip.compress(payload, mtime=0)
    head = compressed[: len(compressed) // 2] if cut == "body" else compressed[:-5]
    expected = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(head)
    assert expected
    stream = Capped(gzip.GzipFile(fileobj=io.BytesIO(head)), len(payload), given=len(head))
    actual = io.BufferedReader(stream, buffer_size=buffer_size).read()
    assert actual == expected
    assert not stream.capped


@pytest.mark.parametrize("codec", [False, True])
def test_a_normal_head_stops_at_the_cap_and_says_so(codec):
    payload = bytes(range(256)) * 40
    inner = (
        gzip.GzipFile(fileobj=io.BytesIO(gzip.compress(payload))) if codec else io.BytesIO(payload)
    )
    stream = Capped(inner, cap=1000)
    assert io.BufferedReader(stream).read() == payload[:1000]
    assert stream.capped


def test_a_high_expansion_head_is_still_refused():
    compressed = gzip.compress(b"A" * 100_000)
    stream = Capped(
        gzip.GzipFile(fileobj=io.BytesIO(compressed)), cap=50_000, given=len(compressed)
    )
    with pytest.raises(TooLarge):
        io.BufferedReader(stream).read()


def test_a_codec_stream_returning_text_is_named_as_the_source_failure():
    class TextStream:
        def read(self, size):
            return "not bytes"

    stream = Capped(TextStream(), cap=100, name="toy codec")

    with pytest.raises(SourceFailed, match="toy codec failed: it gave str, not bytes"):
        io.BufferedReader(stream).read()


@pytest.mark.parametrize(
    ("damage", "error"),
    [("header", gzip.BadGzipFile), ("checksum", gzip.BadGzipFile), ("deflate", zlib.error)],
)
def test_gzip_corruption_is_still_reported(damage, error):
    compressed = bytearray(gzip.compress(b"available evidence" * 100))
    if damage == "deflate":
        compressed[10] = 0x06  # Reserved DEFLATE block type.
    else:
        compressed[0 if damage == "header" else -8] ^= 0xFF
    stream = Capped(gzip.GzipFile(fileobj=io.BytesIO(compressed)), cap=100_000)
    with pytest.raises(error):
        io.BufferedReader(stream).read()
