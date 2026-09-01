"""`build`, `upgrade` and `profile`: the three verbs that resolve.

**One module because they are one flow with three entry conditions, not three flows.** `upgrade`
replays a previous artifact's decisions before resolving; `profile` swaps the goal for one that
measures; `build` does neither. Everything after that — conformance, resolution, materialisation,
writing the file, the gate, the report — is the same code, and splitting it per verb would copy
it three times.

That is why issue #41's design said "one module per verb" and the code said otherwise. Recorded
here rather than in a commit message, because the next person to look at this directory will ask
the same question.
"""

import argparse
import sys
from pathlib import Path

import yaml
from comeni_core import yaml_strict
from comeni_core.artifact.pipeline import Pipeline
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.replay import ReplayResolver
from mendel_resolver.router import UnroutableError

from mendel_compiler import orchestrate, pipeline_file, staging
from mendel_compiler.cli.artifact_verbs import _refuse_a_divergent_directory
from mendel_compiler.cli.report import (
    _displacement_line,
    _report_upgrade,
)
from mendel_compiler.emit import emit, emit_config, entry_params
from mendel_compiler.gates import (
    Gate,
    materialise_stub_data,
    materialise_test_samplesheet,
    run_gate,
)


def run(args, parser) -> int:
    """The shared flow. `args` is the parsed namespace; the verb is `args.command`.

    Takes the `parser` because `parser.error` is how a missing `--goal` is refused: it prints
    the usage line and exits 2, which is argparse's contract with the user. Building a second
    parser here to call `error` on would be a second usage string, and two would drift.
    """
    roots = args.registry or [args.root / "registry"]
    loaded = layers.load(roots)
    # **Only the registry survives here.** `vocabulary` and `rules` went with the resolve into
    # `orchestrate.build`; what the CLI still needs a registry for is `profile`, which reads the
    # ports of the contracts the IR actually chose. Ruff catching the other two unused is the
    # extraction being real rather than a re-export.
    registry = loaded.registry

    # **Reported here, refused in the seam.** Every diagnostic is printed including the
    # non-blocking `MD0100`s — a reader wants to know which contracts could not be re-read even
    # when the build proceeds — and then `orchestrate.build` raises on the blocking ones. The
    # printing is a transport's job and the refusal is not, which is the whole split phase 0
    # made: an HTTP caller needs the same no as a value, not as stderr and an exit code.
    for diagnostic in orchestrate.diagnostics_for(roots):
        print(diagnostic.render(), file=sys.stderr)

    previous: Pipeline | None = None
    resolver = None
    # A56. The evidence behind a replayed `source: HUMAN`, passed to `resolve()` separately
    # from the resolver that will claim it. A resolver cannot both assert that a person
    # answered and supply the proof; these records come from the file on disk.
    prior: list = []
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
        prior = list(previous.replayable_decisions())
        resolver = ReplayResolver(prior)
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
        # The self-overwrite check above only catches `--out` == the *source's* directory. A
        # `--out` that holds some *other* pipeline is just as destructive and was allowed: the
        # write replaced a third pipeline's `pipeline.yml`, overrides and gate evidence with no
        # trace it had ever been there (A53). Refuse a `--out` that already holds a pipeline
        # whose identity differs from the one being upgraded, unless `--force` says so.
        if args.out is not None and not args.force:
            occupant = args.out / pipeline_file.FILENAME
            if occupant.exists():
                existing = pipeline_file.load(occupant)
                if existing.content_digest() != previous.content_digest():
                    print(
                        f"mendel: --out {args.out} already holds a different pipeline. "
                        f"Upgrading into it would overwrite that pipeline's evidence. "
                        f"Choose an empty directory, or pass --force to replace it.",
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

    try:
        built = orchestrate.build(
            goal,
            registry_roots=roots,
            prior=prior,
            resolver=resolver,
        )
    except orchestrate.ConformanceRefused as refused:
        print(
            f"\nmendel: {refused}\n"
            f"`mendel explain {refused.blocking[0].code}` for the long form.",
            file=sys.stderr,
        )
        return 2
    ir, pipeline = built.ir, built.pipeline

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
    # **The layer carries the module now** (Plan 5A), so the source comes out of the same
    # `--registry` the contracts did rather than out of a `vendor/` in this repository. One
    # implementation, shared with the API's `keep`, which had no copy at all until `MD0210`
    # found it.
    staging.stage(pipeline, built.layers.modules, args.out)

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
        # **Both gates, and only `stub` was branched on.** A `test` run needs the
        # samplesheet the profile points at, and `-stub-run` needs it too — a stub
        # never reads its inputs but `splitCsv` runs before any process does.
        materialise_test_samplesheet(args.out, pipeline)
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

