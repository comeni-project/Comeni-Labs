"""The commands a person or a job performs (spec §11.3): typed, plain, and naming their arrows."""

import dataclasses
import types
import typing

import pytest
from mendel_authoring import commands as c
from mendel_authoring.protocol import PROTOCOL
from mendel_authoring.types import Command

PLAIN = {str, int, float, bool, type(None), dict, list, tuple, bytes, object}


def _plain(hint) -> bool:
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        return all(_plain(a) for a in typing.get_args(hint))
    return (origin or hint) in PLAIN


def test_every_command_is_frozen_and_holds_plain_values_only():
    assert c.COMMANDS, "no command: the loop would hold vacuously"
    for kind in c.COMMANDS:
        assert dataclasses.is_dataclass(kind) and kind.__dataclass_params__.frozen, kind
        hints = typing.get_type_hints(kind)
        for f in dataclasses.fields(kind):
            assert _plain(hints[f.name]), f"{kind.__name__}.{f.name}: {hints[f.name]}"


def test_every_arrow_a_built_edge_names_is_taken_by_some_command():
    drawn = {e.on for e in PROTOCOL.edges if e.built} & {m.value for m in Command}
    assert drawn, "no command arrow drawn: the comparison would hold vacuously"
    taken = {a.value for kind in c.COMMANDS for a in kind.takes}
    assert drawn <= taken, sorted(drawn - taken)


def test_a_command_takes_only_arrows_the_core_names():
    for kind in c.COMMANDS:
        assert all(isinstance(a, Command) for a in kind.takes), kind


def test_a_command_cannot_be_changed_once_made():
    said = c.Say("s1", "hello")
    with pytest.raises(dataclasses.FrozenInstanceError):
        said.text = "other"  # type: ignore[misc]
