"""How files are read into samples (#511): the default mate-token rule, a person's pattern, and
the fixes Check these offers."""

import pytest
from mendel_api.services.data import pairing
from mendel_api.services.data.rule import Fix, Rule, checks, group

NAMES = ["Y1_R1.fastq.gz", "Y1_R2.fastq.gz", "Y2_R1.fastq.gz", "Y2_R2.fastq.gz",
         "Y4_R1.fastq.gz", "Y4_2.fq.gz", "notes.txt"]


def named(found):
    return [(name, [NAMES[i] for i in files]) for name, files in found.samples]


def test_default_rule_matches_samples_of():
    found = group(NAMES, Rule(), [])
    assert found.samples == pairing.pair(NAMES) and found.unfit == []


def test_pattern_sample_read_pairs_and_counts_unfit():
    found = group(NAMES, Rule(pattern="{sample}_R{read}.fastq.gz", origin="you"), [])
    assert named(found) == [("Y1", ["Y1_R1.fastq.gz", "Y1_R2.fastq.gz"]),
                            ("Y2", ["Y2_R1.fastq.gz", "Y2_R2.fastq.gz"]),
                            ("Y4", ["Y4_R1.fastq.gz"])]
    assert [NAMES[i] for i in found.unfit] == ["Y4_2.fq.gz", "notes.txt"]


def test_pattern_without_read_makes_single_file_samples():
    names = ["a.fasta", "b.fasta", "c.txt"]
    found = group(names, Rule(pattern="{sample}.fasta", origin="you"), [])
    assert [(n, f) for n, f in found.samples] == [("a", [0]), ("b", [1])] and found.unfit == [2]


@pytest.mark.parametrize("pattern", ["", "no tokens", "{read}.fq", "{sample}{sample}", "{bad}"])
def test_bad_pattern_is_refused_with_a_coded_message(pattern):
    with pytest.raises(ValueError, match="MI0223"):
        group(NAMES, Rule(pattern=pattern, origin="you"), [])


def test_examples_are_the_first_three_fits():
    found = group(NAMES, Rule(pattern="{sample}_R{read}.fastq.gz", origin="you"), [])
    assert found.examples == [("Y1_R1.fastq.gz", "Y1", "1"), ("Y1_R2.fastq.gz", "Y1", "2"),
                              ("Y2_R1.fastq.gz", "Y2", "1")]


def test_use_file_fix_adds_the_mate_under_the_shared_name():
    found = group(NAMES, Rule(), [Fix(kind="use_file", sample="Y4_R1", file="Y4_2.fq.gz")])
    assert ("Y4", ["Y4_R1.fastq.gz", "Y4_2.fq.gz"]) in named(found)
    assert "Y4_2" not in [n for n, _ in found.samples]


def sample(name, files, **facts):
    return {"name": name, "files": [f"/d/{f}" for f in files], "outcome": "measured",
            "type_id": "fastq.reads", "left_out": False,
            "facts": [{"measurement": k, "value": v} for k, v in facts.items()]}


def test_missing_mate_suggests_the_nearby_lone_file():
    found = checks([sample("Y1", ["Y1_R1.fq", "Y1_R2.fq"]),
                    sample("Y2", ["Y2_R1.fq", "Y2_R2.fq"]),
                    sample("Y4_R1", ["Y4_R1.fastq.gz"]), sample("Y4_2", ["Y4_2.fq.gz"])], [])
    [missing] = [c for c in found if c.kind == "missing_mate" and c.sample == "Y4_R1"]
    assert [f.model_dump(exclude_none=True) for f in missing.fixes] == [
        {"kind": "use_file", "sample": "Y4_R1", "file": "Y4_2.fq.gz", "by": "you"},
        {"kind": "leave_out", "sample": "Y4_R1", "by": "you"}]


def test_odd_fact_flags_the_half_length_sample():
    found = checks([sample("Y1", ["a", "b"], read_length=101),
                    sample("Y2", ["c", "d"], read_length=101),
                    sample("Y3", ["e", "f"], read_length=50)], [])
    [odd] = found
    assert (odd.kind, odd.sample) == ("odd_fact", "Y3") and "read_length" in odd.detail
    assert [f.kind for f in odd.fixes] == ["leave_out"]


def test_checks_are_neutral_for_assemblies():
    found = checks([sample("a", ["a.fasta"]), sample("b", ["b.fasta"]),
                    sample("c", ["c.fasta"])], [])
    assert found == []


def test_a_left_out_sample_is_not_checked_again():
    odd = sample("Y3", ["e", "f"], read_length=50)
    odd["left_out"] = True
    found = checks([sample("Y1", ["a", "b"], read_length=101),
                    sample("Y2", ["c", "d"], read_length=101), odd], [])
    assert found == []
