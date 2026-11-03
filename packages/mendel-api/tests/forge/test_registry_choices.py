"""`GET /registry/choices`: what a person can pick from, served rather than retyped."""

from mendel_api.services import registry_choices


def test_a_type_says_what_it_is_and_what_uses_it():
    choices = registry_choices.read()
    assert choices.types
    gtf = next(t for t in choices.types if t.id == "annotation.gtf")
    assert gtf.name == "gene annotation (GTF)"
    assert gtf.family == "annotation"
    assert gtf.family_says
    assert gtf.explain
    assert gtf.made_by == []
    assert "nf-core/star/align@2.7.11b" in gtf.read_by


def test_a_type_brings_its_own_words_and_its_familys():
    choices = registry_choices.read()
    bam = next(t for t in choices.types if t.id == "alignment.bam")
    assert bam.explain
    assert bam.family_says
    assert bam.made_by


def test_a_job_says_what_it_means():
    assert all(role.explain for role in registry_choices.read().roles)


def test_a_job_lists_the_tools_doing_it_and_what_they_read_and_make():
    choices = registry_choices.read()
    assert choices.roles
    alignment = next(r for r in choices.roles if r.id == "alignment")
    assert alignment.tools == ["nf-core/hisat2/align@2.2.2", "nf-core/star/align@2.7.11b"]
    assert "fastq.reads" in alignment.reads
    assert alignment.makes == ["alignment.bam"]


def test_a_tool_says_its_job_and_its_ports():
    choices = registry_choices.read()
    assert choices.tools
    fastqc = next(t for t in choices.tools if t.id == "nf-core/fastqc@0.12.1")
    assert fastqc.roles == ["qc_per_sample"]
    assert fastqc.reads == ["fastq.reads"]
    assert fastqc.makes == ["qc.report"]


def test_every_list_is_in_a_stable_order():
    choices = registry_choices.read()
    for found in (choices.types, choices.roles, choices.tools):
        assert found
        ids = [entry.id for entry in found]
        assert ids == sorted(ids)


def _next(choices, tool):
    return next(t for t in choices.tools if t.id == tool).feeds


def test_a_tool_feeds_what_accepts_its_output_with_its_states():
    choices = registry_choices.read()
    assert "nf-core/samtools/sort@1.24" in _next(choices, "nf-core/star/align@2.7.11b")
    assert "nf-core/samtools/index@1.24" in _next(choices, "nf-core/samtools/sort@1.24")
    # Index and featureCounts need a sorted BAM, which the aligner alone does not make.
    assert "nf-core/samtools/index@1.24" not in _next(choices, "nf-core/star/align@2.7.11b")
    assert "nf-core/subread/featurecounts@2.1.1" not in _next(choices, "nf-core/star/align@2.7.11b")


def test_a_tool_that_reads_what_it_makes_does_not_feed_itself():
    choices = registry_choices.read()
    assert "nf-core/multiqc@1.35" not in _next(choices, "nf-core/multiqc@1.35")
