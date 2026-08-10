"""`mendel build` — goal in, pipeline directory out; `mendel profile` — measure first."""

import argparse
import shutil
import sys
from pathlib import Path

import yaml
from comeni_core import yaml_strict
from comeni_core.digest import digest_of, digest_of_bytes
from comeni_core.layer import layer_name
from comeni_core.layered import Displacement
from comeni_core.lockfile import Lockfile
from comeni_core.measurement import BadMeasurementValueError, UnknownMeasurementError
from comeni_core.pipeline import Pipeline
from mendel_resolver import layers
from mendel_resolver.diff import diff_pipeline
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.replay import ReplayResolver
from mendel_resolver.resolve import resolve
from mendel_resolver.router import UnroutableError
from mendel_resolver.rules import RuleValidationError
from pydantic import ValidationError

from mendel_compiler import conformance, pipeline_file
from mendel_compiler.emit import emit, emit_config, entry_params
from mendel_compiler.gates import Gate, materialise_stub_data, run_gate


def main(argv: list[str] | None = None) -> int:
    """Entry point. Wraps `_build` so a user mistake is a message, not a traceback."""
    try:
        return _build(argv)
    except UnroutableError as exc:
        print(f"mendel: cannot route this goal — {exc}", file=sys.stderr)
    except ValidationError as exc:
        print(f"mendel: this goal is not valid —\n{exc}", file=sys.stderr)
    except RuleValidationError as exc:
        print(f"mendel: a rule table will not load —\n{exc}", file=sys.stderr)
    except (UnknownMeasurementError, BadMeasurementValueError) as exc:
        print(f"mendel: this goal's profile is not valid — {exc}", file=sys.stderr)
    except (OSError, KeyError, ValueError) as exc:
        # `ValueError` last, and it catches a lot on purpose: a symlink in a layer, a
        # duplicate YAML key, an `add_states` for a type nothing declares, A35's joined
        # `UnknownStateError`. Every one of them is a refusal this code chose to make, and
        # every one of them reached the user as a traceback. `ValidationError` is caught
        # above and `RuleValidationError` above that, so the specific messages still win.
        print(f"mendel: {exc}", file=sys.stderr)
    return 2


def _build(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mendel")
    parser.add_argument(
        "command", choices=["build", "profile", "publish", "upgrade", "emit", "explain"]
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help=(
            "a diagnostic code for `explain`, or a pipeline.yml for `emit`, `upgrade` "
            "and `publish`"
        ),
    )
    parser.add_argument("--goal", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "`upgrade` only: report what would move and write nothing. This is `verify` — "
            "a separate verb comparing digests would answer a strictly weaker question, "
            "and two answers to 'is this still what it says it is' is how they disagree."
        ),
    )
    parser.add_argument(
        "--have",
        action="append",
        default=None,
        help="a type id the laboratory holds; repeat. `profile` only.",
    )
    # Not `required=True`: `mendel explain MD0104` writes nothing and loads nothing, so
    # demanding an output directory for it would be argparse describing the wrong verb.
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--gate", type=Gate, default=None)
    parser.add_argument(
        "--registry",
        type=Path,
        action="append",
        default=None,
        help=(
            "a registry layer — a directory holding contracts/, rules/ and vocabularies/; "
            "repeat to stack overlays, later layers win"
        ),
    )
    args = parser.parse_args(argv)

    # Before anything loads: `explain` is documentation, and asking it for a code while a
    # registry will not load would answer the wrong question.
    if args.command == "explain":
        if not args.target:
            parser.error("explain needs a code, e.g. `mendel explain MD0104`")
        print(conformance.explain(args.target))
        return 0

    # `--dry-run` belongs to `upgrade` alone: it means "re-resolve and compare", and there
    # is nothing to compare a fresh `build` against. Accepting it elsewhere would make it a
    # flag that silently means "do nothing".
    if args.dry_run and args.command != "upgrade":
        parser.error("--dry-run is for `upgrade`; it is what `verify` would have been")

    # `publish` takes no `--out`, and that is the shape of the verb rather than an omission.
    # It does not produce a new pipeline; it certifies the one it was given — runs the gate
    # and stamps the verdict into that directory's `pipeline.yml`. `upgrade` is the opposite
    # and must never write in place, because what you had is the evidence.
    if args.command == "publish":
        if args.out is not None:
            parser.error(
                "publish takes no --out: it certifies the pipeline you give it, in place. "
                "Use `mendel upgrade <pipeline.yml> --out <dir>` to produce a new one."
            )
    # `--dry-run` writes nothing, so demanding somewhere to write would be argparse
    # describing the wrong verb — the same reason `explain` is handled above it.
    elif args.out is None and not args.dry_run:
        parser.error(f"{args.command} needs --out")

    # Before the registry loads, and deliberately: `emit` reads no registry, no vocabulary
    # and no measurements. That is the whole point of materialising the pipeline — a
    # laboratory can archive a validated pipeline and regenerate its Nextflow years later
    # without the registry it was built against, which is the part that resolves differently
    # as it changes. Loading one here would make that untrue while the tests still passed.
    if args.command == "emit":
        if not args.target:
            parser.error("emit needs a pipeline.yml, e.g. `mendel emit build/pipeline.yml`")
        return _emit_verb(Path(args.target), args.out)

    # `publish` certifies the artifact on disk and re-resolves nothing (A50). Like `emit`, it
    # needs no registry and no network: `pipeline.yml` is self-contained, so certification only
    # asks "do the files on disk pass the gate?" — a question the registry does not answer.
    # Sharing `upgrade`'s re-resolution path made publish re-resolve against whatever `--registry`
    # was installed, silently swap the pipeline, erase human overrides, and stamp a gate on the
    # result: the door with no undo certifying a pipeline nobody read.
    if args.command == "publish":
        if not args.target:
            parser.error("publish needs a pipeline.yml, e.g. `mendel publish build/pipeline.yml`")
        return _publish_verb(Path(args.target), args.gate)

    # A layer is a directory, not a contracts folder: all three kinds of registry data
    # stack together, so a laboratory can ship its own types and rules alongside its
    # modules. Only contracts stacked before the 2026-08-03 audit.
    loaded = layers.load(args.registry or [args.root / "registry"])
    vocab, registry, rules = loaded.vocabulary, loaded.registry, loaded.rules

    # Conformance: does each contract tell the truth about its module? `-stub-run` cannot
    # answer this — nf-core stubs never read their inputs, so a process handed an empty
    # tuple where a genome belongs is exactly as green as one handed a genome.
    #
    # `args.root / "vendor"` is the module *source*, not `nf_include`'s prefix. `nf_include`
    # says where a module lands in the generated pipeline; these are deliberately not the
    # same path.
    diagnostics = conformance.check(
        registry, args.root / "vendor", measurements=loaded.measurements
    )
    unverified = [d.where for d in diagnostics if d.code == "MD0100"]
    blocking = [d for d in diagnostics if d.code != "MD0100"]
    for diagnostic in diagnostics:
        print(diagnostic.render(), file=sys.stderr)
    if blocking:
        print(
            f"\nmendel: {len(blocking)} contract(s) disagree with their modules. "
            f"Nothing was emitted.\n"
            f"`mendel explain {blocking[0].code}` for the long form.",
            file=sys.stderr,
        )
        return 2

    previous: Pipeline | None = None
    resolver = None
    if args.command == "upgrade":
        # `upgrade` takes its goal from the file rather than from a `--goal` argument:
        # re-resolving a *different* goal and calling the result an upgrade is how "only what
        # you touched moved" would quietly become false. (`publish` no longer shares this path —
        # it certifies without re-resolving, A50.)
        if not args.target:
            parser.error(
                "upgrade needs a pipeline.yml, e.g. `mendel upgrade build/pipeline.yml`"
            )
        source = Path(args.target)
        previous = pipeline_file.load(source)
        refusal = _refuse_a_divergent_directory(source, previous, args.command)
        if refusal is not None:
            return refusal
        goal = previous.goal
        # A46: replay the answer `settings[].value` carries, not only `decisions[].human_override`
        # — the two are one answer and `emit` reads the former, so `upgrade` must honour it too.
        resolver = ReplayResolver(previous.replayable_decisions())
        if args.out is not None and args.out.resolve() == source.parent.resolve():
            # Never in place. With one artifact the natural implementation updates
            # `pipeline.yml` where it sits, and that destroys the only record of what you
            # had: the replayed overrides, the previous digests, the gate evidence.
            print(
                f"mendel: {args.command} must not write over the pipeline it read. "
                f"Give --out a different directory; the one you have is the evidence.",
                file=sys.stderr,
            )
            return 2
    elif args.command == "profile":
        goal = _profiling_goal(args, loaded)
    else:
        if args.goal is None:
            parser.error(f"{args.command} needs --goal")
        goal = Goal.model_validate(yaml_strict.load(args.goal))
        # The profile used to be rebuilt here through `MeasurementRegistry.profile()`,
        # the one validating constructor — belt and braces over a check that did not
        # exist anywhere else. It exists now, in `resolve()`, which is the only way past
        # this point for any verb. Doing it here as well would mean `build` was checked
        # twice and `upgrade` once, which is how the gap opened. Audit 2026-08-06, A2.

    ir = resolve(
        goal,
        registry,
        rules,
        loaded.measurements,
        vocabulary=vocab,
        resolver=resolver,
        layer_names=[layer_name(p) for p in loaded.paths],
    )
    ir.unverified = unverified

    pipeline = Pipeline.of(ir, registry, vocab, loaded.measurements, loaded.paths, goal=goal)

    # **Before anything is written.** A refused upgrade must leave nothing behind — A4's
    # posture, and `MD0203` is a refusal — and reporting after the write meant an orphaned
    # override produced a directory that looked upgraded and then said it was not.
    #
    # It is also what makes `--dry-run` the same code path rather than a second one. The
    # verdict compares against what *would* be emitted, in memory, so nothing here needs
    # files on disk: `verify` differs from `upgrade` only in whether bytes are written. Two
    # comparisons of "is this still what it says it is" is root D's finding waiting to happen.
    if previous is not None and args.command == "upgrade":
        if _report_upgrade(previous, pipeline, ir, registry, loaded.paths, resolver):
            return 2
        if args.dry_run:
            return 0

    args.out.mkdir(parents=True, exist_ok=True)
    # Materialise once, write it, read it back, and emit from **the copy that was read**.
    # Everything the emitter reads now lives on the `Pipeline`, which is what lets `mendel
    # emit` regenerate this without a registry — and running emission on the round trip is
    # what keeps that promise honest, since a field that does not survive YAML fails the
    # build (MD0206) instead of quietly meaning less than the file says.
    pipeline = pipeline_file.write(args.out, pipeline)
    (args.out / "main.nf").write_text(emit(pipeline))
    (args.out / "nextflow.config").write_text(emit_config(pipeline))
    # `nf_include` is where a module lands in the *generated* pipeline; `vendor/` is
    # where this repository keeps the source. Deliberately not the same path.
    vendored = args.root / "vendor" / "modules"
    if vendored.exists():
        shutil.copytree(vendored, args.out / "modules", dirs_exist_ok=True)

    if args.command == "profile":
        # Which contract measures what, read off the IR that was actually resolved rather
        # than off the registry — the file records what this pipeline will produce, not
        # what the registry could produce in principle.
        produced = {
            port.type_id.removeprefix("measurement."): node.contract_id
            for node in ir.nodes
            for port in registry.get(node.contract_id).produces
            if port.type_id.startswith("measurement.")
        }
        (args.out / "profile.yml").write_text(
            yaml.safe_dump(
                loaded.measurements.to_measure(produced).model_dump(mode="json"),
                sort_keys=True,
            )
        )

    # Its own section, above the review list rather than inside it. "What did my overlay
    # change" and "what must I decide" are different questions, and folding the first into
    # the second is how a reviewer learns to skim both. Audit A5, A15.
    #
    # One block for all four kinds since A23/A24/A25. `SHADOW` was contracts only, printed
    # off the registry, so a measurement or vocabulary an overlay replaced had nowhere to
    # be said — and a reader had two lists to read that answered one question.
    reroutes = [_displacement_line(record) for record in ir.displaced]
    reroutes += ir.overlay_reroutes()
    if reroutes:
        print(
            f"{len(reroutes)} overlay reroute(s) — an installed layer changed what the "
            f"layers below it would do:",
            file=sys.stderr,
        )
        for item in reroutes:
            print(f"  OVERLAY  {item}", file=sys.stderr)

    # Its own line, above the review list, exactly as OVERLAY is. "What did somebody
    # already decide" and "what must I decide" are different questions, and an answered
    # tier-4 left in the second is how the count never reaches zero — a list that cries
    # wolf gets ignored, and the genuinely unanswered item beside it goes unread too.
    answered = ir.overrides()
    if answered:
        print(
            f"{len(answered)} tier-4 question(s) answered by a human — still tier 4, and "
            f"still recorded:",
            file=sys.stderr,
        )
        for item in answered:
            print(f"  ANSWERED {item}", file=sys.stderr)

    flagged = ir.needs_review()
    print(f"{len(ir.nodes)} modules, {len(flagged)} requiring review", file=sys.stderr)
    for item in flagged:
        print(f"  REVIEW  {item}", file=sys.stderr)

    passed: Gate | None = None
    failed = False
    if args.gate is not None:
        if args.gate is Gate.STUB:
            materialise_stub_data(args.out, entry_params(pipeline))
        result = run_gate(args.gate, args.out)
        print(f"gate {result.gate}: {'PASS' if result.passed else 'FAIL'}", file=sys.stderr)
        if result.passed:
            passed = result.gate
        else:
            print(result.output, file=sys.stderr)
            failed = True

    # Stamped last, because `gate:` is part of what `from_digest` covers — recording the
    # digest before the gate ran would make every gated build stale the moment its verdict
    # arrived. Stamped on the failing path too: generated files with no record of what they
    # came from are exactly the divergence MD0213 exists to catch.
    pipeline = pipeline_file.stamp(args.out, pipeline, gate=passed)
    if failed:
        return 1

    # `pipeline.bundle.json` and `mendel.lock.yml` are both gone. Everything they carried
    # is in `pipeline.yml` — the goal, every decision, every contract by digest and
    # container, every layer, the gate that passed and the digests of what was emitted.
    # **The directory is the artifact.**
    #
    # This path is `build` and `upgrade` (and `profile`): they resolve a goal and write a fresh
    # directory. Certifying an existing one is `publish`, which branched off above (A50) — it
    # re-resolves nothing, so it never reaches here. The gate still runs *before* the verdict is
    # stamped — A4: a `--gate` build must not leave an artifact stamped with a gate it failed.
    return 0


def _emit_verb(target: Path, out: Path) -> int:
    """`mendel emit <pipeline.yml> --out <dir>` — the Nextflow, rebuilt from the file.

    Four checks, and only three of them refuse.

    `MD0210` refuses because an `include` path that resolves to nothing produces a `main.nf`
    which looks finished and dies at launch. `MD0214` refuses because regenerating would
    overwrite a hand edit in silence, and its fix names `pipeline.yml` rather than telling
    anyone to revert — a person who edited `main.nf` was trying to change the pipeline.

    `MD0213` **does not refuse here**, and the plan had it the other way round. This verb is
    the cure for staleness; refusing it would mean the file a reader is told to edit can never
    be edited. The refusal belongs on the verbs that treat the generated files as evidence.
    """
    pipeline = pipeline_file.load(target)

    # Beside the file, not beside the output: `modules/` is part of the pipeline a laboratory
    # archives, and `pipeline.yml` is what names it.
    source = target.parent
    if not (source / "modules").is_dir():
        print(
            f"mendel: MD0210: {source}/modules is absent, so every `include` in the emitted "
            f"workflow would point at nothing. Nothing was written. "
            f"`mendel explain MD0210`.",
            file=sys.stderr,
        )
        return 2

    out.mkdir(parents=True, exist_ok=True)
    edited = pipeline_file.hand_edited(out, pipeline)
    if edited:
        print(
            f"mendel: MD0214: {', '.join(edited)} changed since it was generated, and "
            f"re-emitting would overwrite that.\n"
            f"  Make the change in {target} and run this again — that is the file the "
            f"pipeline is built from.\n"
            f"  To discard it instead, delete {edited[0]} and run this again.",
            file=sys.stderr,
        )
        return 2

    stale = pipeline_file.is_stale(pipeline)
    if stale:
        print(
            f"MD0213: {target} has changed since the Nextflow was generated from it. "
            f"Regenerating.",
            file=sys.stderr,
        )

    # A49: render both in memory first. `emit_config` raises `MD0201` on a non-substitutable
    # value, and writing `main.nf` before that raise left the directory half-regenerated — then
    # the retry refused with `MD0214`, blaming the user for a change `emit` itself made. A
    # refusal must leave nothing behind, the posture `upgrade` already takes.
    main_nf = emit(pipeline)
    config = emit_config(pipeline)
    if source.resolve() != out.resolve():
        shutil.copytree(source / "modules", out / "modules", dirs_exist_ok=True)
    (out / "main.nf").write_text(main_nf)
    (out / "nextflow.config").write_text(config)
    # A47: a no-op re-emit must carry the verdict through — `stamp`'s default `gate=None` erased a
    # `publish`ed pipeline's certification on the next `emit`. But a *stale* file has changed since
    # it was gated, so the verdict no longer describes this pipeline and is cleared: preserving it
    # would certify content that never passed the gate.
    pipeline_file.stamp(out, pipeline, gate=None if stale else pipeline.gate)
    return 0


def _publish_verb(target: Path, gate: "Gate | None") -> int:
    """`mendel publish <pipeline.yml> --gate <g>` — certify the artifact on disk, in place.

    A50. Certification asks one question — do the files on disk pass the gate — and the answer
    does not depend on the registry: `pipeline.yml` is self-contained and `emit` regenerated
    these files from it with no registry at all. So `publish` re-resolves nothing. It refuses a
    directory that has diverged from its `pipeline.yml` (`MD0213`/`MD0214`, so the gate runs on
    the files this file describes), runs the gate, and stamps the verdict — the door with no
    undo now certifies exactly what a person read, never a re-resolution of it.

    The legitimate "I edited my goal and want to publish the result" flow still works: edit,
    `mendel emit` (which surfaces the change via `MD0213` and regenerates), then `publish`.
    """
    pipeline = pipeline_file.load(target)
    directory = target.parent
    refusal = _refuse_a_divergent_directory(target, pipeline, "publish")
    if refusal is not None:
        return refusal

    passed: Gate | None = None
    if gate is not None:
        if gate is Gate.STUB:
            materialise_stub_data(directory, entry_params(pipeline))
        result = run_gate(gate, directory)
        print(f"gate {result.gate}: {'PASS' if result.passed else 'FAIL'}", file=sys.stderr)
        if result.passed:
            passed = result.gate
        else:
            print(result.output, file=sys.stderr)
            # The verdict is stamped on the failing path too — a directory with no record of
            # what it came from is the divergence MD0213 exists to catch — but publish reports
            # the failure. A4: never leave an artifact stamped with a gate it did not pass.
            pipeline_file.stamp(directory, pipeline, gate=None)
            return 1

    pipeline_file.stamp(directory, pipeline, gate=passed)
    return 0


def _refuse_a_divergent_directory(source: Path, previous: Pipeline, verb: str) -> int | None:
    """`MD0213` and `MD0214`, on the verbs that treat the generated files as evidence.

    Task 6 put both on `emit`, where `MD0213` could only report — that verb is the *cure* for
    staleness, so refusing there would mean the file a reader is told to edit can never be
    edited. Here it refuses, and the reason is the difference between the verbs.

    `upgrade` compares against what this directory says it emitted, and `publish` stamps a
    gate verdict onto it. A `main.nf` generated from a different `pipeline.yml` than the one
    being read makes both of those statements about nothing.
    """
    directory = source.parent
    edited = pipeline_file.hand_edited(directory, previous)
    if edited:
        print(
            f"mendel: MD0214: {', '.join(edited)} changed since it was generated, so this "
            f"directory does not describe itself. Make the change in {source} and run "
            f"`mendel emit` — `mendel explain MD0214`.",
            file=sys.stderr,
        )
        return 2
    if pipeline_file.is_stale(previous):
        print(
            f"mendel: MD0213: {source} has changed since the Nextflow was generated from "
            f"it, so `{verb}` would report on files that are not what this file describes.\n"
            f"  Run `mendel emit {source} --out {directory}` first — "
            f"`mendel explain MD0213`.",
            file=sys.stderr,
        )
        return 2
    return None


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


def _profiling_goal(args: argparse.Namespace, loaded: layers.Layers) -> Goal:
    """Sugar for `build --want measurement.*`. One resolver, one emitter, one set of
    decision records — the verb exists for discoverability, not as a second path.

    Two rules do the work.

    **The profile is empty.** A build resolves tier-3 parameters against a profile, and a
    profiling build is a build; resolving one against a profile would need a profile to
    profile with. So profiling contracts resolve at tiers 1, 2 and 4 only, and the regress
    stops here rather than one recursion later.

    **`want` is what this registry can actually reach.** Declaring a measurement is how a
    laboratory *starts* — before any tool for it exists — so wanting every declared
    measurement would make the verb unroutable for exactly the people adopting it. What
    cannot be measured is named on stderr, never dropped in silence.
    """
    have = args.have or []
    reachable, unreachable = [], []
    for measurement_id in loaded.measurements.ids():
        type_id = f"measurement.{measurement_id}"
        (reachable if loaded.registry.producers_of(type_id, frozenset()) else unreachable).append(
            measurement_id
        )
    if not reachable:
        raise UnroutableError(
            f"nothing can measure anything: no contract produces a measurement.* type. "
            f"Declared measurements: {', '.join(loaded.measurements.ids()) or '(none)'}"
        )
    print(f"profiling for: {', '.join(reachable)}", file=sys.stderr)
    if unreachable:
        print(
            f"  NOT MEASURED  {', '.join(unreachable)} — declared, but no contract in this "
            f"registry produces them",
            file=sys.stderr,
        )
    return Goal(
        have=[GoalInput(type_id=t) for t in have],
        want=[f"measurement.{m}" for m in reachable],
        profile=loaded.measurements.profile({}),
    )


if __name__ == "__main__":
    raise SystemExit(main())
