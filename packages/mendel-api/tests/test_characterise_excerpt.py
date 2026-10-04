"""The excerpt a model is shown (spec §5): readable text, bounded, never more."""

import gzip
import struct
import zlib

from comeni_core.artifact.egress import CharacteriseRequest
from comeni_core.spell.marks import EXCERPT_BYTES, EXCERPT_LINES
from mendel_api.services.characterise import DECODED_CAP, MIN_TEXT, excerpt

HEADER = (
    "@HD\tVN:1.6\tSO:coordinate\n"
    + "".join(f"@SQ\tSN:chr{i}\tLN:{1000 * i}\n" for i in range(1, 30))
    + "@PG\tID:bwa\tPN:bwa\tVN:0.7.17\n"
)


def _bam(header: str = HEADER) -> bytes:
    """A BAM's first block as BGZF writes it: gzip around `BAM\\1`, a length, the header."""
    raw = b"BAM\x01" + struct.pack("<i", len(header)) + header.encode() + b"\x00" * 64
    return gzip.compress(raw)


def test_a_bams_header_is_read_after_its_binary_start():
    got = excerpt(_bam())
    assert got is not None and got.binary_before
    assert got.text.startswith("@HD\tVN:1.6\tSO:coordinate")


def test_gzip_is_recognised_by_its_first_bytes_not_its_name():
    assert excerpt(gzip.compress(b"@r1\nACGT\n+\nIIII\n" * 40)).text.startswith("@r1")


def test_a_fasta_is_text_from_its_first_byte():
    got = excerpt(b">chr1 test\n" + b"ACGT" * 100 + b"\n")
    assert got is not None and not got.binary_before and got.text.startswith(">chr1")


def test_a_very_long_first_line_is_cut_at_the_byte_bound():
    got = excerpt(b">chr1\n" + b"A" * 20_000)
    assert got is not None and len(got.text.encode()) <= EXCERPT_BYTES
    CharacteriseRequest(excerpt=got.text)  # the type agrees


def test_many_lines_are_cut_at_the_line_bound():
    got = excerpt(b"chr1\t.\tgene\t1\t100\t.\t+\t.\tgene_id \"g\";\n" * 1000)
    assert got is not None and len(got.text.splitlines()) == EXCERPT_LINES


def test_a_file_with_no_stretch_of_text_sends_nothing():
    assert excerpt(bytes(range(256)) * 400) is None


def test_too_little_text_sends_nothing():
    assert excerpt(b"\x00\x01" + b"a" * (MIN_TEXT - 1) + b"\x00") is None


def test_a_bomb_stops_at_the_decoded_cap():
    bomb = gzip.compress(b"\x00" * (50 * 2**20))
    assert excerpt(bomb) is None  # 64 KB of zeros decoded, and no text in it


def test_a_truncated_gzip_is_read_as_far_as_it_goes():
    whole = gzip.compress((HEADER * 20).encode())
    got = excerpt(whole[: len(whole) // 2])
    assert got is not None and got.text.startswith("@HD")


def test_several_gzip_members_are_read_through():
    two = gzip.compress(b"\x00" * 10) + gzip.compress(HEADER.encode())
    got = excerpt(two)
    assert got is not None and got.binary_before and got.text.startswith("@HD")


def test_never_more_than_the_cap_is_decoded():
    calls = []
    real = zlib.decompressobj

    class Watching:
        def __init__(self, *a, **k):
            self.inner = real(*a, **k)

        def decompress(self, data, max_length=0):
            calls.append(max_length)
            return self.inner.decompress(data, max_length)

        def __getattr__(self, name):
            return getattr(self.inner, name)

    import mendel_api.services.characterise as c

    c.zlib.decompressobj = Watching
    try:
        excerpt(gzip.compress(b"a" * (5 * 2**20)))
    finally:
        c.zlib.decompressobj = real
    assert calls and all(0 < n <= DECODED_CAP for n in calls)
