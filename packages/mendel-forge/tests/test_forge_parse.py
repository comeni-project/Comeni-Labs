"""Reading one nf-core module folder: everything it declares, and nothing it does not."""

from pathlib import Path

from mendel_forge.nfcore.parse import parse_module

FIXTURES = Path(__file__).parent / "fixtures" / "nf-core"


def _parse(path: str):
    return parse_module(FIXTURES / path, path)


def test_star_align_reads_everything():
    module = _parse("star/align")
    assert module.name == "star/align"
    assert module.description == "Align reads to a reference genome using STAR"
    assert module.tool_version == "2.7.11b"
    assert [tool.name for tool in module.tools] == ["star"]
    assert module.tools[0].biotools == "biotools:star"
    assert module.tools[0].licence == ["MIT"]
    reads = next(channel for channel in module.inputs if channel.name == "reads")
    assert reads.type == "file"
    names = [channel.name for channel in module.outputs]
    assert "bam" in names
    fastq = next(channel for channel in module.outputs if channel.name == "fastq")
    assert fastq.ontologies == ["http://edamontology.org/format_3989"]
    assert module.containers == [
        "https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/26/"
        "268b4c9c6cbf8fa6606c9b7fd4fafce18bf2c931d1a809a0ce51b105ec06c89d/data",
        "community.wave.seqera.io/library/htslib_samtools_star_gawk:ae438e9a604351a4",
    ]
    assert module.label == "process_high"
    assert module.tests, "the nf-test cases are read"
    assert module.tests[0].name == "homo_sapiens - single_end"
    assert "genomics/homo_sapiens/genome/genome.fasta" in module.tests[0].datasets
    assert module.authors, "authors are read"
    assert module.problems == []


def test_meta_is_never_a_channel():
    module = _parse("fastqc")
    assert module.inputs, "fastqc has inputs"
    assert all(not channel.name.startswith("meta") for channel in module.inputs)
    assert [channel.name for channel in module.inputs] == ["reads"]
    html = next(channel for channel in module.outputs if channel.name == "html")
    assert html.pattern == "*_{fastqc.html}"


def test_flat_channel_lists_read_like_nested_ones(tmp_path):
    """Older modules list `input:` as single-key maps rather than tuples of them."""
    folder = tmp_path / "old"
    folder.mkdir()
    (folder / "meta.yml").write_text(
        "name: old\n"
        "input:\n  - reads:\n      type: file\n      pattern: '*.fastq.gz'\n"
        "output:\n  - bam:\n      type: file\n      pattern: '*.bam'\n"
    )
    module = parse_module(folder, "old")
    assert [(c.name, c.pattern) for c in module.inputs] == [("reads", "*.fastq.gz")]
    assert [(c.name, c.pattern) for c in module.outputs] == [("bam", "*.bam")]


def test_broken_meta_is_kept_with_MF0500():
    module = _parse("broken-meta")
    assert module.name == "broken-meta"
    assert module.problems, "the module is kept with its problem"
    assert module.problems[0].code == "MF0500"


def test_missing_environment_gives_unknown_version_MF0501():
    module = _parse("no-environment")
    assert module.tool_version is None
    assert [problem.code for problem in module.problems] == ["MF0501"]


def test_two_tools_gives_unknown_version_MF0501():
    module = _parse("two-tools")
    assert module.packages, "its packages are still read"
    assert module.tool_version is None
    assert [problem.code for problem in module.problems] == ["MF0501"]


def _folder(tmp_path, meta: bytes | str, environment: str | None = None):
    folder = tmp_path / "odd"
    folder.mkdir()
    (folder / "meta.yml").write_bytes(meta if isinstance(meta, bytes) else meta.encode())
    if environment is not None:
        (folder / "environment.yml").write_text(environment)
    return folder


def test_a_malformed_environment_is_a_problem_not_a_crash(tmp_path):
    for environment in ("dependencies: [unclosed\n", "- just\n- a list\n"):
        folder = tmp_path / str(abs(hash(environment)))
        folder.mkdir()
        (folder / "meta.yml").write_text("name: odd\n")
        (folder / "environment.yml").write_text(environment)
        module = parse_module(folder, "odd")
        assert module.tool_version is None
        assert "MF0501" in [p.code for p in module.problems]


def test_a_meta_that_is_not_utf8_is_MF0500(tmp_path):
    module = parse_module(_folder(tmp_path, b"name: \xff\xfe odd\n"), "odd")
    assert module.problems, "kept with its problem"
    assert module.problems[0].code == "MF0500"


def test_scalars_where_lists_belong_are_read_as_nothing(tmp_path):
    meta = ("name: odd\nkeywords: 5\nauthors: 5\n"
            "input:\n  - reads:\n      type: file\n      ontologies: 5\n"
            "output:\n  bam: 5\n")
    module = parse_module(_folder(tmp_path, meta), "odd")
    assert module.keywords == [] and module.authors == []
    assert [c.name for c in module.inputs] == ["reads"]
    assert module.inputs[0].ontologies == []
