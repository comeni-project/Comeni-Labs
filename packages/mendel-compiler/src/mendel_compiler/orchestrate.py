"""The build path, as a function.

**Extracted in Plan 3C phase 0, and it is a lift rather than a rewrite.** The core was already
in memory: `resolve_verbs.run`'s own comment said so — *"nothing here needs files on disk:
`verify` differs from `upgrade` only in whether bytes are written"* — and what kept it uncallable
was the `Namespace` around it, not the work inside. Three plans named this as a prerequisite
before anyone read it closely enough to notice.

**Takes roots, returns objects, writes nothing.** Every path decision, every collision check and
every byte stays in the CLI — the same split the forge's own command layer already has, whose
docstring says in as many words that a transport holds no logic.

*(That package is named here only in prose, and not even that: `tests/guards/test_purity.py` scans
for the module name in the **file**, not merely in its imports, and refused this docstring when it
spelled it out. The breadth is right — a prose reference is how a dependency gets argued into
existence — and it costs one rewording.)*

**Conformance raises here rather than printing.** In the CLI it printed to stderr and returned 2,
which is a *transport's* way of saying no; a caller that is an HTTP request needs the same refusal
as a value. `ConformanceRefused` is a `ValueError`, which `mendel-api` already maps to a coded
422 — so one raise serves both without either knowing about the other.

`test_the_seam_and_the_cli_agree_byte_for_byte` is what makes this safe, and it compares the
serialised artifact rather than the object graph: moving orchestration is precisely the change
`make check` waves through, since nothing outside `test_counts.py` runs a tool.
"""

from dataclasses import dataclass
from pathlib import Path

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.declared.layer import layer_name
from mendel_resolver import layers
from mendel_resolver.goal import Goal
from mendel_resolver.ports import AmbiguityResolver
from mendel_resolver.resolve import resolve

from mendel_compiler import conformance


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


def build(
    goal: Goal,
    *,
    registry_root: Path | None = None,
    registry_roots: list[Path] | None = None,
    prior: list | None = None,
    resolver: AmbiguityResolver | None = None,
) -> Built:
    """Resolve a goal against a registry. Writes nothing, reads no arguments namespace.

    `registry_roots` is the stack — invariant 11 — and `registry_root` is the one-layer
    convenience every caller but a lab overlay wants. Passing both is a caller bug and the
    stack wins, because a list is the general case and a scalar cannot express it.
    """
    roots = registry_roots or ([registry_root] if registry_root else None)
    if not roots:
        raise ValueError("orchestrate.build needs a registry root")

    loaded = layers.load(roots)

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
    blocking = [d for d in diagnostics if d.code != "MD0100"]
    if blocking:
        raise ConformanceRefused(
            blocking,
            f"{len(blocking)} contract(s) disagree with their modules. Nothing was emitted.",
        )

    ir = resolve(
        goal,
        loaded.registry,
        loaded.rules,
        loaded.measurements,
        vocabulary=loaded.vocabulary,
        resolver=resolver,
        layer_names=[layer_name(p) for p in loaded.paths],
        prior=prior or [],
    )
    ir.unverified = [d.where for d in diagnostics if d.code == "MD0100"]

    pipeline = Pipeline.of(
        ir, loaded.registry, loaded.vocabulary, loaded.measurements, loaded.paths, goal=goal
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
