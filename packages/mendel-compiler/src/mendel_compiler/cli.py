"""`mendel build` — goal in, pipeline directory out."""

import argparse
import shutil
import sys
from pathlib import Path

import yaml
from comeni_core.measurement import (
    BadMeasurementValueError,
    MeasurementRegistry,
    UnknownMeasurementError,
)
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import Goal
from mendel_resolver.resolve import resolve
from mendel_resolver.router import UnroutableError
from mendel_resolver.rules import RuleTable, RuleValidationError
from pydantic import ValidationError

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
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--goal", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
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

    # A layer is a directory, not a contracts folder: all three kinds of registry data
    # stack together, so a laboratory can ship its own types and rules alongside its
    # modules. Only contracts stacked before the 2026-08-03 audit.
    layers = args.registry or [args.root / "examples"]
    vocab = Vocabulary.load([layer / "vocabularies" for layer in layers])
    registry = Registry.load([layer / "contracts" for layer in layers], vocab)
    measurements = MeasurementRegistry.load([layer / "measurements" for layer in layers])
    rules = RuleTable.load(
        [layer / "rules" for layer in layers],
        registry=registry,
        vocabulary=vocab,
        measurements=measurements,
    )
    goal = Goal.model_validate(yaml.safe_load(args.goal.read_text()))

    # Re-build the goal's profile through the one constructor that validates it. The
    # mapping shorthand in the goal file cannot check itself — measurements are declared
    # data, so the model has no idea what is declared — and `profile: {sample_name: ...}`
    # is exactly the shape invariant 15 exists to refuse. This is the door.
    goal = goal.model_copy(
        update={
            "profile": measurements.profile(
                {m.measurement: m.value for m in goal.profile.measurements}
            )
        }
    )

    ir = resolve(goal, registry, rules)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "main.nf").write_text(emit(ir, registry, vocab))
    (args.out / "nextflow.config").write_text(emit_config(ir, registry, vocab))
    (args.out / "pipeline.ir.json").write_text(ir.model_dump_json(indent=2))
    # `nf_include` is where a module lands in the *generated* pipeline; `vendor/` is
    # where this repository keeps the source. Deliberately not the same path.
    vendored = args.root / "vendor" / "modules"
    if vendored.exists():
        shutil.copytree(vendored, args.out / "modules", dirs_exist_ok=True)

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


if __name__ == "__main__":
    raise SystemExit(main())
