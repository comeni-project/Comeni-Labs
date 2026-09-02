"""Closed state vocabularies. A type declares exactly the states it may carry."""

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator

from comeni_core import yaml_strict
from comeni_core.artifact.load import _param_refs
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
    sample_columns: int = 1
    """How many CSV columns one sample of this type occupies. **1 or 2.**

    `fastq.reads` is 2 — `reads_1` and `reads_2`, nf-core's samplesheet convention, with an
    empty second column meaning single-end. `annotation.gtf` is 1. **Not derivable**: nothing
    about the type id or its states says a FASTQ arrives in pairs and a GTF does not, and the
    entry channel's Groovy says it only by using `fromFilePairs`, which is a fact about the
    glob form rather than about the type.

    Only read when a pipeline takes two or more sample-scoped channels, which is when
    `params.input` becomes a table — see `Pipeline.input_form`. A single sample-scoped channel
    still emits its glob, and that is `tests/emit/test_counts.py`'s shape.

    The **column names** come from the channel, not from here: `reads` becomes `reads_1` and
    `reads_2`, and a pipeline taking two GTFs gets `gtf` and `gtf_2`, because a channel's name
    is already the thing a person distinguishes them by.
    """

    scope: str = "sample"
    """How many times one of these arrives, relative to the run — `run` or `sample`.

    **A reference genome is `run`.** It is one file for the whole analysis, and a Nextflow
    process with several *queue* inputs runs as many times as the shortest — so a queue of one
    genome capped a twenty-four-sample run at one invocation, silently. `Scope` carries the
    argument.

    A **default**, which a pipeline may override: the same split as `entry_param`. Per-sample
    annotations over a shared one is a judgement about an experiment, and the product's claim is
    that no such judgement is silent — so the override carries a `Why` and appears in
    `pipeline.yml`.

    Defaulting to `sample` is the conservative choice: it is what every channel was before this
    field existed, so a type that says nothing behaves exactly as it did.
    """

    entry_channel: GroovyExpression | None = None
    """Unbounded Groovy, emitted verbatim — the designed exception, marked as such.

    **A one-placeholder template since Plan 5B:** `params.{param}`, substituted at
    materialisation with the channel's own param. Not a template language — one substitution,
    the same argument as Plan 1.15's `transform`. `{` is legal Groovy and appears throughout
    these expressions (`.map { gtf -> … }`), so the placeholder is matched as the literal seven
    characters `{param}` and everything else is left alone.

    **Why it stopped being a literal.** `params.gtf` written into the type fuses three things
    that belong to a *pipeline* rather than to a type: the param name, the cardinality, and the
    fan-out. The first is what made two `annotation.gtf` inputs one hole — spec §0's table.
    """
    param: NfIdentifier | None = None
    """The param a channel of this type reads **by default**. `None` derives it from the type
    id's last segment, which is right for `annotation.gtf` → `gtf` and `genome.fasta` → `fasta`.

    ═══ IT EXISTS BECAUSE `fastq.reads` READS `params.input` ══════════════════════════════════

    Every other type in the shipped registry reads `params.<last segment>`; `fastq.reads` reads
    `params.input`, and has since the spine was first emitted. Deriving the param from the
    channel name alone would rename it to `params.reads` — a change to **what a laboratory
    types**, arriving inside a phase the plan describes as *"the rename, with no behaviour
    change"*.

    It would also delete the problem spec §12.1 says phase 5 has to solve: *`params.input` is
    one null whether it is a fastq glob or a CSV path*. A spec that reasons about a live
    ambiguity is a spec whose author expects it to still be there.

    So the type declares the name and the pipeline suffixes it — `gtf`, `gtf_2` — which is the
    same split as `name` and keeps both facts where they can be read.
    """
    test_data: str | list[str] | None = None

    @model_validator(mode="after")
    def _an_entry_channel_names_no_param_of_its_own(self) -> "TypeDeclaration":
        """MD0228. A literal `params.gtf` is refused; `params.{param}` is what to write.

        ═══ THE TWO DIRECTIONS ARE DELIBERATELY NOT SYMMETRIC — spec §1.3 ════════════════════

        - **A new registry read by an OLD Mendel** is the version floor's job: `requires_format`
          on the layer, `MD0020`, so an engine that does no substitution says *this registry
          needs a newer Mendel* instead of writing `params.{param}` into Groovy.
        - **An old registry read by a NEW resolver** is this, and it is a refusal rather than a
          tolerance. A registry whose channel names cannot be controlled is one that silently
          merges two inputs of one type into one hole — the defect this whole plan exists to
          remove — and carrying on quietly would be worse than stopping.

        So `requires_format: 1` does **not** buy a layer a literal entry channel. It is not
        meant to: the floor protects old *engines* from new *layers*, and this protects new
        engines from old layers.

        ═══ IT CHECKS FOR A HARDCODED NAME, NOT FOR A MISSING PLACEHOLDER ════════════════════

        The first version refused any `entry_channel` without `{param}` and was too broad by
        exactly one case: a channel that reads **no** param at all. `Channel.empty()` hardcodes
        nothing, so there is nothing for a pipeline to have taken away from it — and several
        test fixtures use precisely that to exercise other diagnostics, which is how the
        over-reach surfaced.

        The spec's own words are *"a literal `params.gtf`"*, and that is the thing being
        refused: a param name written into a type. An expression that names none is fine, and
        one that names only `{param}` is the point.
        """
        if self.entry_channel is None:
            return self
        hardcoded = _param_refs(self.entry_channel.replace("params.{param}", ""))
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

    **`declares:` is accepted and ignored, and `id:` is required** (`MD0012`). Both are part of
    comeni-registry#1: a layer was one directory per kind because the directory was how the
    loader knew what a file was, and vocabularies took their identity from the filename on top
    of that — so a type could not be moved without being renamed. The filename fallback is gone
    rather than deprecated: `align.type.yml` in a tool folder would declare `align.type`.

    `declares:` is ignored rather than checked *here* on purpose. Every declared model sets
    `extra="forbid"`, so without accepting it a migrated file would fail to load, and the
    registry could not be migrated one file at a time.
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

    params: dict[str, str] = {}
    """The default param name for each type that declares one. See `TypeDeclaration.param` —
    absent means the type id's last segment, which is every type but `fastq.reads`."""

    columns: dict[str, int] = {}
    """Type id -> how many CSV columns one sample of it occupies. See
    `TypeDeclaration.sample_columns`."""

    scopes: dict[str, str] = {}
    """Type id -> its default scope. See `TypeDeclaration.scope`."""

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
        scopes: dict[str, str] = {}
        columns: dict[str, int] = {}
        params: dict[str, str] = {}
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
            if entry.test_data:
                test_data[type_id] = entry.test_data
        return cls(
            types=types,
            entry_channels=entry_channels,
            scopes=scopes,
            columns=columns,
            params=params,
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

    def with_proposals(self, ids: Iterable[str]) -> "Vocabulary":
        """This vocabulary plus the types a draft is proposing to add, each stateless.

        **Derived, never mutated** — the same argument as `with_measurements`: the loaded
        vocabulary is what the registry says, and asking *what if I added these* must not
        change that for every other caller.

        **A declared type is never overwritten.** Its states are real and a proposal's
        emptiness is not; silently emptying them would be a very quiet way to break routing.

        States are empty because a new type's states are a separate judgement, and inventing
        them at approval time would be the reviewer guessing at a second thing while judging
        the first. `add_states:` is how a later layer extends them — invariant 11.
        """
        added = {id: frozenset() for id in ids if id not in self.types}
        if not added:
            return self
        return self.model_copy(update={"types": {**self.types, **added}})

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
        # **`model_copy`, not a fresh `Vocabulary(...)`.** This listed every field by hand, so
        # it had to be kept in step with the model — and the failure mode is silence: a field
        # added to `Vocabulary` and collected by `of()` is dropped here, leaving one populated
        # and another empty a few lines apart with nothing raising. It was correct when this
        # changed, and correct by vigilance is what `test_a_derived_vocabulary_keeps_every_field`
        # replaces.
        return self.model_copy(update={"types": types})

    def states_for(self, type_id: str) -> frozenset[str]:
        if type_id not in self.types:
            # **The message says what to do, because the commonest way to reach it is not a
            # typo.** A private overlay names types the base layer declares, so loading one on
            # its own fails here — and it used to print the type id in quotes and nothing else,
            # which names the symptom and not the cause. `docs/guides/registry-layers.md`
            # documents that exact situation; the error now agrees with it.
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
