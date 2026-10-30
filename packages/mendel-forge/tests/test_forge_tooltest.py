"""A tool's test as data: refused before it is stored, carried in the draft, read by the loader."""

import shutil
from types import SimpleNamespace

import pytest
import yaml
from comeni_core.declared.contract import ModuleContract, Provenance
from comeni_core.declared.tooltest import TestDraft
from comeni_flow.interpret import Refused
from mendel_compiler import registry_lint
from mendel_forge.forging.assemble import ModuleOrigin, prove, write_layer
from mendel_forge.forging.model import Actor, Adaptation, Command, Move, Piece, Status
from mendel_forge.forging.rules import apply, next_piece
from mendel_forge.forging.validate import Known, check_items
from mendel_forge.forging.values import items_of
from mendel_resolver import layers
from pydantic import ValidationError
from support.paths import REGISTRY

STAR = REGISTRY / "tools" / "nf-core" / "star" / "align"
GOOD = {"inputs": {"reads": ["genomics/homo_sapiens/x_1.fastq.gz"]},
        "expect": [{"port": "bam", "pattern": "*.bam"}]}


MAIN = SimpleNamespace(process="X", inputs=[SimpleNamespace(names=("reads",))],
                       emits=("bam", "log"))


def _do(state, move, actor, item, **kw):
    return apply(state, Command(move=move, actor=actor, item=item, by="r", **kw))


def _all_but_tests() -> Adaptation:
    state = _do(Adaptation(), Move.ANSWER, Actor.PERSON, "questions:role", value={"choice": "x"})
    state = _do(state, Move.WRITE, Actor.PERSON, "contract:process", value={})
    for key in ("parameters:none", "vocabulary:none", "rules:none"):
        state = _do(state, Move.WRITE, Actor.PERSON, key, value={"because": "nothing"})
    return state


@pytest.mark.parametrize("path", ["../x", "a/../b", "https://a/b", "a b", "/x", "a//b", ""])
def test_a_path_outside_test_datasets_is_refused(path):
    with pytest.raises(ValidationError):
        TestDraft(inputs={"reads": [path]}, expect=GOOD["expect"])


def test_a_model_cannot_supply_the_data_commit():
    with pytest.raises(ValidationError):
        TestDraft(**GOOD, data_commit="abc")


def test_tests_come_after_rules_and_one_is_required():
    state = _all_but_tests()
    assert next_piece(state) is Piece.TESTS
    with pytest.raises(Refused, match="MF0506"):
        _do(state, Move.WRITE, Actor.PERSON, "tests:none", value={"because": "no"})
    state = _do(state, Move.WRITE, Actor.PERSON, "tests:test:one", value=GOOD)
    assert next_piece(state) is None


def test_a_removed_test_leaves_the_piece_unfinished():
    state = _do(_all_but_tests(), Move.WRITE, Actor.PERSON, "tests:test:one", value=GOOD)
    state = _do(state, Move.REMOVE, Actor.PERSON, "tests:test:one", expected=1)
    assert next_piece(state) is Piece.TESTS


def test_a_changed_parameter_reopens_tests():
    state = _do(_all_but_tests(), Move.WRITE, Actor.PERSON, "tests:test:one", value=GOOD)
    item = state.items["parameters:none"]
    state = _do(state, Move.CHANGE, Actor.PERSON, "parameters:none", expected=item.current.n,
                value={"because": "still nothing"})
    assert state.items["tests:test:one"].status is Status.REOPENED


def _checked(test: dict) -> list[str]:
    items = {"contract:input:reads": {"position": 0, "name": "reads", "type_id": "t"},
             "contract:output:bam": {"position": 0, "name": "bam", "type_id": "t"},
             "contract:output:log": {"position": 1, "name": "log", "type_id": "t"},
             "parameters:param:depth": {"position": 0, "name": "depth", "via": "ext",
                                        "key": "args"},
             "tests:test:one": test}
    seen = Known(types=frozenset({"t"}), roles=frozenset(), measurements=frozenset(),
                 contracts=frozenset({"nf-core/x@1"}))
    return [p.says for p in check_items(items, seen, MAIN)]


def _with(**changes) -> dict:
    return {"inputs": {"reads": ["a/b.fq"]}, "expect": [{"port": "bam", "pattern": "*.bam"}],
            "unchecked": {"log": "named after the sample"}, **changes}


def test_a_complete_test_is_accepted():
    assert not [s for s in _checked(_with()) if "tests:test" in s]


@pytest.mark.parametrize("changes,says", [
    ({"inputs": {"nope": ["a/b.fq"], "reads": ["a/b.fq"]}}, "nope"),
    ({"inputs": {}}, "reads"),
    ({"params": {"nope": 1}}, "nope"),
    ({"expect": [{"port": "nope", "pattern": "*"}]}, "nope"),
    ({"unchecked": {}}, "log"),
    ({"setup": [{"tool": "nf-core/nope@1", "feeds": {"out": "reads"}}], "inputs": {}}, "nope"),
    ({"setup": [{"tool": "nf-core/x@1", "feeds": {"out": "nope"}}]}, "nope"),
])
def test_a_test_that_does_not_fit_the_contract_is_MF0507(changes, says):
    problems = [s for s in _checked(_with(**changes)) if "tests:test:one" in s]
    assert problems and any(says in s for s in problems)


def test_a_port_fed_by_a_setup_step_needs_no_file():
    test = _with(inputs={}, setup=[{"tool": "nf-core/x@1", "feeds": {"out": "reads"}}])
    assert not [s for s in _checked(test) if "tests:test" in s]


def _star_values() -> dict:
    data = yaml.safe_load((STAR / "contract.yml").read_text())
    data.pop("declares")
    return items_of(ModuleContract(**data))


PROVENANCE = Provenance(source="forge", drafted_by="ai", approved_by="rafael",
                        approved_at="2026-10-30")


def _origin() -> ModuleOrigin:
    module = yaml.safe_load((STAR / "module.yml").read_text())
    return ModuleOrigin(source_dir=STAR / "module", module_id="nf-core/star/align",
                        repo=module["upstream"]["repo"], sha=module["upstream"]["sha"],
                        path=module["upstream"]["path"], licence="MIT", data_commit="abc123")


TEST_VALUE = {"inputs": {"reads": ["genomics/x.fq"]}, "expect": [{"port": "bam", "pattern": "*"}]}


def test_a_draft_layer_carries_its_tests(tmp_path):
    values = {**_star_values(), "tests:test:one": TEST_VALUE}
    id_ = "nf-core/star/align@2.7.11b"
    write_layer(values, id_, PROVENANCE, _origin(), base=REGISTRY, out=tmp_path / "d")
    written = yaml.safe_load((tmp_path / "d/tools/nf-core/star/align/tests/one.yml").read_text())
    assert written["declares"] == "test" and written["data_commit"] == "abc123"
    assert written["contract"] == id_ and written["name"] == "one"
    assert prove(REGISTRY, [], tmp_path / "d").loaded
    stack = layers.load([REGISTRY, tmp_path / "d"])
    assert [t.name for t in stack.tests[id_]] == ["one"]


def test_tests_without_a_known_commit_do_not_assemble(tmp_path):
    origin = _origin().model_copy(update={"data_commit": ""})
    with pytest.raises(ValueError, match="MF0511"):
        write_layer({**_star_values(), "tests:test:one": TEST_VALUE}, "nf-core/star/align@2.7.11b",
                    PROVENANCE, origin, base=REGISTRY, out=tmp_path / "d")


def _layer_with(tmp_path, text: str):
    layer = tmp_path / "layer"
    (layer / "tools/nf-core/star/align/tests").mkdir(parents=True)
    (layer / "registry.yml").write_text("name: x\nrequires_format: 2\n")
    (layer / "tools/nf-core/star/align/tests/one.yml").write_text(text)
    return layer


def test_a_malformed_test_refuses_to_load(tmp_path):
    layer = _layer_with(tmp_path, "declares: test\nname: one\n")
    with pytest.raises(ValueError):
        layers.load([REGISTRY, layer])


def test_a_test_of_a_contract_nobody_declares_refuses_to_load(tmp_path):
    layer = _layer_with(tmp_path, "declares: test\nname: one\ncontract: nf-core/no@1\n"
                        "data_commit: a\ninputs: {}\nexpect: [{port: a, pattern: '*'}]\n")
    with pytest.raises(ValueError, match="MD0026"):
        layers.load([REGISTRY, layer])


def test_lint_accepts_a_tests_folder(tmp_path):
    layer = tmp_path / "copy"
    shutil.copytree(REGISTRY, layer, ignore=shutil.ignore_patterns(".git"))
    tests = layer / "tools/nf-core/star/align/tests"
    tests.mkdir()
    (tests / "one.yml").write_text("declares: test\nname: one\n"
                                   "contract: nf-core/star/align@2.7.11b\ndata_commit: a\n"
                                   "inputs: {}\nexpect: [{port: bam, pattern: '*.bam'}]\n")
    assert [d for d in registry_lint.lint(layer)] == []
