"""`mendel build` — goal in, pipeline directory out."""

import argparse
import shutil
import sys
from pathlib import Path

import yaml
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import Goal
from mendel_resolver.resolve import resolve
from mendel_resolver.rules import RuleTable

from mendel_compiler.emit import emit, emit_config, entry_params
from mendel_compiler.gates import Gate, materialise_stub_data, run_gate


def main(argv: list[str] | None = None) -> int:
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
        help="a registry layer; repeat to stack overlays, later layers win",
    )
    args = parser.parse_args(argv)

    data = args.root / "examples"
    layers = args.registry or [data / "contracts"]

    vocab = Vocabulary.load(data / "vocabularies")
    registry = Registry.load(layers, vocab)
    rules = RuleTable.load(data / "rules" / "rnaseq.yml")
    goal = Goal.model_validate(yaml.safe_load(args.goal.read_text()))

    ir = resolve(goal, registry, rules)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "main.nf").write_text(emit(ir, registry, vocab))
    (args.out / "nextflow.config").write_text(emit_config(ir, registry, vocab))
    (args.out / "pipeline.ir.json").write_text(ir.model_dump_json(indent=2))
    if (args.root / "modules").exists():
        shutil.copytree(args.root / "modules", args.out / "modules", dirs_exist_ok=True)

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
