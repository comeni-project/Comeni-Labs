import pytest
from mendel_resolver.goal import DataProfile, Goal
from mendel_resolver.rules import RuleTable
from pydantic import ValidationError

RULES = """
rules:
  - id: aligner-long-reads
    subject: aligner
    when: {read_length: {">=": 70}}
    then: {module: nf-core/star/align@1.11.0}
    citation: "STAR handles reads >=70bp well (Dobin 2013)"
  - id: aligner-short-reads
    subject: aligner
    when: {read_length: {"<": 70}}
    then: {module: nf-core/hisat2/align@2.2.1}
    citation: "HISAT2 preferred for short reads"
  - id: strand-reverse
    subject: strandedness
    when: {strandedness: {"==": reverse}}
    then: {value: 2}
    citation: "featureCounts -s 2 for reverse-stranded libraries"
"""


def test_matches_rule_on_numeric_comparison(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    table = RuleTable.load(path)
    rule = table.match("aligner", DataProfile(read_length=150))
    assert rule is not None
    assert rule.id == "aligner-long-reads"
    assert rule.then == {"module": "nf-core/star/align@1.11.0"}


def test_matches_the_other_branch(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    rule = RuleTable.load(path).match("aligner", DataProfile(read_length=50))
    assert rule.id == "aligner-short-reads"


def test_matches_string_equality(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    rule = RuleTable.load(path).match("strandedness", DataProfile(strandedness="reverse"))
    assert rule.then == {"value": 2}


def test_returns_none_when_no_rule_matches(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    assert RuleTable.load(path).match("aligner", DataProfile()) is None


def test_returns_none_for_unknown_subject(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    assert RuleTable.load(path).match("umi_handling", DataProfile(read_length=150)) is None


def test_first_matching_rule_wins(tmp_path):
    path = tmp_path / "r.yml"
    path.write_text(RULES)
    table = RuleTable.load(path)
    assert table.match("aligner", DataProfile(read_length=70)).id == "aligner-long-reads"


def test_goal_has_nowhere_to_put_a_sample_identifier():
    """Invariant 15. Not a rule the user must follow — an absence they cannot fill."""
    with pytest.raises(ValidationError):
        Goal(want=["counts.matrix"], samples=["patient_4471023_R1.fastq.gz"])


def test_profile_rejects_unknown_measurements():
    with pytest.raises(ValidationError):
        DataProfile(read_length=150, sample_name="SILVA_biopsy_01")
