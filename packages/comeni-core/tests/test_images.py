"""An image reference split into name, tag and digest (#308)."""

import pytest
from comeni_core.spell.images import Image, image_of

WAVE = "community.wave.seqera.io/library/htslib_samtools:1.24--d697cfb9dce007cd"
DIGEST = "sha256:" + "a" * 64


@pytest.mark.parametrize(("ref", "name", "tag", "digest"), [
    (WAVE, "community.wave.seqera.io/library/htslib_samtools", "1.24--d697cfb9dce007cd", None),
    (f"{WAVE}@{DIGEST}", "community.wave.seqera.io/library/htslib_samtools",
     "1.24--d697cfb9dce007cd", DIGEST),
    ("localhost:5000/tools/x:1.0", "localhost:5000/tools/x", "1.0", None),
    ("localhost:5000/tools/x", "localhost:5000/tools/x", None, None),
    (f"quay.io/a/b@{DIGEST}", "quay.io/a/b", None, DIGEST),
])
def test_a_reference_splits(ref, name, tag, digest):
    assert image_of(ref) == Image(name=name, tag=tag, digest=digest)


def test_pinning_keeps_the_tag_for_people_and_adds_the_digest():
    assert image_of(WAVE).pinned(DIGEST).ref == f"{WAVE}@{DIGEST}"


def test_the_image_without_its_digest_is_what_the_module_names():
    assert image_of(f"{WAVE}@{DIGEST}").unpinned().ref == WAVE


def test_a_round_trip_is_the_same_text():
    for ref in (WAVE, f"{WAVE}@{DIGEST}", "localhost:5000/tools/x"):
        assert image_of(ref).ref == ref


@pytest.mark.parametrize("bad", ["", "a b:1", f"x@sha256:{'a' * 63}", "x@md5:abc"])
def test_a_malformed_reference_is_refused(bad):
    with pytest.raises(ValueError):
        image_of(bad)
