"""Closed state vocabularies. A type declares exactly the states it may carry."""

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, field_serializer

from comeni_core import yaml_strict
from comeni_core.declared.layered import (
    DeclaredKind,
    Displacement,
    Kind,
    Policy,
    Stacked,
    layers_of,
    stack,
)
from comeni_core.diagnostics import coded
from comeni_core.spell.marks import GroovyExpression, TypeId

if TYPE_CHECKING:  # `measurement` imports `profile`, which imports nothing from here
    from comeni_core.declared.measurement import MeasurementRegistry


class UnknownTypeError(KeyError):
    """Raised when a type id has no vocabulary file."""


class UnknownStateError(ValueError):
    """Raised when a state is not declared for its type.

    Carries the type and the state as fields, not only inside the message. A caller that
    knows something the raiser does not — `layers.load` knows an overlay replaced this very
    type's states — can then join the two facts, which is A35: the traceback named a base
    contract that had not changed rather than the overlay that removed the state.
    """

    def __init__(self, message: str, *, type_id: str | None = None, state: str | None = None):
        super().__init__(message)
        self.type_id = type_id
        self.state = state


class TypeDeclaration(BaseModel):
    """One vocabulary file: a type, its states, how it enters, and where an example is.

    `extra="forbid"` for A10's reason — a key that is ignored is a key that can be
    misspelled in silence. `add_states` was exactly that misspelling-shaped hole: the
    loader read `data.get("states", [])`, so a file declaring only `add_states` produced a
    type with **no** states at all and the failure surfaced three files away.
    """

    model_config = ConfigDict(extra="forbid")

    id: TypeId
    """The filename stem, validated. A vocabulary type id is whatever somebody named a
    file, and it is emitted as a channel name — root C, A34."""
    states: frozenset[str] = frozenset()
    entry_channel: GroovyExpression | None = None
    """Unbounded Groovy, emitted verbatim — the designed exception, marked as such."""
    test_data: str | list[str] | None = None


class TypeExtension(BaseModel):
    """An overlay adding states to a type a lower layer declared.

    The vocabulary half of `add_values`. One convention across kinds: **`states:` replaces
    the whole declaration, `add_states:` extends it.** Before this, a lab that wanted one
    extra state could only restate every state it knew about, and silently dropped the
    entry channel and test data while doing it.
    """

    model_config = ConfigDict(extra="forbid")

    id: TypeId
    add_states: list[str]


def _parse_type(path: Path) -> list[TypeDeclaration | TypeExtension]:
    """One vocabulary file — a type declaration, or an extension of one.

    **`declares:` is accepted and ignored, and `id:` wins over the filename.** Both are part of
    comeni-registry#1: a layer was one directory per kind because the directory was how the
    loader knew what a file was, and vocabularies took their identity from the filename on top
    of that — so a type could not be moved without being renamed.

    Ignored rather than checked *here* on purpose. Every declared model sets `extra="forbid"`,
    so without accepting `declares:` a migrated file would fail to load, and the registry could not
    be migrated one file at a time. The task that makes it required is the one that stops
    reading the directory.
    """
    data = yaml_strict.load(path) or {}
    data.pop("declares", None)
    type_id = data.pop("id", None)
    if not type_id:
        raise ValueError(
            coded(
                "MD0012",
                f"{path} is a vocabulary and declares no `id:`. The filename stopped\n"
                f"  being the identity when a file stopped having to live in a directory\n"
                f"  named for its kind.",
            )
        )
    added = data.pop("add_states", None)
    if added is not None:
        if data:
            raise ValueError(
                coded("MD0007", f"{path}: `add_states` extends a declaration and cannot carry "
                f"{', '.join(sorted(data))} as well. Declare the whole type to change those.")
            )
        return [TypeExtension(id=type_id, add_states=added)]
    return [TypeDeclaration(id=type_id, **data)]


def _merge_type(
    old: TypeDeclaration | TypeExtension, new: TypeDeclaration | TypeExtension
) -> TypeDeclaration | TypeExtension:
    if not isinstance(new, TypeExtension):
        # A whole declaration replaces a whole declaration. It used to replace `states`
        # unconditionally and `entry_channel` only when present, so one file was governed
        # by two policies and neither was written down. A35.
        return new
    if isinstance(old, TypeExtension):
        return TypeExtension(id=old.id, add_states=[*old.add_states, *new.add_states])
    return old.model_copy(update={"states": old.states | frozenset(new.add_states)})


class Vocabulary(BaseModel):
    types: dict[str, frozenset[str]]

    displaced: list[Displacement] = []
    """What a higher layer replaced or extended here. See `Registry.displaced`."""
    test_data: dict[str, str | list[str]] = {}
    """Where a small public example of this type lives, for the `test` profile.

    Declared per type for the same reason `entry_channel` is: the compiler has no built-in
    idea what a FASTQ is, and a type a laboratory invents has to be able to bring its own.

    Pin these to a commit, never a branch. A dataset that moves is one you cannot compare a
    result against next year, which is the entire point of having one.
    """

    entry_channels: dict[str, str] = {}
    """How a type enters a pipeline when nothing upstream produces it.

    Declared per type rather than hardcoded in the compiler, so a type the compiler
    has never seen — from a pegi3s image, an in-house process — can say how it
    arrives without a code change. Absent means the default in
    `mendel_compiler.emit`.
    """

    @field_serializer("types")
    def _sorted(self, types: dict[str, frozenset[str]]) -> dict[str, list[str]]:
        """Sorted states, and sorted keys.

        The frozensets here are nested inside a `dict` value rather than being fields of
        their own, so they had no serialiser while every other frozenset in the codebase
        did — and nothing had ever serialised a `Vocabulary`, so nothing noticed. The
        moment `digest_of` existed, the same vocabulary produced three different digests
        under three `PYTHONHASHSEED` values, which would have made every lockfile
        spuriously dirty while looking perfectly stable inside any one process.
        """
        return {type_id: sorted(types[type_id]) for type_id in sorted(types)}

    @staticmethod
    def kind() -> Kind[str, TypeDeclaration | TypeExtension]:
        """How vocabulary types are found, keyed and stacked. Everything else is `stack()`."""
        return Kind(
            DeclaredKind.VOCABULARIES,
            parse=_parse_type,
            key=lambda entry: entry.id,
            policy=Policy.MERGE,
            merge=_merge_type,
        )

    @classmethod
    def of(cls, stacked: Stacked[str, "TypeDeclaration | TypeExtension"]) -> "Vocabulary":
        """Build a vocabulary from a stacked result, refusing an extension of nothing."""
        types: dict[str, frozenset[str]] = {}
        test_data: dict[str, str | list[str]] = {}
        entry_channels: dict[str, str] = {}
        for type_id, entry in stacked.entries.items():
            if isinstance(entry, TypeExtension):
                raise ValueError(
                coded("MD0008", f"add_states for {type_id!r}, which no layer declares")
            )
            types[type_id] = entry.states
            if entry.entry_channel:
                entry_channels[type_id] = entry.entry_channel
            if entry.test_data:
                test_data[type_id] = entry.test_data
        return cls(
            types=types,
            entry_channels=entry_channels,
            test_data=test_data,
            displaced=list(stacked.displaced),
        )

    @classmethod
    def load(cls, layers: "Path | Sequence[Path]") -> "Vocabulary":
        """Load vocabulary types across a layer stack. **Layer roots, not `vocabularies/`.**

        A laboratory adding a state — or, once the rule-tables spec lands, a measurement —
        needs types to stack the way contracts already do. Only contracts stacked before
        the 2026-08-03 audit, so a lab could ship modules but not the vocabulary they
        depend on. Since A24 it stacks through the one mechanism, so a replacement is
        recorded rather than silent; callers wanting the records use `stack()` and `of()`,
        as `mendel_resolver.layers.load` does.
        """
        return cls.of(stack(layers_of(layers), cls.kind()))

    def with_measurements(self, registry: "MeasurementRegistry") -> "Vocabulary":
        """Derive a stateless `measurement.<id>` type per declaration.

        This is what makes profiling free: a measurement is a type a module produces, so
        "measure the read length" is an ordinary routing problem and the router needs no
        profiling code at all.

        Derived rather than declared twice: the measurement file already says what the
        measurement is, and a second vocabulary file saying it again is a thing to drift.
        Stateless because a measurement has a *value*, not a condition — `strandedness`'s
        three values are declared values, not states, and letting them be both would give
        routing two places to disagree.
        """
        types = dict(self.types)
        for measurement_id in registry.ids():
            types[f"measurement.{measurement_id}"] = frozenset()
        return Vocabulary(
            types=types,
            entry_channels=dict(self.entry_channels),
            test_data=dict(self.test_data),
            displaced=list(self.displaced),
        )

    def states_for(self, type_id: str) -> frozenset[str]:
        if type_id not in self.types:
            raise UnknownTypeError(type_id)
        return self.types[type_id]

    def validate(self, type_id: str, states: Iterable[str]) -> None:
        allowed = self.states_for(type_id)
        for state in states:
            if state not in allowed:
                raise UnknownStateError(
                    coded("MD0009", f"{state!r} is not a declared state for {type_id!r}; "
                    f"allowed: {sorted(allowed)}"),
                    type_id=type_id,
                    state=state,
                )
