"""Files paired into samples by name (#466, #511), the default reading rule."""

import pytest
from mendel_api.services.data.pairing import pair


def names(found):
    return [(sample, files) for sample, files in found]


def test_mates_pair_and_the_rest_stand_alone():
    files = ["a_R1.fq.gz", "a_R2.fq.gz", "b_1.fq", "b_2.fq", "c_R1.fq"]
    assert names(pair(files)) == [("a", [0, 1]), ("b", [2, 3]), ("c_R1", [4])]


def test_a_repeated_name_is_numbered():
    assert [s for s, _ in pair(["a.fq", "a.fq", "a.fq"])] == ["a", "a#2", "a#3"]


@pytest.mark.parametrize("files", [
    ("S1_L001_R1_001.fastq.gz", "S1_L001_R2_001.fastq.gz"),
    ("a_r1.fq", "a_r2.fq"),
    ("a_R1", "a_R2"),
    ("a_R1.fq.gz", "a_R2.fq"),
    ("a.R1.fq", "a.R2.fq"),
])
def test_real_world_mates_pair(files):
    """bcl2fastq's own names, lowercase, no extension, mixed compression."""
    assert names(pair(list(files))) == [(pair(list(files))[0][0], [0, 1])]


def test_two_files_that_do_not_look_like_mates_are_two_samples():
    """An upload of two files was one sample; a folder of two assemblies is two."""
    assert names(pair(["left.fasta", "right.fasta"])) == [("left", [0]), ("right", [1])]


def test_mates_are_ordered_read_1_first():
    assert names(pair(["x_R2.fq", "x_R1.fq"])) == [("x", [1, 0])]
