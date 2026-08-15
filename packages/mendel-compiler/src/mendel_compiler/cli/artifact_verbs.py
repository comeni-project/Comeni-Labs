"""`emit` and `publish`: the verbs that read a `pipeline.yml` and load no registry.

Together because that is what they have in common and it is the interesting thing about them.
`emit` rebuilds the Nextflow from the artifact alone — no registry, no network — which is the
whole claim `pipeline.yml` makes and what lets a laboratory rebuild a validated pipeline years
later. `publish` certifies a directory that already exists. Neither resolves anything, and
neither can, which is why they return before `layers.load` is ever reached.

`_refuse_a_divergent_directory` is here rather than in `report.py` because it is a *refusal*
rather than a report: it decides whether the verb runs at all.
"""

import shutil
import sys
from pathlib import Path

from comeni_core.artifact.pipeline import SCHEMA_VERSION, Pipeline

from mendel_compiler import pipeline_file
from mendel_compiler.emit import emit, emit_config, entry_params
from mendel_compiler.gates import Gate, materialise_stub_data, run_gate


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

    # After the render and before the write. Rendering first keeps `MD0201` — a value that
    # would execute as Groovy on the pipeline host — ahead of this one: both refuse the same
    # edit, and a person who has written an injection needs to hear about that rather than
    # about their citation. Nothing has been written at this point either way. A104.
    # Named `mismatched`, not `stale`: `stale` is the MD0213 boolean above and is read
    # twelve lines below to decide whether the gate verdict survives. Shadowing it with a
    # list made an edited pipeline keep its certification, which `test_emit_clears_the_gate_
    # verdict_when_the_file_was_edited` caught immediately.
    if mismatched := pipeline_file.stale_reasons(pipeline):
        print(
            "mendel: MD0223: a value was edited and the reason beside it was not.\n  "
            + "\n  ".join(mismatched)
            + "\n  Update `why.reason` to explain the new value and set `why.for_value` to "
            "it, or revert the value — `mendel explain MD0223`.",
            file=sys.stderr,
        )
        return 2
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
    if previous.emitted is None and verb == "publish":
        # A70. `hand_edited` and `is_stale` both return "nothing to compare" here, and that is
        # right — there is genuinely no evidence. What is wrong is a *certifying* verb reading
        # no-evidence as no-problem: publish would gate whatever `main.nf` is on disk and stamp
        # the verdict onto an artifact that then permanently records having emitted that file.
        # Round four certified an unrelated workflow this way, at exit 0.
        #
        # A pipeline with no `emitted:` block is a supported state — archived, or hand-authored
        # — so this is not a defect in the file. It is a statement that this directory cannot
        # be certified until something ties the two together.
        #
        # **`publish` only, and the other two verbs are deliberate.**
        #
        # `emit` is the *cure*: it regenerates the files from this `pipeline.yml` and stamps
        # `emitted:`, after which MD0213 and MD0214 are meaningful again. Refusing there would
        # leave an archived pipeline with no way forward at all.
        #
        # `upgrade` already answers this honestly — it prints "predates the emitted-artifact
        # record" rather than claiming byte-identity, which is the same no-evidence-is-not-a-
        # clean-bill distinction this refusal makes. The difference is what the verb *does*
        # with the answer: upgrade produces a report a person reads, and publish stamps a
        # verdict onto the artifact itself. Only one of those is a claim about files nobody
        # checked, and only one has no undo.
        print(
            f"mendel: MD0222: {source} records no `emitted:` block, so nothing ties the files "
            f"in {directory} to it and `{verb}` cannot certify them. Run `mendel emit "
            f"{source} --out {directory}` first — `mendel explain MD0222`.",
            file=sys.stderr,
        )
        return 2
    edited = pipeline_file.hand_edited(directory, previous)
    if edited:
        print(
            f"mendel: MD0214: {', '.join(edited)} changed since it was generated, so this "
            f"directory does not describe itself. Make the change in {source} and run "
            f"`mendel emit` — `mendel explain MD0214`.",
            file=sys.stderr,
        )
        return 2
    # Before the digest checks, because this one is about the *document* rather than about
    # whether the generated files match it. A value carrying a justification that is false
    # about it is exactly what `publish` must not certify — the door with no undo stamped one
    # at exit 0 for as long as this check did not exist. A104.
    if stale := pipeline_file.stale_reasons(previous):
        print(
            f"mendel: MD0223: a value in {source} was edited and the reason beside it was "
            "not.\n  " + "\n  ".join(stale)
            + "\n  Update `why.reason` to explain the new value and set `why.for_value` to "
            "it, or revert the value — `mendel explain MD0223`.",
            file=sys.stderr,
        )
        return 2
    if pipeline_file.predates_schema(previous):
        # Not an error, and deliberately not `MD0213`. The digest was taken under an older
        # SCHEMA_VERSION, so it cannot match — for every archived pipeline at once, with
        # nobody having touched one. Saying "this file has changed" would send a laboratory
        # looking for an edit that does not exist. The generated files are still checked
        # above by `hand_edited`, which is the corruption that actually matters.
        print(
            f"note: {source} predates the current schema (written under version "
            f"{previous.emitted.schema_version}, this Mendel writes {SCHEMA_VERSION}), so its "
            f"content digest cannot match.\n"
            f"  Its generated files are unaffected and were checked. Run `mendel emit "
            f"{source} --out {directory}` to restamp it.",
            file=sys.stderr,
        )
        return None
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


