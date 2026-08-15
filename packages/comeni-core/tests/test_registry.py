import pathlib

import pytest
from comeni_core.declared.layered import DeclaredKind
from comeni_core.declared.registry import Registry, module_key
from comeni_core.declared.vocabulary import Vocabulary

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

SORT = """
id: nf-core/samtools/sort@1.21.0
nf_process: SAMTOOLS_SORT
nf_include: modules/nf-core/samtools/sort/main
consumes: [{name: bam, type_id: alignment.bam}]
produces: [{name: bam, type_id: alignment.bam, state: [coordinate_sorted]}]
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-02"}
"""

# **Sorts *after* `sort` by id and *before* it by priority**, so the two orderings
# disagree. It was `fastsort`, which is higher priority *and* alphabetically first — so
# `sorted(key=id)` and `sorted(key=(-priority, id))` produced the same list and the test
# below passed against both. Reverting `producers_of` to id-only ordering failed nothing in
# the entire suite. A37, found by Part I's sweep.
PREFERRED_SORT = SORT.replace(
    "nf-core/samtools/sort@1.21.0", "nf-core/samtools/zippysort@1.21.0"
).replace("priority: 0", "priority: 10")

# same module key, newer version — the lab pinning a different build
NEWER_SORT = SORT.replace("@1.21.0", "@1.22.0").replace("SAMTOOLS_SORT", "SAMTOOLS_SORT_NEW")


def _layer(root, name, files):
    """A layer root holding a `contracts/` directory. `Registry.load` takes layer roots."""
    d = root / name / "contracts"
    d.mkdir(parents=True)
    for filename, body in files.items():
        (d / filename).write_text(_declared(d / filename, body))
    return root / name


@pytest.fixture
def vocab(tmp_path):
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text(
        _declared(vocab_dir / "alignment.bam.yml", "states: [coordinate_sorted]\n")
    )
    return Vocabulary.load(tmp_path)


@pytest.fixture
def base(tmp_path):
    return _layer(tmp_path, "base", {"sort.yml": SORT, "fastsort.yml": PREFERRED_SORT})


@pytest.fixture
def registry(base, vocab):
    return Registry.load(base, vocab)


def test_module_key_strips_the_version():
    assert module_key("nf-core/samtools/sort@1.21.0") == "nf-core/samtools/sort"


def test_get_returns_contract_by_id(registry):
    assert registry.get("nf-core/samtools/sort@1.21.0").nf_process == "SAMTOOLS_SORT"


def test_producers_of_matches_required_states(registry):
    found = registry.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    assert len(found) == 2


def test_producers_of_returns_nothing_for_unproduced_state(registry):
    assert registry.producers_of("alignment.bam", frozenset({"name_sorted"})) == []


def test_producers_are_sorted_by_priority_then_id(registry):
    """Priority first, id second — and the fixture must be able to tell them apart.

    `zippysort` outranks `sort` on priority and loses to it on id, so this list is wrong
    under either half of the key alone. That is the whole content of the test: the previous
    fixture agreed on both orderings, so it asserted nothing.
    """
    found = registry.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    assert [c.id for c in found] == [
        "nf-core/samtools/zippysort@1.21.0",
        "nf-core/samtools/sort@1.21.0",
    ]


def test_get_raises_on_unknown_id(registry):
    with pytest.raises(KeyError):
        registry.get("nf-core/nope@1.0.0")


def test_a_single_path_is_the_one_layer_case(base, vocab):
    assert Registry.load(base, vocab).contracts == Registry.load([base], vocab).contracts


def test_overlay_shadows_the_same_module_key_at_any_version(tmp_path, base, vocab):
    overlay = _layer(tmp_path, "lab", {"sort.yml": NEWER_SORT})
    reg = Registry.load([base, overlay], vocab)

    # the base's @1.21.0 is gone, displaced by the overlay's @1.22.0
    assert reg.get("nf-core/samtools/sort@1.22.0").nf_process == "SAMTOOLS_SORT_NEW"
    with pytest.raises(KeyError):
        reg.get("nf-core/samtools/sort@1.21.0")

    # and it did not tie: exactly one sort candidate survives, plus zippysort — which
    # outranks it on priority, so it comes first.
    found = reg.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    assert [c.id for c in found] == [
        "nf-core/samtools/zippysort@1.21.0",
        "nf-core/samtools/sort@1.22.0",
    ]


def test_shadowing_is_recorded_as_a_displacement(tmp_path, base, vocab):
    overlay = _layer(tmp_path, "lab", {"sort.yml": NEWER_SORT})
    reg = Registry.load([base, overlay], vocab)

    assert len(reg.displaced) == 1
    record = reg.displaced[0]
    assert record.kind is DeclaredKind.CONTRACTS
    assert record.key == "nf-core/samtools/sort"
    assert record.winning_key == "nf-core/samtools/sort@1.22.0"
    assert record.displaced_keys == ["nf-core/samtools/sort@1.21.0"]


def test_a_displacement_names_the_contract_routing_prefers(tmp_path, base, vocab):
    """A layer may hold two versions of one module. The record must not name a loser."""
    overlay = _layer(
        tmp_path,
        "lab",
        {
            "sort.yml": NEWER_SORT,
            "sort-old.yml": SORT.replace("priority: 0", "priority: 5"),
        },
    )
    reg = Registry.load([base, overlay], vocab)

    # @1.21.0 at priority 5 outranks @1.22.0 at priority 0 under (-priority, id) — so it is
    # the winner named, even though it sorts later lexically.
    assert reg.displaced[0].winning_key == "nf-core/samtools/sort@1.21.0"
    produced = reg.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    sorts = [c.id for c in produced if module_key(c.id) == "nf-core/samtools/sort"]
    assert sorts[0] == "nf-core/samtools/sort@1.21.0"


def test_a_different_module_key_does_not_shadow(tmp_path, base, vocab):
    overlay = _layer(
        tmp_path, "lab", {"mine.yml": SORT.replace("nf-core/samtools/sort", "lab/mysort")}
    )
    reg = Registry.load([base, overlay], vocab)

    assert reg.displaced == []
    # it competes normally — and ties with the base at equal priority, which invariant 8
    # leaves for the router to demote to tier 4
    found = reg.producers_of("alignment.bam", frozenset({"coordinate_sorted"}))
    assert len(found) == 3


def test_unshadowed_stack_is_the_union(tmp_path, base, vocab):
    overlay = _layer(
        tmp_path, "lab", {"mine.yml": SORT.replace("nf-core/samtools/sort", "lab/mysort")}
    )
    assert len(Registry.load([base, overlay], vocab).contracts) == 3
