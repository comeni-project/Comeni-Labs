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
