"""`stack()` — the one mechanism all four declared-data kinds use.

Tested against a synthetic kind with no dependency on the registry, so these tests fail for
one reason only. The four real kinds arrive in later tasks and each is a `Kind` plus a thin
constructor; if one of them behaves differently from another, that is a bug in the kind
rather than in stacking, which is the property this module exists to buy.
"""

import pathlib

import pytest
import yaml
from comeni_core.declared.layered import DeclaredKind, Displacement, Kind, Layer, Policy, stack

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


def _write(root, layer, subdir, name, data):
    directory = root / layer / subdir
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(_declared(directory / name, yaml.safe_dump(data)))


def _parse(path):
    data = yaml.safe_load(path.read_text()) or {}
    return [{"id": path.stem, **data}]


def _kind(**over):
    args = {
        "which": DeclaredKind.MEASUREMENTS,
        "parse": _parse,
        "key": lambda e: e["id"],
    }
    return Kind(**{**args, **over})


def _layers(root, *names):
    return [Layer(path=root / n, name=n, index=i) for i, n in enumerate(names)]


def test_a_higher_layer_wins_and_the_displacement_is_recorded(tmp_path):
    _write(tmp_path, "base", "measurements", "shared.yml", {"value": "base"})
    _write(tmp_path, "base", "measurements", "only_base.yml", {"value": "b"})
    _write(tmp_path, "lab", "measurements", "shared.yml", {"value": "lab"})
    _write(tmp_path, "lab", "measurements", "only_lab.yml", {"value": "l"})

    result = stack(_layers(tmp_path, "base", "lab"), _kind())

    assert result.entries["shared"]["value"] == "lab"
    assert set(result.entries) == {"shared", "only_base", "only_lab"}
    assert result.origin == {"shared": 1, "only_base": 0, "only_lab": 1}
    assert [(d.key, d.winning_layer, d.displaced_layer) for d in result.displaced] == [
        ("shared", "lab", "base")
    ]


def test_origin_is_an_index_so_two_layers_may_share_a_name(tmp_path):
    """A25. Layer identity is the index; the name is a label.

    The lockfile's own docstring says this collision is not exotic: the public layer is named
    `registry`, so a lab stacking it over their own `registry/` hits it on day one. Keying
    displacement on a name suppressed the record entirely.
    """
    _write(tmp_path, "one", "measurements", "shared.yml", {"value": "lower"})
    _write(tmp_path, "two", "measurements", "shared.yml", {"value": "upper"})

    layers = [
        Layer(path=tmp_path / "one", name="registry", index=0),
        Layer(path=tmp_path / "two", name="registry", index=1),
    ]
    result = stack(layers, _kind())

    assert result.entries["shared"]["value"] == "upper"
    assert result.origin["shared"] == 1
    assert len(result.displaced) == 1, "a same-name displacement must still be recorded"


def test_the_lowest_displaced_layer_is_named_across_a_deep_stack(tmp_path):
    """Three layers, one key. The reader is most surprised by losing the base."""
    for name, value in (("a", "1"), ("b", "2"), ("c", "3")):
        _write(tmp_path, name, "measurements", "shared.yml", {"value": value})

    result = stack(_layers(tmp_path, "a", "b", "c"), _kind())

    assert result.entries["shared"]["value"] == "3"
    assert [d.displaced_layer for d in result.displaced] == ["a", "b"]


def test_a_merge_policy_extends_instead_of_replacing(tmp_path):
    _write(tmp_path, "base", "measurements", "m.yml", {"values": ["a", "b"]})
    _write(tmp_path, "lab", "measurements", "m.yml", {"values": ["c"]})

    def merge(old, new):
        return {**old, "values": [*old["values"], *new["values"]]}

    result = stack(
        _layers(tmp_path, "base", "lab"), _kind(policy=Policy.MERGE, merge=merge)
    )

    assert result.entries["m"]["values"] == ["a", "b", "c"]
    assert len(result.displaced) == 1, "merging is still a displacement worth reporting"


def test_merge_without_a_merge_function_is_refused():
    with pytest.raises(ValueError, match="merge function"):
        _kind(policy=Policy.MERGE)


def test_delete_group_removes_every_lower_entry_sharing_a_group(tmp_path):
    """Contract shadowing, tested before any contract uses it.

    Storage key is the full id; group key is the id minus its version. A higher layer
    supplying `@2.0` displaces `@1.0` *and* `@1.1`, because the module key is the same.
    """
    _write(tmp_path, "base", "measurements", "star@1.0.yml", {"p": 0})
    _write(tmp_path, "base", "measurements", "star@1.1.yml", {"p": 0})
    _write(tmp_path, "base", "measurements", "hisat@1.0.yml", {"p": 0})
    _write(tmp_path, "lab", "measurements", "star@2.0.yml", {"p": 9})

    result = stack(
        _layers(tmp_path, "base", "lab"),
        _kind(group=lambda e: e["id"].split("@")[0], policy=Policy.DELETE_GROUP),
    )

    assert set(result.entries) == {"star@2.0", "hisat@1.0"}, "both star versions are gone"
    assert len(result.displaced) == 1
    displaced = result.displaced[0]
    assert displaced.key == "star"
    assert displaced.displaced_keys == ["star@1.0", "star@1.1"]
    assert displaced.winning_key == "star@2.0"


def test_delete_group_names_the_version_routing_prefers(tmp_path):
    """A layer may hold two versions of one module, so the record must name the winner.

    `ShadowRecord.winning_id` carried this, and a record that names only the group can
    contradict the build it describes.
    """
    _write(tmp_path, "base", "measurements", "star@1.0.yml", {"p": 0})
    _write(tmp_path, "lab", "measurements", "star@2.0.yml", {"p": 1})
    _write(tmp_path, "lab", "measurements", "star@3.0.yml", {"p": 9})

    result = stack(
        _layers(tmp_path, "base", "lab"),
        _kind(
            group=lambda e: e["id"].split("@")[0],
            policy=Policy.DELETE_GROUP,
            prefer=lambda entries: max(entries, key=lambda e: e["p"]),
        ),
    )

    assert result.displaced[0].winning_key == "star@3.0"


def test_delete_group_names_the_lowest_layer_it_displaced(tmp_path):
    """Three layers, one group, chained displacement under DELETE_GROUP.

    Added because a revert of `min(origin[k] for k in victims)` fired nothing. Chasing that
    found the deep-stack test above uses REPLACE — a different branch — and then that the
    `min` could never differ from `max` at all, because an arriving layer deletes a whole
    group before adding to it. The reduction became an assertion.
    """
    _write(tmp_path, "a", "measurements", "star@1.0.yml", {"p": 0})
    _write(tmp_path, "b", "measurements", "star@2.0.yml", {"p": 0})
    _write(tmp_path, "c", "measurements", "star@3.0.yml", {"p": 0})

    result = stack(
        _layers(tmp_path, "a", "b", "c"),
        _kind(group=lambda e: e["id"].split("@")[0], policy=Policy.DELETE_GROUP),
    )

    # Layer b displaces a; layer c then displaces b's survivor. The second record has two
    # victims to choose between only if b left one behind — it did not, so the discriminating
    # case is the first record naming `a` and the second naming `b`.
    assert [d.displaced_layer for d in result.displaced] == ["a", "b"]
    assert set(result.entries) == {"star@3.0"}


def test_delete_group_attributes_each_group_to_the_layer_that_supplied_it(tmp_path):
    """One layer displacing two groups that arrived from two different layers.

    This is as close as `DELETE_GROUP` gets to a multi-origin case, and it is why the
    implementation asserts a group's victims share one origin rather than reducing over them:
    reverting `min` to `max` changed no test, because the set is always a singleton.
    """
    _write(tmp_path, "a", "measurements", "star@1.0.yml", {"p": 0})
    _write(tmp_path, "b", "measurements", "hisat@1.0.yml", {"p": 0})
    _write(tmp_path, "c", "measurements", "star@9.0.yml", {"p": 0})
    _write(tmp_path, "c", "measurements", "hisat@9.0.yml", {"p": 0})

    result = stack(
        _layers(tmp_path, "a", "b", "c"),
        _kind(group=lambda e: e["id"].split("@")[0], policy=Policy.DELETE_GROUP),
    )

    by_key = {d.key: d.displaced_layer for d in result.displaced}
    assert by_key == {"star": "a", "hisat": "b"}


def test_files_are_found_recursively_and_yaml_counts(tmp_path):
    """A26. Three loaders globbed one level and all four matched `*.yml` only."""
    _write(tmp_path, "base", "measurements", "flat.yml", {"v": 1})
    _write(tmp_path, "base", "measurements/nested", "deep.yml", {"v": 2})
    _write(tmp_path, "base", "measurements", "other.yaml", {"v": 3})

    result = stack(_layers(tmp_path, "base"), _kind())

    assert set(result.entries) == {"flat", "deep", "other"}
    assert len(result.claimed) == 3, "every file read is recorded, so a residue is detectable"


def test_a_missing_subdirectory_is_ordinary(tmp_path):
    _write(tmp_path, "base", "measurements", "m.yml", {"v": 1})
    (tmp_path / "lab").mkdir()

    result = stack(_layers(tmp_path, "base", "lab"), _kind())

    assert set(result.entries) == {"m"}
    assert result.displaced == []


def test_one_key_declared_twice_in_one_layer_is_refused(tmp_path):
    _write(tmp_path, "base", "measurements", "m.yml", {"v": 1})
    _write(tmp_path, "base", "measurements/nested", "m.yml", {"v": 2})

    with pytest.raises(ValueError, match="in measurements/nested/m.yml and in measurements/m.yml"):
        stack(_layers(tmp_path, "base"), _kind())


def test_a_single_layer_displaces_nothing(tmp_path):
    """The regression that matters most: a lab with no overlay sees no change."""
    _write(tmp_path, "base", "measurements", "a.yml", {"v": 1})
    _write(tmp_path, "base", "measurements", "b.yml", {"v": 2})

    result = stack(_layers(tmp_path, "base"), _kind())

    assert result.displaced == []
    assert set(result.origin.values()) == {0}


def test_a_displacement_satisfies_the_egress_leaf_rule():
    """Root A and root B must not fight: `Displacement` reaches the IR and a bundle.

    Runs part A's actual rule rather than asserting something about it. The first version of
    this test checked `assert [hints[name]]`, which is a non-empty list and therefore always
    true — an inert assertion in the test file for the mechanism whose whole point is that
    displacement cannot go unrecorded. A14, caught by re-reading rather than by reverting.
    """
    import sys
    import typing

    sys.path.insert(0, str(pathlib.Path(__file__).parents[3] / "tests"))
    from test_egress import _leaf_problems

    hints = typing.get_type_hints(Displacement, include_extras=True)
    problems: list[str] = []
    for name in Displacement.model_fields:
        problems += _leaf_problems(hints[name], f"Displacement.{name}", {Displacement})
    assert problems == [], problems
