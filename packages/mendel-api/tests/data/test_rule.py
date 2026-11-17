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
    assert (odd.kind, odd.sample) == ("odd_fact", "Y3") and "Read length" in odd.detail
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


def test_use_file_does_not_rename_onto_a_name_another_folder_took():
    taken = {"Y4"}
    found = group(NAMES, Rule(), [Fix(kind="use_file", sample="Y4_R1", file="Y4_2.fq.gz")], taken)
    names = [n for n, _ in found.samples]
    assert "Y4" not in names and len(names) == len(set(names))


def test_a_lone_file_of_another_kind_is_not_missing_its_mate():
    genome = sample("ref", ["ref.fa"])
    genome["type_id"] = "genome.fasta"
    found = checks([sample("Y1", ["Y1_R1.fq", "Y1_R2.fq"]), sample("Y2", ["Y2_R1.fq", "Y2_R2.fq"]),
                    genome], [])
    assert found == []


def test_check_text_says_values_plainly():
    [odd] = checks([sample("a", ["1", "2"], quality_encoding="phred33"),
                    sample("b", ["3", "4"], quality_encoding="phred33"),
                    sample("c", ["5", "6"], quality_encoding="phred64")], [])
    assert odd.detail == "Quality encoding is phred64; most samples have phred33"


def test_a_missing_mate_is_one_check_not_three():
    """The demo's folder: the lone halves of Y4 differ in `paired` because they are halves; that
    is the missing mate, said once, and Y3's short reads are the other check."""
    y4r1 = sample("Y4_R1", ["Y4_R1.fastq.gz"], paired=False, read_length=101)
    y42 = sample("Y4_2", ["Y4_2.fq.gz"], paired=False, read_length=101)
    found = checks([sample("Y1", ["Y1_R1.fq", "Y1_R2.fq"], paired=True, read_length=101),
                    sample("Y2", ["Y2_R1.fq", "Y2_R2.fq"], paired=True, read_length=101),
                    sample("Y3", ["Y3_R1.fq", "Y3_R2.fq"], paired=True, read_length=50),
                    y4r1, y42], [])
    assert [(c.sample, c.kind) for c in found] == [("Y4_R1", "missing_mate"), ("Y3", "odd_fact")]



def test_a_count_ten_times_off_the_median_is_flagged_with_no_common_value():
    """Walk 2026-11-16: contigs 1, 2, 4, 24, 65 share no value, so BAC47 (65 pieces) was never
    flagged. A number ten times above or below the median is, once there are three to compare."""
    found = checks([sample("MRSA252", ["m.fna"], contigs=1, n50=2902619),
                    sample("N315", ["n.fna"], contigs=2, n50=2814816),
                    sample("USA300", ["u.fna"], contigs=4, n50=2872769),
                    sample("ATCC12600", ["a.fna"], contigs=24, n50=2818338 // 12),
                    sample("BAC47", ["b.fna"], contigs=65, n50=85010)], [])
    flagged = {(c.sample, c.measurement) for c in found}
    assert ("BAC47", "contigs") in flagged and ("BAC47", "n50") in flagged
    assert ("ATCC12600", "contigs") not in flagged
    bac = next(c for c in found if (c.sample, c.measurement) == ("BAC47", "contigs"))
    assert bac.detail == "Contigs is 65; the median is 4"
    assert [f.kind for f in bac.fixes] == ["leave_out"]
    n50 = next(c for c in found if (c.sample, c.measurement) == ("BAC47", "n50"))
    assert n50.detail == "N50 is 85,010; the median is 2,814,816"


def test_two_samples_are_not_enough_to_call_one_odd():
    assert checks([sample("a", ["a.fna"], contigs=1), sample("b", ["b.fna"], contigs=65)], []) == []


def test_a_sample_flagged_twice_is_one_to_check():
    """Walk 2026-11-16: BAC47, odd in contigs and in N50, made '3 samples to check' of two."""
    from mendel_api.services.data.rule import to_check

    found = checks([sample("a", ["a.fna"], contigs=1, n50=2902619),
                    sample("b", ["b.fna"], contigs=2, n50=2814816),
                    sample("c", ["c.fna"], contigs=4, n50=2872769),
                    sample("d", ["d.fna"], contigs=65, n50=85010)], [])
    assert len(found) == 2 and to_check(found) == 1
