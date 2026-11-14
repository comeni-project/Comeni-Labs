"""A reply is checked against the registry and the module before anything is stored (§3)."""

from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from comeni_core.declared.contract import ModuleContract
from mendel_compiler.modulespec import ModuleSpec
from mendel_forge.forging.validate import check_items, known, pending_used
from mendel_forge.forging.values import items_of
from mendel_resolver import layers
from support.paths import REGISTRY

STAR_NF = Path(__file__).parent / "fixtures" / "nf-core" / "star" / "align" / "main.nf"


@pytest.fixture(scope="module")
def stack():
    return layers.load(REGISTRY)


@pytest.fixture(scope="module")
def star_items():
    data = yaml.safe_load((REGISTRY / "tools/nf-core/star/align/contract.yml").read_text())
    data.pop("declares")
    return items_of(ModuleContract(**data))


def _codes(problems) -> list[str]:
    return [p.code for p in problems]


def test_star_aligns_registry_items_pass(stack, star_items):
    assert check_items(star_items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_an_unknown_type_is_MF0507(stack, star_items):
    items = {**star_items, "contract:input:reads": {**star_items["contract:input:reads"],
                                                    "type_id": "nothing.here"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]


def test_a_type_proposed_in_this_adaptation_is_known(stack, star_items):
    items = {**star_items,
             "contract:input:reads": {**star_items["contract:input:reads"],
                 "type_id": "new.type", "state_required_conventional": []},
             "vocabulary:type:new.type": {"id": "new.type", "states": []}}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_a_type_in_another_adaptations_unassembled_draft_is_unknown(stack, star_items):
    """Review Focus 3: only assembled drafts are pending; anything else is simply unknown."""
    items = {**star_items, "contract:input:reads": {**star_items["contract:input:reads"],
                                                    "type_id": "draft.only"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]


def test_a_pending_type_is_accepted_and_flagged(stack, star_items):
    items = {**star_items, "contract:input:reads": {**star_items["contract:input:reads"],
                                                    "type_id": "genome.index.bwa",
                                                    "state_required_conventional": []}}
    seen = known(stack, pending=frozenset({"genome.index.bwa"}))
    assert check_items(items, seen, ModuleSpec.parse(STAR_NF)) == []
    assert pending_used(items, seen) == {"genome.index.bwa"}


def test_a_port_main_nf_lacks_is_MF0508(stack, star_items):
    items = {**star_items, "contract:input:ghost": {"position": 9, "name": "ghost",
                                                    "type_id": "fastq.reads"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0508"]


def test_a_param_routed_nowhere_is_MF0509(stack, star_items):
    items = {**star_items, "parameters:param:loose": {"position": 9, "name": "loose",
                                                      "via": "ext", "default": 1}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0509"]


def test_a_port_whose_name_differs_from_its_key_is_MF0508(stack, star_items):
    items = {**star_items, "contract:output:bam": {**star_items["contract:output:bam"],
                                                   "name": "bamm"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0508"]


def test_undeclared_output_state_requires_explicit_new_option(stack):
    question = {"asks": "What does this report hold?", "options": [
        {"id": "qc.report::assembly", "label": "assembly report", "because": "assembly metrics"}]}
    items = {"questions:output_type:report": question}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]
    question["options"][0]["new"] = True
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_an_undeclared_contract_state_requires_an_answer_or_vocabulary(stack, star_items):
    items = {**star_items, "contract:output:bam": {**star_items["contract:output:bam"],
                                                 "type_id": "alignment.bam::new_state"}}
    assert _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF))) == ["MF0507"]
    items["questions:output_type:bam"] = {"choice": "alignment.bam::new_state", "new": True}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []
    del items["questions:output_type:bam"]
    items["vocabulary:type:alignment.bam"] = {"id": "alignment.bam", "add_states": ["new_state"]}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_approved_new_answers_permit_draft_references_without_declaring_vocabulary(
    stack, star_items,
):
    items = {**star_items,
        "questions:role": {"choice": "custom_alignment", "new": True},
        "questions:output_type:bam": {"choice": "alignment.custom::reviewed", "new": True},
        "contract:process": {**star_items["contract:process"], "roles": ["custom_alignment"]},
        "contract:output:bam": {**star_items["contract:output:bam"],
                                "type_id": "alignment.custom::reviewed"}}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []
    assert not any(key.startswith("vocabulary:") for key in items)


def test_an_offered_new_option_does_not_grant_contract_reference_permission(stack, star_items):
    items = {**star_items,
        "questions:output_type:bam": {"asks": "What is it?", "options": [
            {"id": "alignment.custom", "label": "Custom", "because": "New", "new": True}]},
        "contract:output:bam": {**star_items["contract:output:bam"], "type_id": "alignment.custom"}}
    assert "MF0507" in _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF)))


@pytest.mark.parametrize("status", ["approved", "proposed", "reopened", "removed", "rejected"])
def test_only_approved_answer_values_reach_the_draft_permission_check(status):
    from mendel_forge.forging.model import Adaptation, Item, Revision
    from mendel_forge.forging.validate import validation_items

    key = "questions:output_type:bam"
    state = Adaptation(items={key: Item(key=key, piece="questions", status=status,
        revisions=(Revision(n=1, move="answer", actor="person",
                            value={"choice": "alignment.custom", "new": True}),))})
    assert (key in validation_items(state)) is (status == "approved")


def test_explicit_port_state_fields_require_the_same_permission_as_signatures(stack, star_items):
    items = {**star_items, "contract:output:bam": {**star_items["contract:output:bam"],
        "type_id": "alignment.bam", "state": ["reviewed"]}}
    assert "MF0507" in _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF)))
    items["questions:output_type:bam"] = {"choice": "alignment.bam::reviewed", "new": True}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


def test_input_alternatives_use_the_same_approved_new_type_permission(stack, star_items):
    items = {**star_items, "contract:input:reads": {"name": "reads", "position": 0,
        "accepts": [{"type_id": "fastq.reads"}, {"type_id": "alignment.custom"}]}}
    assert "MF0507" in _codes(check_items(items, known(stack), ModuleSpec.parse(STAR_NF)))
    items["questions:input_type:reads"] = {"choice": "alignment.custom", "new": True}
    assert check_items(items, known(stack), ModuleSpec.parse(STAR_NF)) == []


@pytest.mark.parametrize(("own", "expected"), [(False, {"assembly"}), (True, set())])
def test_pending_families_are_separate_from_type_and_role_names(stack, own, expected):
    from mendel_forge.forging.validate import pending_families_used

    items = {"vocabulary:type:assembly.graph": {"id": "assembly.graph", "states": []}}
    if own:
        items["vocabulary:family:assembly"] = {"id": "assembly", "description": "Assembly products"}
    seen = known(stack, pending=frozenset({"assembly"}), pending_families=frozenset({"assembly"}))
    assert pending_used(items, seen) == set()
    assert pending_families_used(items, seen) == expected


def _test_items(inputs: dict) -> dict:
    return {"contract:input:a": {"position": 0, "name": "a", "type_id": "fastq.reads"},
            "contract:input:b": {"position": 1, "name": "b", "type_id": "genome.fasta",
                                 "required": False},
            "contract:output:o": {"position": 0, "name": "o", "type_id": "qc.report"},
            "tests:test:t": {"inputs": inputs, "expect": [{"port": "o", "pattern": "*"}]}}


def test_a_test_may_leave_an_optional_input_out(stack):
    """#470: QUAST's no-reference test was told "nothing feeds input 'fasta'"."""
    from mendel_forge.forging.validate import _test_problems

    for inputs in ({"a": ["x"]}, {"a": ["x"], "b": []}):
        assert _test_problems(_test_items(inputs), known(stack)) == []
    says = [p.says for p in _test_problems(_test_items({"a": [], "b": ["y"]}), known(stack))]
    assert says == ["tests:test:t: nothing feeds input 'a'"]


def test_a_test_type_names_an_input_and_a_type_it_accepts(stack):
    """Task 7 review: `types` was checked only when the test ran, so a typo was ignored."""
    from mendel_forge.forging.validate import _test_problems

    items = _test_items({"a": ["x.bam"]})
    items["contract:input:a"] = {"position": 0, "name": "a",
                                 "accepts": [{"type_id": "fastq.reads"},
                                             {"type_id": "alignment.bam"}]}
    items["tests:test:t"]["types"] = {"a": "alignment.bam"}
    assert _test_problems(items, known(stack)) == []
    items["tests:test:t"]["types"] = {"a": "alignment.cram", "nope": "fastq.reads"}
    says = sorted(p.says for p in _test_problems(items, known(stack)))
    assert says == ["tests:test:t: input 'a' does not accept 'alignment.cram'",
                    "tests:test:t: types names 'nope', not an input of this contract"]


# ── measurers (#487) ─────────────────────────────────────────────────────────────────────────

FAIDX_NF = REGISTRY / "tools/nf-core/samtools/faidx/module/main.nf"


@pytest.fixture(scope="module")
def faidx_items():
    from support.forge_measurer import KEY, measurer
    data = yaml.safe_load((REGISTRY / "tools/nf-core/samtools/faidx/contract.yml").read_text())
    data.pop("declares")
    test = {"inputs": {"fasta": ["genomics/genome.fasta"]},
            "expect": [{"port": p.name, "pattern": "*"} for p in ModuleContract(**data).produces]}
    return {**items_of(ModuleContract(**data)), "tests:test:small": test, KEY: measurer()}


def _measurer_says(stack, items) -> list[str]:
    """Checked against the registry as it was before `genome_length_fai` existed: the fixture
    drafts the registry's own piece."""
    seen = known(stack)
    seen = replace(seen, measurers=seen.measurers - {"genome_length_fai"})
    return [p.says for p in check_items(items, seen, ModuleSpec.parse(FAIDX_NF))]


def test_a_good_measurer_has_no_problems(stack, faidx_items):
    assert _measurer_says(stack, faidx_items) == []


@pytest.mark.parametrize("change, says", [
    ({"measures": "nothing_here"}, "measures 'nothing_here', which is not a measurement"),
    ({"output": "nope"}, "reads output 'nope', which this contract does not produce"),
    ({"code": "import os\ndef parse(stream, decided):\n    return None\n"}, "MD0027"),
    ({"code": "def measure(stream):\n    return None\n"}, "defines no parse(stream, decided)"),
    ({"tests": "import x\n"}, "its tests define no test_ function"),
])
def test_a_wrong_measurer_says_why(stack, faidx_items, change, says):
    from support.forge_measurer import KEY
    items = {**faidx_items, KEY: {**faidx_items[KEY], **change}}
    found = _measurer_says(stack, items)
    assert len(found) == 1 and says in found[0], found


def test_a_measurer_no_test_proves_is_refused(stack, faidx_items):
    from support.forge_measurer import KEY
    # faidx has one output, so the only way no test expects it is no test at all.
    items = {k: v for k, v in faidx_items.items() if k != "tests:test:small"}
    found = _measurer_says(stack, items)
    assert any("no test expects output 'fai'" in f for f in found), found
    assert KEY in found[0]


def test_a_measurer_id_must_be_a_python_name(stack, faidx_items):
    from support.forge_measurer import KEY
    items = {k: v for k, v in faidx_items.items() if k != KEY}
    items["measurers:measurer:n50-quast"] = faidx_items[KEY]
    assert any("not a Python name" in f for f in _measurer_says(stack, items))


def test_a_drafted_measurement_counts_and_its_id_matches_its_key(stack, faidx_items):
    from support.forge_measurer import KEY
    value = {"id": "n50", "kind": "integer", "description": "N50", "cite": "QUAST"}
    items = {**faidx_items, KEY: {**faidx_items[KEY], "measures": "n50"},
             "measurers:measurement:n50": value}
    assert _measurer_says(stack, items) == []
    items["measurers:measurement:n50"] = {**value, "id": "n51"}
    assert any("measurement ID must match its item key" in f
               for f in _measurer_says(stack, items))


def test_assembly_finds_a_measurer_no_test_proves_any_more(faidx_items):
    """#487 review I1: removing a test is not validated, so assembly asks again."""
    from mendel_forge.forging.validate import unproven
    from support.forge_measurer import KEY
    assert unproven(faidx_items) == []
    items = {k: v for k, v in faidx_items.items() if not k.startswith("tests:")}
    (problem,) = unproven(items)
    assert problem.code == "MF0507" and KEY in problem.says and "'fai'" in problem.says


def test_two_measurers_of_one_measurement_are_refused(stack, faidx_items):
    """#487 review I2: a run keeps one fact per measurement and sample, so one parser's value
    would stand for the other's failure."""
    from support.forge_measurer import KEY
    items = {**faidx_items, "measurers:measurer:genome_length_again": faidx_items[KEY]}
    found = _measurer_says(stack, items)
    assert any("genome_length_again" in f and "genome_length_fai" in f
               and "also measures 'genome_length'" in f for f in found), found


# ── deferred minors (issue 489) ───────────────────────────────────────────────────────────


def test_one_measurement_drafted_in_two_steps_is_refused_where_it_is_drafted(stack, faidx_items):
    value = {"id": "n50", "kind": "integer", "description": "N50", "cite": "QUAST"}
    items = {**faidx_items, "vocabulary:measurement:n50": value,
             "measurers:measurement:n50": value}
    assert any("measurers:measurement:n50" in f and "vocabulary:measurement:n50" in f
               for f in _measurer_says(stack, items))


@pytest.mark.parametrize("name", ["class", "re", "gzip", "io"])
def test_a_measurer_id_may_not_be_a_keyword_or_a_module_name(stack, faidx_items, name):
    from support.forge_measurer import KEY
    items = {k: v for k, v in faidx_items.items() if k != KEY}
    items[f"measurers:measurer:{name}"] = faidx_items[KEY]
    assert any(f"{name!r} is a Python keyword or module name" in f
               for f in _measurer_says(stack, items))


def test_an_annotated_parse_is_a_parse(stack, faidx_items):
    from support.forge_measurer import KEY
    code = faidx_items[KEY]["code"].replace("def parse(stream, decided):",
                                            "def parse(stream: object, decided: dict) -> object:")
    assert "def parse(stream: object" in code
    items = {**faidx_items, KEY: {**faidx_items[KEY], "code": code}}
    assert _measurer_says(stack, items) == []


def test_a_measurer_the_registry_has_is_not_drafted_again(stack, faidx_items):
    from support.forge_measurer import KEY
    found = [p.says for p in check_items(faidx_items, known(stack), ModuleSpec.parse(FAIDX_NF))]
    assert any(KEY in f and "the registry already has measurer 'genome_length_fai'" in f
               for f in found), found
