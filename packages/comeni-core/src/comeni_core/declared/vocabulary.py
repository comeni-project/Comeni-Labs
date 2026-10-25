"""Declare data types, their allowed states, and their pipeline-entry metadata."""

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from comeni_core import yaml_strict
from comeni_core.artifact.param_refs import extract_param_refs
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
from comeni_core.spell.marks import GroovyExpression, NfIdentifier, TypeId

if TYPE_CHECKING:  # `measurement` imports `profile`, which imports nothing from here
    from comeni_core.declared.measurement import MeasurementRegistry


class UnknownTypeError(KeyError):
    """Raised when a type id has no vocabulary file."""


class UnknownStateError(ValueError):
    """Raised for an undeclared state, with the type and state available as fields."""

    def __init__(self, message: str, *, type_id: str | None = None, state: str | None = None):
        super().__init__(message)
        self.type_id = type_id
        self.state = state


class TypeDeclaration(BaseModel):
    """One data type, including its closed states and default pipeline-entry settings."""

    model_config = ConfigDict(extra="forbid")

    id: TypeId
    """Stable type identifier used by contracts and routing."""
    states: frozenset[str] = frozenset()
    sample_columns: int = 1
    """Number of input-table columns occupied by one sample of this type."""

    scope: str = "sample"
    """Default arrival scope: once per `run` or once per `sample`."""

    entry_channel: GroovyExpression | None = None
    """Groovy expression used when no upstream channel produces this type.

    The literal placeholder `params.{param}` is substituted during materialisation. Other Groovy
    braces are left untouched. Hard-coded `params.<name>` references are refused.
    """
    param: NfIdentifier | None = None
    """Default pipeline parameter name; absent values derive from the final ID segment."""
    test_data: str | list[str] | None = None
    name: str | None = Field(default=None, min_length=1, max_length=80)
    """Optional user-facing name; the type ID is shown when this is absent."""
    explain: str | None = Field(default=None, min_length=1, max_length=600)
    """Short user-facing explanation of the type and its usual source."""

    @model_validator(mode="after")
    def _an_entry_channel_names_no_param_of_its_own(self) -> "TypeDeclaration":
        """Refuse hard-coded parameter names while allowing `{param}` or no parameter."""
        if self.entry_channel is None:
            return self
        hardcoded = extract_param_refs(self.entry_channel.replace("params.{param}", ""))
        if hardcoded:
            raise ValueError(
                coded(
                    "MD0228",
                    f"type {self.id!r} names {', '.join('params.' + p for p in hardcoded)} in "
                    f"its `entry_channel`. A channel's param belongs to the pipeline, not to "
                    f"the type — write `params.{{param}}`, and declare `param:` beside it if "
                    f"this type needs a particular name. `mendel explain MD0228`.",
                )
            )
        return self


class TypeExtension(BaseModel):
    """An overlay that adds states to a type declared in a lower layer."""

    model_config = ConfigDict(extra="forbid")

    id: TypeId
    add_states: list[str]


def _parse_type(path: Path) -> list[TypeDeclaration | TypeExtension]:
    """Parse one type declaration or `add_states` extension.

    `id` is required. The generic stacker consumes `declares`; this parser discards it before
    strict model validation. Extensions may not carry replacement fields.
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
        # A whole declaration replaces every field of the lower declaration.
        return new
    if isinstance(old, TypeExtension):
        return TypeExtension(id=old.id, add_states=[*old.add_states, *new.add_states])
    return old.model_copy(update={"states": old.states | frozenset(new.add_states)})


class Vocabulary(BaseModel):
    types: dict[str, frozenset[str]]

    displaced: list[Displacement] = []
    """Declarations replaced or extended by higher layers."""
    test_data: dict[str, str | list[str]] = {}
    """Locations of small examples used by the test profile; remote data should be immutable."""

    params: dict[str, str] = {}
    """Explicit default parameter names; absent names derive from the type ID."""
    names: dict[str, str] = {}
    """User-facing names keyed by type ID."""
    explains: dict[str, str] = {}
    """User-facing explanations keyed by type ID."""

    columns: dict[str, int] = {}
    """Input-table column counts keyed by type ID."""

    scopes: dict[str, str] = {}
    """Default arrival scopes keyed by type ID."""

    entry_channels: dict[str, str] = {}
    """Entry-channel expressions keyed by type ID; absent entries use compiler defaults."""

    @field_serializer("types")
    def _sorted(self, types: dict[str, frozenset[str]]) -> dict[str, list[str]]:
        """Serialize type IDs and their states deterministically."""
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
        scopes: dict[str, str] = {}
        columns: dict[str, int] = {}
        params: dict[str, str] = {}
        names: dict[str, str] = {}
        explains: dict[str, str] = {}
        for type_id, entry in stacked.entries.items():
            if isinstance(entry, TypeExtension):
                raise ValueError(
                coded("MD0008", f"add_states for {type_id!r}, which no layer declares")
            )
            types[type_id] = entry.states
            scopes[type_id] = entry.scope
            columns[type_id] = entry.sample_columns
            if entry.entry_channel:
                entry_channels[type_id] = entry.entry_channel
            if entry.param:
                params[type_id] = entry.param
            if entry.name:
                names[type_id] = entry.name
            if entry.explain:
                explains[type_id] = entry.explain
            if entry.test_data:
                test_data[type_id] = entry.test_data
        return cls(
            types=types,
            entry_channels=entry_channels,
            scopes=scopes,
            columns=columns,
            params=params,
            names=names,
            explains=explains,
            test_data=test_data,
            displaced=list(stacked.displaced),
        )

    @classmethod
    def load(cls, layers: "Path | Sequence[Path]") -> "Vocabulary":
        """Load declarations from one or more layer roots in precedence order."""
        return cls.of(stack(layers_of(layers), cls.kind()))

    def with_proposals(self, ids: Iterable[str]) -> "Vocabulary":
        """Return a copy containing undeclared proposal IDs as stateless types.

        Existing declarations retain their states. If no ID is added, return this vocabulary.
        """
        added = {id: frozenset() for id in ids if id not in self.types}
        if not added:
            return self
        return self.model_copy(update={"types": {**self.types, **added}})

    def with_measurements(self, registry: "MeasurementRegistry") -> "Vocabulary":
        """Return a copy with one stateless `measurement.<id>` type per measurement."""
        types = dict(self.types)
        for measurement_id in registry.ids():
            types[f"measurement.{measurement_id}"] = frozenset()
        # Copy the model so future fields are retained without updating a hand-written list.
        return self.model_copy(update={"types": types})

    def states_for(self, type_id: str) -> frozenset[str]:
        if type_id not in self.types:
            raise UnknownTypeError(
                f"no layer declares the type {type_id!r}. Either it is a typo, or a layer that "
                f"uses it is being loaded without the layer that declares it — a private "
                f"overlay usually needs the base registry stacked underneath it."
            )
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
