"""What the verbs print, as distinct from what they do.

`OVERLAY`, `ANSWERED` and `REVIEW` are three different questions — what an installed layer
changed, what a person has already settled, and what still needs deciding — and folding any of
them into the others is the defect `cli.py`'s own comments warn about. Keeping them in one
module keeps that distinction in one place to read.

`_verdict` and `_frozen_against_moved_contracts` are `upgrade`'s report: drift, changes, stale
and orphaned overrides are reported separately because they oblige a reader to do different
things.
"""

import sys

from comeni_core.artifact.digest import digest_of, digest_of_bytes
from comeni_core.artifact.lockfile import Lockfile
from comeni_core.declared.layered import Displacement
from mendel_resolver.diff import diff_pipeline

from mendel_compiler.emit import emit, emit_config


def _report_upgrade(previous, fresh, ir, registry, paths, resolver) -> int:
    """Five categories, printed. Returns non-zero when one of them refuses.

    Drift and changes stay separate because Plan 1.7 established that distinction and it
    earns its keep: a digest moving is not the same event as a decision moving, and a contract
    can be edited in ways that change nothing here.
    """
    lockfile = Lockfile.from_pipeline(previous)
    for line in lockfile.drift_against(ir, registry, paths):
        print(f"  DRIFT   {line}", file=sys.stderr)

    changes = diff_pipeline(previous, fresh)
    for line in _verdict(previous, fresh, changes):
        print(line, file=sys.stderr)
    for change in changes:
        print(f"  CHANGED {change}", file=sys.stderr)

    for line in _frozen_against_moved_contracts(previous, fresh, registry):
        print(f"  MD0202  {line}", file=sys.stderr)

    if resolver is None:
        return 0
    print(
        f"{len(resolver.replayed)} decisions replayed, {len(resolver.fresh)} newly asked",
        file=sys.stderr,
    )
    # Five categories, not four. Stale and orphaned are different events and were both
    # invisible: stale vanished into the "newly asked" count above, and orphaned had
    # nowhere to appear at all, because `resolve()` is never called for a question that is
    # no longer asked.
    for key in resolver.stale:
        what = (
            "your edit no longer answers the question being asked"
            if key in resolver.stale_overrides
            else "the recorded choice no longer fits; re-asked"
        )
        print(f"  STALE    {key} — {what}", file=sys.stderr)
    for key in resolver.orphaned:
        print(f"  ORPHANED {key} — your edit no longer applies to anything", file=sys.stderr)
    if resolver.orphaned:
        # Refuses, where stale only reports. The difference is whether there is still a
        # question: a stale answer is re-asked and flagged tier 4, and an orphaned one has
        # nothing left to be an answer to. Dropping it quietly is the same failure as a
        # guard that silently stops guarding — A14's shape.
        print(
            f"\nmendel: MD0203: {len(resolver.orphaned)} recorded override(s) answer "
            f"questions this re-resolution does not ask. Nothing was written.\n"
            f"`mendel explain MD0203` for the long form.",
            file=sys.stderr,
        )
        return 2
    return 0


def _frozen_against_moved_contracts(previous, fresh, registry) -> list[str]:
    """`MD0202` — which values are carried forward from a contract that has since moved.

    `DRIFT` says a contract you pinned was edited. This says the consequence: these values
    were decided against the version before that edit and are being replayed regardless.
    Both are true and neither implies the other — a contract can be edited in ways that touch
    nothing here, and a value can be replayed from a contract that has not moved at all.

    Reports rather than refuses, because replaying is correct. Invariant 9 is that records are
    replayed on rerun rather than re-asked, which is how determinism survives having a model
    in the loop. A person is owed knowing it happened, not being stopped.
    """
    now = {step.id: step for step in fresh.steps}
    lines = []
    for step in previous.steps:
        current = now.get(step.id)
        if current is None or current.module.contract_id not in registry.contracts:
            continue
        if digest_of(registry.get(current.module.contract_id)) == step.module.digest:
            continue
        was = {setting.name: setting.value for setting in step.settings}
        frozen = sorted(
            setting.name
            for setting in current.settings
            if setting.name in was and was[setting.name] == setting.value
        )
        if frozen:
            lines.append(
                f"{step.id}: {', '.join(frozen)} unchanged, but "
                f"{step.module.contract_id} has been edited since they were decided"
            )
    return lines


def _verdict(previous, fresh, changes: list) -> list[str]:
    """Did the emitted pipeline move, and does anything explain it?

    Three separate statements, and they stay separate: `DRIFT` says the registry moved
    underneath the pin, this says the *pipeline* moved, and `CHANGED` says why. Drift with an
    identical artifact is ordinary — a contract edited in a way this pipeline does not use —
    and that is why they were split in Plan 1.7.

    Compares against what would be emitted **now**, in memory, rather than against files on
    disk. That is what lets `--dry-run` answer the same question while writing nothing, and it
    removes a way for the two paths to disagree.
    """
    if previous.emitted is None:
        return [
            "this pipeline predates the emitted-artifact record, so whether it moved cannot "
            "be checked — only what the diff below can see."
        ]

    would_be = {
        "main.nf": digest_of_bytes(emit(fresh).encode()),
        "nextflow.config": digest_of_bytes(emit_config(fresh).encode()),
    }
    recorded = {file.name: file.digest for file in previous.emitted.files}
    moved = sorted(name for name, digest in recorded.items() if would_be.get(name) != digest)
    if not moved:
        return ["the generated pipeline is byte-identical to the one recorded"]

    lines = [f"the generated pipeline differs: {', '.join(moved)}"]
    if not changes:
        # A guard that reports its own blind spot. `diff_pipeline` deliberately does not
        # compare `ext_args`, and no comparison of two documents can see the compiler itself
        # changing; naming both causes keeps a reader from assuming the likelier one.
        lines.append(
            "  but no recorded change explains it. Either the compiler itself changed since "
            "this pipeline was written, or the diff has a blind spot. Both are worth knowing."
        )
    return lines


def _displacement_line(record: Displacement) -> str:
    """One displaced declaration, in the words a reader of the build output needs.

    Names the kind, because `strandedness` and a contract id look nothing alike but a
    laboratory reading "displaced" wants to know *what* was displaced before it cares
    which layer did it.
    """
    what = record.winning_key or record.key
    displaced = f" over {', '.join(record.displaced_keys)}" if record.displaced_keys else ""
    return (
        f"{record.kind.value}: {what} from {record.winning_layer}{displaced}, "
        f"displacing {record.displaced_layer}"
    )


