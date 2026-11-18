"""Resolve, validate, and materialise a pipeline entirely in memory.

``build`` is the shared seam for CLI and service callers. It loads registry layers, rejects
blocking conformance diagnostics, resolves the goal, and returns the IR, artifact, and loaded
layer data; callers decide where and whether to write them.
"""

from dataclasses import dataclass
from pathlib import Path

from comeni_core.artifact.digest import digest_of_directory
from comeni_core.artifact.pipeline import Pipeline
from comeni_core.declared.layer import layer_name
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from mendel_resolver.ports import AmbiguityResolver
from mendel_resolver.resolve import resolve

from mendel_compiler import conformance, locate


class ConformanceRefused(ValueError):
    """A contract disagrees with the module it describes, so nothing may be emitted.

    **Carries the diagnostics rather than a rendered string.** The CLI prints every one to
    stderr and exits 2; an API answers 422 with the first code. Rendering here would decide for
    both, and the two audiences genuinely differ — `mendel explain MD0104` is a terminal
    instruction and a JSON body cannot follow it.
    """

    def __init__(self, blocking: list, message: str) -> None:
        super().__init__(message)
        self.blocking = blocking


@dataclass(frozen=True)
class Built:
    """What a build produced, before anything is written.

    Three things rather than one, because the callers want different halves: the CLI writes
    `pipeline`, `upgrade` compares against `ir`, and 3C's canvas lays out `ir` while reading
    `pipeline` for the reasons. Returning only the pipeline would send the canvas back to the
    registry for a graph it already had.
    """

    pipeline: Pipeline
    ir: object
    layers: layers.Layers
    unverified: list[str]
    """Contracts whose module source could not be read — `MD0100`. **Not an error**: they are
    marked on the IR rather than trusted, which is what `CLAUDE.md` means by never asserting a
    conformance property over modules that were not readable."""


@dataclass(frozen=True)
class Prepared:
    """What a build needs of a registry before it sees a goal: the loaded layers, their
    conformance diagnostics and the facts each contract reads (#545).

    **Made here, remembered elsewhere.** A pure package keeps no cache (invariant 10); a caller
    that holds the registry's content digest, as `mendel_api.services.registry` does, may keep
    one of these for as long as the digest stands and pass it to every `build`. Nothing in it
    depends on git, so the layers' locators are still read on each build. Shared between
    builds, so nothing may mutate it."""

    layers: layers.Layers
    diagnostics: list
    facts_read: object
    digests: tuple[str, ...]
    """Each layer's `digest_of_directory`, in stack order: what the lockfile pins."""


def prepare(roots: list[Path], *, loaded: layers.Layers | None = None) -> Prepared:
    """Load `roots` and check each contract against its module: the part of a build that
    depends only on the registry. `loaded` is `layers.load(roots)` when the caller has it."""
    loaded = loaded or layers.load(roots)
    # Does each contract tell the truth about its module? `-stub-run` cannot answer this —
    # nf-core stubs never read their inputs, so a process handed an empty tuple where a genome
    # belongs is exactly as green as one handed a genome.
    #
    # **The layer carries the module now** (Plan 5A). It used to take a `vendor_root` — a
    # directory in *this* repository, on a different release cadence from the registry the
    # contracts came out of — so the check that exists to catch a contract drifting from its
    # module was comparing two things nobody kept in step. `--registry X` is now the whole
    # input, which is also what makes an air-gapped site a first-class customer (invariant 13).
    diagnostics = conformance.check(
        loaded.registry, loaded.modules, measurements=loaded.measurements
    )
    return Prepared(
        layers=loaded, diagnostics=diagnostics,
        facts_read=conformance.facts_read(loaded.registry, loaded.modules, loaded.measurements),
        digests=tuple(str(digest_of_directory(path)) for path in loaded.paths),
    )


def build(
    goal: Goal,
    *,
    registry_root: Path | None = None,
    registry_roots: list[Path] | None = None,
    prior: list | None = None,
    resolver: AmbiguityResolver | None = None,
    ai=None,
    prepared: Prepared | None = None,
) -> Built:
    """Resolve a goal against a registry. Writes nothing, reads no arguments namespace.

    `registry_roots` is the stack — invariant 11 — and `registry_root` is the one-layer
    convenience every caller but a lab overlay wants. Passing both is a caller bug and the
    stack wins, because a list is the general case and a scalar cannot express it.

    `prepared` is `prepare(roots)` made earlier, for these same roots in this same state; a
    caller that cannot vouch for that passes nothing and the registry is read here.
    """
    roots = registry_roots or ([registry_root] if registry_root else None)
    if not roots:
        raise ValueError("orchestrate.build needs a registry root")

    prepared = prepared or prepare(roots)
    loaded, diagnostics = prepared.layers, prepared.diagnostics
    blocking = conformance.blocking(diagnostics)
    if blocking:
        raise ConformanceRefused(
            blocking,
            f"{len(blocking)} contract(s) disagree with their modules. Nothing was emitted.",
        )

    # The registry this build routes with: the layers' contracts and the generated measuring
    # steps (#465). Conformance above checks only what a layer declares.
    routing = loaded.routing
    ir = resolve(
        goal,
        routing,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=resolver,
        layer_names=[layer_name(p) for p in loaded.paths],
        prior=prior or [],
        facts_read=prepared.facts_read,
        inspection=loaded.inspection,
    )
    ir.unverified = [d.where for d in diagnostics if d.code == "MD0100"]

    pipeline = Pipeline.of(
        ir, routing, loaded.vocabulary, loaded.measurements, loaded.paths, goal=goal,
        # The caller's AI provenance: none recorded is *no AI*, which refuses a value a model
        # settled (`MD0225`), so a builder session passes what it had.
        ai=ai, locators=locate.locators(loaded.paths), layer_digests=prepared.digests,
    )
    return Built(pipeline=pipeline, ir=ir, layers=loaded, unverified=ir.unverified)


def diagnostics_for(registry_roots: list[Path]) -> list:
    """Conformance alone, for a caller that wants to report before it builds.

    The CLI prints **every** diagnostic including the non-blocking `MD0100`s, before deciding
    whether to stop. `build()` cannot do that for it without printing, so it exposes the same
    check instead of the CLI re-deriving one.
    """
    loaded = layers.load(registry_roots)
    return conformance.check(loaded.registry, loaded.modules, measurements=loaded.measurements)
