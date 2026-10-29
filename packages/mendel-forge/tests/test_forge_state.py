"""A module's state against the registry, computed on read (forge part 1 spec, §3)."""

from mendel_forge.state import BEST_ORDER, Held, State, gone, held, state_of
from mendel_resolver import layers
from support.paths import REGISTRY

HELD = {"star/align": Held(module_id="nf-core/star/align",
                           contract_id="nf-core/star/align@2.7.11b", version="2.7.11b",
                           upstream_path="star/align")}


def test_same_version_is_imported():
    assert state_of("star/align", "2.7.11b", HELD) is State.IMPORTED


def test_different_version_is_update_available():
    """`2.7.11a` sorts before `2.7.11b`: "differs", not "is newer", decides it."""
    assert state_of("star/align", "2.7.11a", HELD) is State.UPDATE


def test_absent_is_not_imported():
    assert state_of("fastqc", "0.12.1", HELD) is State.NOT_IMPORTED


def test_unknown_version_of_a_held_module_is_unknown():
    assert state_of("star/align", None, HELD) is State.UNKNOWN


def test_unknown_version_of_an_absent_module_is_not_imported():
    assert state_of("fastqc", None, HELD) is State.NOT_IMPORTED


def test_a_held_path_missing_upstream_is_gone():
    assert gone(HELD, {"fastqc"}) == [HELD["star/align"]]
    assert gone(HELD, {"star/align"}) == []


def test_best_order_puts_what_the_registry_holds_first():
    assert BEST_ORDER == (State.UPDATE, State.IMPORTED, State.UNKNOWN, State.GONE,
                          State.NOT_IMPORTED)


def test_the_shipped_registry_holds_star_align():
    shipped = held(layers.load(REGISTRY))
    assert shipped, "the shipped registry holds modules"
    assert shipped["star/align"].version == "2.7.11b"
    assert shipped["star/align"].contract_id == "nf-core/star/align@2.7.11b"
