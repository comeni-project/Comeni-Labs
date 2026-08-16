"""The vendored module is the specification. This parses it.

Tested against the real tree rather than fixtures, deliberately: a parser for nf-core
modules that works on invented input and not on nf-core is worthless, and the tree is
right there.
"""

import pathlib

import pytest
from mendel_compiler.modulespec import ModuleSpec

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/fastqc.contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body

VENDOR = pathlib.Path(__file__).parent.parent / "vendor"


def spec(path: str) -> ModuleSpec:
    return ModuleSpec.parse(VENDOR / "modules/nf-core" / path / "main.nf")


def test_it_reads_the_process_name():
    assert spec("star/align").process == "STAR_ALIGN"
    assert spec("subread/featurecounts").process == "SUBREAD_FEATURECOUNTS"


def test_it_reads_every_input_slot_in_order():
    star = spec("star/align")
    assert [s.kinds for s in star.inputs] == [
        ["val", "path"],  # tuple val(meta), path(reads, stageAs: "input*/*")
        ["val", "path"],  # tuple val(meta2), path(index)
        ["val", "path"],  # tuple val(meta3), path(gtf)
        ["val"],  # val star_ignore_sjdbgtf
    ]
    assert star.inputs[0].names == ["meta", "reads"]
    assert star.inputs[3].names == ["star_ignore_sjdbgtf"]


def test_it_survives_stageas_inside_the_parentheses():
    """`path(reads, stageAs: "input*/*")` is one element, not two."""
    assert spec("star/align").inputs[0].names == ["meta", "reads"]


def test_it_reads_a_three_element_tuple():
    """samtools/sort takes tuple val(meta2), path(fasta), path(fai) — width 3."""
    sort = spec("samtools/sort")
    assert sort.inputs[1].kinds == ["val", "path", "path"]


def test_it_reads_a_single_channel_carrying_a_wide_tuple():
    """featurecounts takes one channel of (meta, bams, annotation)."""
    fc = spec("subread/featurecounts")
    assert len(fc.inputs) == 1
    assert fc.inputs[0].kinds == ["val", "path", "path"]


def test_it_reads_emit_labels():
    star = spec("star/align")
    assert "bam" in star.emits
    assert "log_final" in star.emits


def test_it_ignores_optional_and_topic_on_an_emit_line():
    """`, optional:true, emit: bam` and `, emit: versions_star, topic: versions` both
    appear. Only the emit name is wanted."""
    star = spec("star/align")
    assert "true" not in star.emits
    assert "versions" not in star.emits
    assert "versions_star" in star.emits


def test_it_reads_the_container():
    assert spec("subread/featurecounts").container.startswith("quay.io/biocontainers/subread")


def test_it_reads_which_meta_keys_the_script_uses():
    """The finding that produced `-s 0`: featurecounts reads meta.strandedness, which
    nf-core's own guidelines say is not a standard key."""
    fc = spec("subread/featurecounts")
    keys = {r.key for r in fc.meta_reads}
    assert {"id", "single_end", "strandedness"} <= keys


def test_it_distinguishes_meta_from_meta2():
    """`meta2.id` belongs to a reference channel, not the reads channel. Conflating them
    would make MD0106 demand a measurement for the genome's id."""
    star = spec("star/align")
    variables = {r.variable for r in star.meta_reads}
    assert "meta" in variables


def test_it_notices_whether_the_module_reads_ext_args():
    assert spec("star/align").reads_ext_args is True


def test_it_reads_input_documentation_from_meta_yml():
    genome = spec("star/genomegenerate")
    fasta = next(d for d in genome.documented if d.name == "fasta")
    assert "genome" in fasta.description.lower()


def test_every_vendored_module_parses():
    """A parser that works on the six modules someone tested it against is not a parser."""
    found = sorted(VENDOR.rglob("modules/nf-core/**/main.nf"))
    # Without this the test passes when the glob matches nothing, which is how a parser
    # comes to be "verified" against an empty tree.
    assert len(found) == 10, f"expected the whole vendored spine, globbed {len(found)}"

    failures = []
    for main_nf in found:
        try:
            parsed = ModuleSpec.parse(main_nf)
            assert parsed.process, main_nf
            assert parsed.inputs, main_nf
        except Exception as exc:  # noqa: BLE001 — the message is the point
            failures.append(f"{main_nf}: {exc}")
    assert failures == [], "\n".join(failures)


def test_a_missing_module_raises_rather_than_returning_empty():
    with pytest.raises(FileNotFoundError):
        ModuleSpec.parse(VENDOR / "modules/nf-core/nope/main.nf")


def test_a_container_named_directly_parses(tmp_path):
    """A fixture rather than the tree, because the tree has no such module — and that is
    the point. Every vendored module writes nf-core's singularity/docker ternary, so
    taking the last *quoted alternative* works there and raises IndexError on a module
    that simply names its image. A laboratory wrapping one container writes exactly this.
    """
    module = tmp_path / "main.nf"
    module.write_text(
        _declared(module, 'process LAB_TOOL {\n'
        '    container "quay.io/biocontainers/lab-tool:1.0"\n'
        '\n'
        '    input:\n'
        '    tuple val(meta), path(reads)\n'
        '\n'
        '    output:\n'
        '    tuple val(meta), path("*.txt"), emit: report\n'
        '\n'
        '    script:\n'
        '    """\n'
        '    lab-tool $reads\n'
        '    """\n'
        '}\n')
    )
    parsed = ModuleSpec.parse(module)
    assert parsed.container == "quay.io/biocontainers/lab-tool:1.0"
    assert parsed.inputs[0].names == ["meta", "reads"]
    assert parsed.emits == ["report"]
