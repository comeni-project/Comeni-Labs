"""Approved items become a draft layer, proven with the builder's own loading and conformance."""

import shutil

import pytest
import yaml
from comeni_core.declared.contract import ModuleContract, Provenance
from mendel_forge.forging.assemble import ModuleOrigin, prove, write_layer
from mendel_forge.forging.model import Piece
from mendel_forge.forging.values import items_of
from support.paths import REGISTRY

STAR = REGISTRY / "tools" / "nf-core" / "star" / "align"
PROVENANCE = Provenance(source="forge", drafted_by="ai", approved_by="rafael",
                        approved_at="2026-10-30")


def _star_values() -> dict:
    data = yaml.safe_load((STAR / "contract.yml").read_text())
    data.pop("declares")
    return items_of(ModuleContract(**data))


def _origin() -> ModuleOrigin:
    module = yaml.safe_load((STAR / "module.yml").read_text())
    return ModuleOrigin(source_dir=STAR / "module", module_id="nf-core/star/align",
                        repo=module["upstream"]["repo"], sha=module["upstream"]["sha"],
                        path=module["upstream"]["path"], licence="MIT")


def test_star_align_items_assemble_into_a_layer_that_loads_and_conforms(tmp_path):
    files = write_layer(_star_values(), "nf-core/star/align@2.7.11b", PROVENANCE, _origin(),
                        base=REGISTRY, out=tmp_path / "draft")
    assert files, "files are written"
    assert (tmp_path / "draft" / "tools/nf-core/star/align/contract.yml").is_file()
    assert (tmp_path / "draft" / "tools/nf-core/star/align/module/main.nf").is_file()
    proof = prove(REGISTRY, [], tmp_path / "draft")
    assert proof.loaded and proof.conforms, proof.problems
    assert proof.blames is None


def test_a_wrong_port_fails_conformance_and_blames_the_contract(tmp_path):
    values = _star_values()
    values["contract:output:bamm"] = {**values.pop("contract:output:bam"), "name": "bamm"}
    write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY,
                out=tmp_path / "draft")
    proof = prove(REGISTRY, [], tmp_path / "draft")
    assert proof.loaded and not proof.conforms
    assert proof.blames is Piece.CONTRACT
    assert any(p.code == "MF0512" for p in proof.problems)


def test_a_missing_licence_is_refused_with_a_reason(tmp_path):
    """Review Focus 5: the base has no text for the module's licence, so nothing is written
    that would load without one."""
    base = tmp_path / "base"
    shutil.copytree(REGISTRY, base, ignore=shutil.ignore_patterns(".git"))
    shutil.rmtree(base / "LICENSES")
    origin = _origin().model_copy(update={"licence": "GPL-3.0-or-later"})
    with pytest.raises(ValueError, match="MF0511"):
        write_layer(_star_values(), "nf-core/star/align@2.7.11b", PROVENANCE, origin,
                    base=base, out=tmp_path / "draft")


def test_rewriting_replaces_the_previous_draft(tmp_path):
    out = tmp_path / "draft"
    write_layer(_star_values(), "nf-core/star/align@2.7.11b", PROVENANCE, _origin(),
                base=REGISTRY, out=out)
    (out / "stray.yml").write_text("declares: nonsense\n")
    write_layer(_star_values(), "nf-core/star/align@2.7.11b", PROVENANCE, _origin(),
                base=REGISTRY, out=out)
    assert not (out / "stray.yml").exists()


def test_nothing_is_written_outside_the_draft(tmp_path):
    """Review C1, the second wall: a key that climbs out is refused before a byte is written."""
    values = _star_values()
    values["rules:rule:../../escaped"] = {
        "decides": {"effect": "implementation", "of": "alignment"}, "rows": [],
    }
    with pytest.raises(ValueError, match="MF0511"):
        write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY,
                    out=tmp_path / "drafts" / "one")
    assert not (tmp_path / "escaped.yml").exists()
    assert not (tmp_path / "drafts" / "escaped.yml").exists()


def test_new_content_state_cannot_assemble_without_reviewed_vocabulary(tmp_path):
    values = _star_values()
    values["contract:output:bam"]["type_id"] = "alignment.bam::new_content"
    out = tmp_path / "draft"
    write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY, out=out)
    assert not prove(REGISTRY, [], out).loaded
    values["vocabulary:type:alignment.bam"] = {"id": "alignment.bam", "add_states": ["new_content"]}
    write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY, out=out)
    proof = prove(REGISTRY, [], out)
    assert proof.loaded and proof.conforms, proof.problems
    saved = yaml.safe_load((out / "tools/nf-core/star/align/contract.yml").read_text())
    assert next(p for p in saved["produces"] if p["name"] == "bam")["type_id"] == \
        "alignment.bam::new_content"


def test_quast_assembly_report_keeps_content_and_format_separate(tmp_path):
    from pathlib import Path

    source = Path(__file__).parent / "fixtures/nf-core/quast"
    values = {
        "contract:process": {"nf_process": "QUAST", "nf_include": "modules/nf-core/quast/main"},
        "contract:nf_inputs": [{"literal": [], "because": "Only output typing is exercised here."}
                               for _ in range(3)],
        "contract:output:tsv": {"position": 0, "name": "tsv", "type_id": "qc.report::assembly"},
        "vocabulary:type:qc.report": {"id": "qc.report", "add_states": ["assembly"]},
    }
    origin = ModuleOrigin(source_dir=source, module_id="nf-core/quast", repo="nf-core/modules",
                          sha="fixture", path="modules/nf-core/quast", licence="MIT")
    out = tmp_path / "draft"
    write_layer(values, "nf-core/quast@5.3.0", PROVENANCE, origin, base=REGISTRY, out=out)
    proof = prove(REGISTRY, [], out)
    assert proof.loaded and proof.conforms, proof.problems
    saved = yaml.safe_load((out / "tools/nf-core/quast/contract.yml").read_text())
    assert saved["produces"] == [
        {"name": "tsv", "type_id": "qc.report::assembly", "format": ["tsv"]}]


@pytest.mark.parametrize(("signature", "declaration"), [
    ("alignment.custom", {"id": "alignment.custom", "states": []}),
    ("alignment.bam::reviewed", {"id": "alignment.bam", "add_states": ["reviewed"]}),
])
def test_new_answers_do_not_replace_vocabulary_declarations_at_assembly(
    tmp_path, signature, declaration,
):
    values = _star_values()
    values["questions:output_type:bam"] = {"choice": signature, "new": True}
    values["questions:role"] = {"choice": "custom_alignment", "new": True}
    values["contract:output:bam"]["type_id"] = signature
    values["contract:process"]["roles"].append("custom_alignment")
    out = tmp_path / "draft"
    write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY, out=out)
    assert not prove(REGISTRY, [], out).loaded
    values["vocabulary:role:custom_alignment"] = {
        "name": "custom_alignment", "explain": "A custom alignment job"}
    write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY, out=out)
    assert not prove(REGISTRY, [], out).loaded
    values[f"vocabulary:type:{declaration['id']}"] = declaration
    write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY, out=out)
    proof = prove(REGISTRY, [], out)
    assert proof.loaded and proof.conforms, proof.problems


def test_new_family_requires_an_explicit_declaration_and_loads_with_it(tmp_path):
    """#441: assembly.fasta must carry its reviewed family into the assembled layer."""
    values = _star_values()
    values["contract:output:bam"]["type_id"] = "assembly.fasta"
    values["vocabulary:type:assembly.fasta"] = {"id": "assembly.fasta", "states": []}
    out = tmp_path / "draft"
    write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY, out=out)
    proof = prove(REGISTRY, [], out)
    assert not proof.loaded and proof.blames is Piece.VOCABULARY
    assert any("MD0316" in p.says for p in proof.problems)
    values["vocabulary:family:assembly"] = {
        "id": "assembly", "description": "Assembled genomic sequences and assembly products."}
    write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY, out=out)
    proof = prove(REGISTRY, [], out)
    assert proof.loaded and proof.conforms, proof.problems
    assert yaml.safe_load((out / "vocabulary/families/assembly.yml").read_text()) == {
        "declares": "family", **values["vocabulary:family:assembly"]}


def test_a_derived_fact_is_assembled_into_derives(tmp_path):
    """#461: a setting can take a derived fact's value; the forge drafts the derivation as its
    own item and assembly writes it into the layer's rules."""
    values = _star_values()
    values["rules:derive:ignore_gtf"] = {
        "fact": "ignore_gtf", "kind": "boolean",
        "rows": [{"when": {}, "then": False, "cite": "STAR manual 2.2.3"}]}
    values["rules:rule:alignment"] = {
        "decides": {"effect": "param", "of": "alignment", "name": "star_ignore_sjdbgtf",
                    "when_implementation": ["nf-core/star/align@2.7.11b"]},
        "rows": [{"when": {}, "then": {"fact": "ignore_gtf"}, "cite": "STAR manual 2.2.3"}]}
    write_layer(values, "nf-core/star/align@2.7.11b", PROVENANCE, _origin(), base=REGISTRY,
                out=tmp_path / "draft")
    # One file per fact: a fixed shared name would make the next tool's derivations a
    # shared-file change publishing refuses (Task 6 review).
    derived = yaml.safe_load(
        (tmp_path / "draft" / "rules" / "derived" / "ignore_gtf.yml").read_text())
    assert [d["fact"] for d in derived["derives"]] == ["ignore_gtf"]
    proof = prove(REGISTRY, [], tmp_path / "draft")
    assert proof.loaded, proof.problems


# ── measurements and measurers (#487, #490) ──────────────────────────────────────────────────

FAIDX = REGISTRY / "tools" / "nf-core" / "samtools" / "faidx"
DEPTH = {"id": "depth", "kind": "number", "description": "Mean depth", "cite": "a fixture"}


def _faidx() -> tuple[dict, ModuleOrigin]:
    data = yaml.safe_load((FAIDX / "contract.yml").read_text())
    data.pop("declares")
    module = yaml.safe_load((FAIDX / "module.yml").read_text())
    origin = ModuleOrigin(source_dir=FAIDX / "module", module_id="nf-core/samtools/faidx",
                          repo=module["upstream"]["repo"], sha=module["upstream"]["sha"],
                          path=module["upstream"]["path"], licence="MIT")
    return items_of(ModuleContract(**data)), origin


def _write(values: dict, origin: ModuleOrigin, out):
    return write_layer(values, "nf-core/samtools/faidx@1.24", PROVENANCE, origin,
                       base=REGISTRY, out=out)


def test_a_vocabulary_measurement_is_written(tmp_path):
    """#490: an approved measurement from the vocabulary step was dropped."""
    values, origin = _faidx()
    _write({**values, "vocabulary:measurement:depth": DEPTH}, origin, tmp_path / "draft")
    written = yaml.safe_load((tmp_path / "draft/vocabulary/measurements/depth.yml").read_text())
    assert written["declares"] == "measurement" and written["id"] == "depth"
    proof = prove(REGISTRY, [], tmp_path / "draft")
    assert proof.loaded and proof.conforms, proof.problems


def test_a_measurer_is_written_and_loads(tmp_path):
    from mendel_resolver import layers
    from support.forge_measurer import KEY, measurer
    values, origin = _faidx()
    drafted = {**measurer(), "decided": {"min_sequences": 1}}
    _write({**values, KEY: drafted}, origin, tmp_path / "draft")
    folder = tmp_path / "draft/measurers/measures/genome_length_fai"
    declared = yaml.safe_load((folder / "measurer.yml").read_text())
    assert declared == {
        "declares": "measurer", "id": "genome_length_fai", "version": "1.0.0",
        "measures": "genome_length", "by": "tool", "uses": "nf-core/samtools/faidx@1.24",
        "output": "fai", "entry": "piece/genome_length_fai.py", "runs": ["pipeline"],
        "decided": {"min_sequences": 1}}
    assert (folder / "measurer.yml").read_text().startswith("# samtools faidx writes")
    assert (folder / "piece/genome_length_fai.py").read_text() == drafted["code"]
    assert (folder / "piece/test_genome_length_fai.py").read_text() == drafted["tests"]
    stack = layers.load([REGISTRY, tmp_path / "draft"])
    assert stack.inspection.measurers["genome_length_fai"].uses == "nf-core/samtools/faidx@1.24"
    proof = prove(REGISTRY, [], tmp_path / "draft")
    assert proof.loaded and proof.conforms, proof.problems


def test_one_measurement_from_two_pieces_is_refused(tmp_path):
    values, origin = _faidx()
    with pytest.raises(ValueError, match="MF0511.*drafted twice.*measurers:measurement:depth"
                                         ".*vocabulary:measurement:depth"):
        _write({**values, "vocabulary:measurement:depth": DEPTH,
                "measurers:measurement:depth": DEPTH}, origin, tmp_path / "draft")


def test_a_piece_that_reaches_out_blames_measurers(tmp_path):
    from support.forge_measurer import KEY, measurer
    values, origin = _faidx()
    bad = {**measurer(), "code": "import os\n" + measurer()["code"]}
    _write({**values, KEY: bad}, origin, tmp_path / "draft")
    proof = prove(REGISTRY, [], tmp_path / "draft")
    assert not proof.conforms and proof.blames is Piece.MEASURERS
    assert any("MD0027" in p.says and "os" in p.says for p in proof.problems)
