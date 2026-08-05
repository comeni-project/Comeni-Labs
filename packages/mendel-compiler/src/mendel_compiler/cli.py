"""`mendel build` — goal in, pipeline directory out; `mendel profile` — measure first."""

import argparse
import shutil
import sys
from pathlib import Path

import yaml
from comeni_core.egress import PublishBundle
from comeni_core.lockfile import Lockfile
from comeni_core.measurement import BadMeasurementValueError, UnknownMeasurementError
from mendel_resolver import layers
from mendel_resolver.diff import diff_ir
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.replay import ReplayResolver
from mendel_resolver.resolve import resolve
from mendel_resolver.router import UnroutableError
from mendel_resolver.rules import RuleValidationError
from pydantic import ValidationError

from mendel_compiler import conformance
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
    except (OSError, KeyError) as exc:
        print(f"mendel: {exc}", file=sys.stderr)
    return 2


def _build(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mendel")
    parser.add_argument(
        "command", choices=["build", "profile", "publish", "upgrade", "explain"]
    )
    parser.add_argument(
        "code", nargs="?", default=None, help="a diagnostic code, for `explain`"
    )
    parser.add_argument("--goal", type=Path, default=None)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="a published pipeline.bundle.json to re-resolve. `upgrade` only.",
    )
    parser.add_argument(
        "--have",
        action="append",
        default=None,
        help="a type id the laboratory holds; repeat. `profile` only.",
    )
    # Not `required=True`: `mendel explain M0104` writes nothing and loads nothing, so
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
        if not args.code:
            parser.error("explain needs a code, e.g. `mendel explain M0104`")
        print(conformance.explain(args.code))
        return 0

    if args.out is None:
        parser.error(f"{args.command} needs --out")

    # A layer is a directory, not a contracts folder: all three kinds of registry data
    # stack together, so a laboratory can ship its own types and rules alongside its
    # modules. Only contracts stacked before the 2026-08-03 audit.
    loaded = layers.load(args.registry or [args.root / "examples"])
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
    unverified = [d.contract_id for d in diagnostics if d.code == "M0100"]
    blocking = [d for d in diagnostics if d.code != "M0100"]
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

    previous: PublishBundle | None = None
    resolver = None
    if args.command == "upgrade":
        # An upgrade reads its goal from the bundle rather than from a file: re-resolving
        # a *different* goal and calling the result an upgrade is how "only what you
        # touched moved" would quietly become false.
        if args.bundle is None:
            parser.error("upgrade needs --bundle")
        previous = PublishBundle.model_validate_json(args.bundle.read_text())
        goal = previous.goal
        resolver = ReplayResolver(previous.decisions)
    elif args.command == "profile":
        goal = _profiling_goal(args, loaded)
    else:
        if args.goal is None:
            parser.error(f"{args.command} needs --goal")
        goal = Goal.model_validate(yaml.safe_load(args.goal.read_text()))
        # Re-build the goal's profile through the one constructor that validates it. The
        # mapping shorthand in the goal file cannot check itself — measurements are
        # declared data, so the model has no idea what is declared — and
        # `profile: {sample_name: ...}` is exactly the shape invariant 15 refuses.
        goal = goal.model_copy(
            update={
                "profile": loaded.measurements.profile(
                    {m.measurement: m.value for m in goal.profile.measurements}
                )
            }
        )

    ir = resolve(
        goal,
        registry,
        rules,
        resolver=resolver,
        layer_names=[p.name for p in loaded.paths],
    )
    ir.unverified = unverified

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "main.nf").write_text(emit(ir, registry, vocab, loaded.measurements))
    (args.out / "nextflow.config").write_text(emit_config(ir, registry, vocab))
    (args.out / "pipeline.ir.json").write_text(ir.model_dump_json(indent=2))
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

    if args.command == "publish":
        # Federation §4.1: a shareable pipeline is what was asked for, what it resolved
        # to, why each choice was made, and against exactly which registry. All four, or
        # the recipient can neither reproduce it nor audit it.
        #
        # This writes files and sends nothing. Transmitting them is a later, separate act,
        # which is the right shape for the door with no undo: a person can read what they
        # are about to publish.
        lockfile = Lockfile.of(ir, registry, loaded.paths)
        bundle = PublishBundle(
            goal=goal, ir=ir, decisions=ir.decisions, lockfile=lockfile
        )
        (args.out / "pipeline.bundle.json").write_text(bundle.model_dump_json(indent=2))
        (args.out / "mendel.lock.yml").write_text(
            yaml.safe_dump(lockfile.model_dump(mode="json"), sort_keys=True)
        )

    if previous is not None:
        # Nothing upgrades implicitly. Drift is what the registry did underneath the
        # lockfile; changes are what that did to *this* pipeline. Both, because a contract
        # can be edited in ways that change nothing here — and the lockfile no longer
        # describing what is on disk is still worth knowing.
        for line in previous.lockfile.drift_against(ir, registry, loaded.paths):
            print(f"  DRIFT   {line}", file=sys.stderr)
        changes = diff_ir(previous.ir, ir)
        if not changes:
            print("no changes: this pipeline re-resolves identically", file=sys.stderr)
        for change in changes:
            print(f"  CHANGED {change}", file=sys.stderr)
        if resolver is not None:
            print(
                f"{len(resolver.replayed)} decisions replayed, "
                f"{len(resolver.fresh)} newly asked",
                file=sys.stderr,
            )

    for record in registry.shadowed:
        print(
            f"  SHADOW  {record.module_key}: {record.winning_id} from {record.winning_layer} "
            f"displaced {', '.join(record.displaced_ids)}",
            file=sys.stderr,
        )

    flagged = ir.needs_review()
    print(f"{len(ir.nodes)} modules, {len(flagged)} requiring review", file=sys.stderr)
    for item in flagged:
        print(f"  REVIEW  {item}", file=sys.stderr)

    if args.gate is not None:
        if args.gate is Gate.STUB:
            materialise_stub_data(args.out, entry_params(ir, registry, vocab))
        result = run_gate(args.gate, args.out)
        print(f"gate {result.gate}: {'PASS' if result.passed else 'FAIL'}", file=sys.stderr)
        if not result.passed:
            print(result.output, file=sys.stderr)
            return 1
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


if __name__ == "__main__":
    raise SystemExit(main())
