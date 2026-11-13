"""A proven draft, placed in the registry's layout and held to the registry's own checks."""

import shutil

import pytest
import yaml
from comeni_core.declared.contract import ModuleContract, Provenance
from mendel_forge.forging.assemble import ModuleOrigin, contract_file, write_layer
from mendel_forge.forging.values import items_of
from mendel_forge.publishing import (
    Decided,
    Record,
    ToolFacts,
    check,
    describe,
    fragment,
    place,
)
from support.paths import REGISTRY

STAR = REGISTRY / "tools/nf-core/star/align"
FACTS = ToolFacts(id="nf-core/star", name="STAR", description="An aligner.",
                  homepage="https://example.org")
TEST = {"inputs": {"reads": ["genomics/a.fq"], "index": ["genomics/star"],
                   "gtf": ["genomics/a.gtf"]},
        "expect": [{"port": "bam", "pattern": "*.bam"}]}


def _values() -> dict:
    data = yaml.safe_load((STAR / "contract.yml").read_text())
    data.pop("declares")
    return {**items_of(ModuleContract(**data)), "tests:test:small": TEST}


def _draft(tmp_path, values=None):
    module = yaml.safe_load((STAR / "module.yml").read_text())
    origin = ModuleOrigin(source_dir=STAR / "module", module_id="nf-core/star/align",
                          repo=module["upstream"]["repo"], sha=module["upstream"]["sha"],
                          path=module["upstream"]["path"], licence="MIT", data_commit="abc123")
    provenance = Provenance(source="forge", drafted_by="ai", approved_by="rafael",
                            approved_at="2026-10-30")
    out = tmp_path / "draft"
    write_layer(values or _values(), "nf-core/star/align@2.7.11b", provenance, origin,
                base=REGISTRY, out=out)
    return out


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout"
    shutil.copytree(REGISTRY, root, ignore=shutil.ignore_patterns(".git"))
    return root


def test_placing_puts_the_tool_in_the_registrys_layout(tmp_path, checkout):
    place(_draft(tmp_path), checkout, "nf-core/star/align", FACTS)
    tool = checkout / "tools/nf-core/star/align"
    assert (tool / "tests/small.yml").is_file() and (tool / "contract.yml").is_file()
    assert (tool / "module/main.nf").is_file()
    assert yaml.safe_load((checkout / "registry.yml").read_text())["name"] != "forge-draft"


def test_each_role_gets_its_own_file(tmp_path, checkout):
    values = {**_values(), "vocabulary:role:forged_one": {"name": "forged_one", "explain": "One."},
              "vocabulary:role:forged_two": {"name": "forged_two", "explain": "Two."}}
    place(_draft(tmp_path, values), checkout, "nf-core/star/align", FACTS)
    roles = checkout / "vocabulary/roles"
    assert not (roles / "forge.yml").exists()
    assert yaml.safe_load((roles / "forged_one.yml").read_text())["roles"] == [
        {"id": "forged_one", "explain": "One."}]
    assert (roles / "forged_two.yml").is_file()


def test_a_new_tool_gets_its_tool_yml(tmp_path, checkout):
    shutil.rmtree(checkout / "tools/nf-core/star")
    place(_draft(tmp_path), checkout, "nf-core/star/align", FACTS)
    written = yaml.safe_load((checkout / "tools/nf-core/star/tool.yml").read_text())
    assert written["declares"] == "tool" and written["name"] == "STAR"


def test_an_existing_tool_yml_is_kept(tmp_path, checkout):
    before = (checkout / "tools/nf-core/star/tool.yml").read_text()
    place(_draft(tmp_path), checkout, "nf-core/star/align", FACTS)
    assert (checkout / "tools/nf-core/star/tool.yml").read_text() == before


def test_a_reforge_replaces_the_tool_folder(tmp_path, checkout):
    stale = checkout / "tools/nf-core/star/align/module/stale.nf"
    stale.write_text("old")
    place(_draft(tmp_path), checkout, "nf-core/star/align", FACTS)
    assert not stale.exists()


def test_a_changed_shared_file_is_refused_with_its_path(tmp_path, checkout):
    values = {**_values(), "vocabulary:type:fastq.reads": {"id": "fastq.reads", "states": []}}
    with pytest.raises(ValueError, match="MF0517.*vocabulary/types/fastq.reads.yml"):
        place(_draft(tmp_path, values), checkout, "nf-core/star/align", FACTS)


def test_the_placed_draft_passes_the_registrys_checks(tmp_path, checkout):
    place(_draft(tmp_path), checkout, "nf-core/star/align", FACTS)
    assert check(checkout) == []
    assert (checkout / "tools/nf-core/star/README.md").is_file()


def test_a_broken_checkout_says_what_failed(tmp_path, checkout):
    place(_draft(tmp_path), checkout, "nf-core/star/align", FACTS)
    contract = checkout / "tools/nf-core/star/align/contract.yml"
    contract.write_text(contract.read_text().replace("nf_process: STAR_ALIGN", "nf_process: NOPE"))
    assert check(checkout)


def test_a_fragment_says_what_arrived(checkout):
    path = fragment(checkout, "nf-core/star/align", "2.7.11b", "Added STAR align.")
    assert path == checkout / "changelog.d/nf-core-star-align.md"
    assert "2.7.11b" in path.read_text()


def test_the_description_names_who_approved_what():
    body = describe(Record(
        module_id="nf-core/star/align", version="2.7.11b", digest="d1", opened_by="rafael",
        decided=[Decided(item="contract:process", drafted_by="ai", decided_by="rafael"),
                 Decided(item="questions:role", drafted_by="ai", decided_by="ana")],
        tests=[("small", "run1")]))
    assert "nf-core/star/align" in body and "2.7.11b" in body
    assert "`contract:process`" in body and "ana" in body and "run1" in body and "d1" in body
    assert "does not show its results are correct" in body


def test_a_drafted_contract_says_its_file_formats(tmp_path):
    draft = _draft(tmp_path)
    contract = yaml.safe_load((draft / "tools/nf-core/star/align/contract.yml").read_text())
    assert contract["produces"][0]["format"] == ["bam"]


def test_a_contract_is_written_with_its_states_in_the_type():
    data = yaml.safe_load((REGISTRY / "tools/nf-core/samtools/index/contract.yml").read_text())
    data.pop("declares")
    written = contract_file(ModuleContract(**data), {})
    assert written["consumes"][0]["type_id"] == "alignment.bam::coordinate_sorted"
    assert "state_required" not in written["consumes"][0]
    assert ModuleContract(**written).consumes[0].state_required == {"coordinate_sorted"}


def test_an_extension_the_registry_already_has_is_placed_as_nothing(tmp_path, checkout):
    """#473: `add_states` never equals the shared declaration, so a forged extension could not
    be published even after the states were added by hand."""
    shared = checkout / "vocabulary/types/qc.report.yml"
    states = yaml.safe_load(shared.read_text())["states"]
    assert states, "qc.report declares no states — this test is measuring nothing"
    before = shared.read_text()
    values = {**_values(), "vocabulary:type:qc.report": {"id": "qc.report",
                                                         "add_states": [states[0]]}}
    place(_draft(tmp_path, values), checkout, "nf-core/star/align", FACTS)
    assert shared.read_text() == before
    values["vocabulary:type:qc.report"] = {"id": "qc.report", "add_states": ["brand_new"]}
    with pytest.raises(ValueError, match="MF0517.*add the states brand_new by hand"):
        place(_draft(tmp_path / "again", values), checkout, "nf-core/star/align", FACTS)


# ── measurements and measurers (#487) ────────────────────────────────────────────────────────

def _registry_measurement(name: str) -> dict:
    data = yaml.safe_load((REGISTRY / "vocabulary/measurements" / f"{name}.yml").read_text())
    data.pop("declares")
    return data


def test_place_drops_assertion_only(tmp_path, checkout):
    """A tool that now measures an `assertion_only` measurement re-declares it without it."""
    measured = {k: v for k, v in _registry_measurement("duplicate_rate").items()
                if k not in ("assertion_only", "assertion_only_because")}
    values = {**_values(), "measurers:measurement:duplicate_rate": measured}
    placed = place(_draft(tmp_path, values), checkout, "nf-core/star/align", FACTS)
    target = checkout / "vocabulary/measurements/duplicate_rate.yml"
    assert target in placed
    assert "assertion_only" not in yaml.safe_load(target.read_text())


def test_place_refuses_another_measurement_change(tmp_path, checkout):
    changed = {k: v for k, v in _registry_measurement("duplicate_rate").items()
               if k not in ("assertion_only", "assertion_only_because")}
    changed["description"] = "something else"
    values = {**_values(), "measurers:measurement:duplicate_rate": changed}
    with pytest.raises(ValueError, match="MF0517.*vocabulary/measurements/duplicate_rate.yml"):
        place(_draft(tmp_path, values), checkout, "nf-core/star/align", FACTS)


def test_place_adds_a_measurer_folder(tmp_path, checkout):
    from support.forge_measurer import measurer
    values = {**_values(), "measurers:measurer:bam_check": {**measurer(), "output": "bam"}}
    placed = place(_draft(tmp_path, values), checkout, "nf-core/star/align", FACTS)
    folder = checkout / "measurers/measures/bam_check"
    assert {folder / "measurer.yml", folder / "piece/bam_check.py",
            folder / "piece/test_bam_check.py"} <= set(placed)
    assert check(checkout) == []
