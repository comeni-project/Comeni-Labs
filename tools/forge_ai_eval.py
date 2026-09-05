"""§5.9's evaluation corpus: the cases, their answer keys, and the scorer over them.

    make forge-ai-eval          # build the corpus from the registry and report what it covers
    make forge-ai-eval ARGS=--json

**The corpus is landed contracts with their answers hidden.** For each case the forge adapts the
upstream source as if for the first time, and the contract a human already approved is the
answer key. That is the only way to measure a prompt without a person reading every response,
and the registry is the only place a known-good answer exists.

**What this command does today is build and check the answer keys.** It does not call a model,
and there is no `MODEL=` switch, because generating a response needs the AI worker that Task 7
builds — and six hand-written "recorded" responses would measure this harness rather than any
prompt, while looking exactly like a measurement. The number that matters arrives with the
worker; what arrives now is everything needed to produce it, checkable on its own.

So the useful output is: which cases have an answer key, how many holes each one would put to a
model, and how many of those the registry can actually judge. A case whose answer key covers
three of eleven holes is a case that would report a precision figure over three answers, and
knowing that before running a model is worth more than the figure.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "mendel-forge" / "src"))

from mendel_forge.ai.evaluate import expected_from  # noqa: E402
from mendel_resolver import layers  # noqa: E402

CASES: tuple[tuple[str, str, str], ...] = (
    ("nfcore_fastqc", "nf-core/fastqc", "multiple reports from one reads input"),
    ("nfcore_samtools_sort", "nf-core/samtools/sort", "same type in and out, changed state"),
    ("nfcore_star_align", "nf-core/star/align", "many outputs and multi-input plumbing"),
    (
        "nfcore_subread_featurecounts",
        "nf-core/subread/featurecounts",
        "joined and broadcast inputs, routed params",
    ),
    ("pegi3s_fastqc", "", "container-only source needing a wrapper"),
    ("pegi3s_weak", "", "weak documentation — must stay unresolved"),
)
"""§5.9's six, and the last two have no answer key by design.

`pegi3s_weak` is **not supposed to acquire one**. It passes when the model declines, and a run
in which it is answered confidently has found the failure the whole corpus exists to detect — a
model filling a gap because a gap was presented to it. Scoring it as a case with zero correct
answers would make the honest outcome look like the worst one.

`pegi3s_fastqc` has no landed contract to compare against either, and that is the harder gap:
the tool is the same fastqc, but a PEGiS wrapper's ports are not nf-core's, so borrowing that
answer key would score a correct proposal as wrong. It is measured on the zero-gate rows —
invented citations, mutated facts, answers outside a candidate set — and not on precision.
"""


def _contracts(stack) -> dict[str, object]:
    return {
        contract.id.split("@")[0]: contract for contract in stack.registry.contracts.values()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="build and check §5.9's evaluation corpus")
    parser.add_argument("--registry", type=Path, default=ROOT / "registry")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    stack = layers.load(args.registry)
    landed = _contracts(stack)

    rows = []
    for case, contract_id, note in CASES:
        contract = landed.get(contract_id) if contract_id else None
        expected = expected_from(contract) if contract is not None else {}
        rows.append(
            {
                "case": case,
                "contract": contract_id or "(none — scored on the zero-gate rows only)",
                "note": note,
                "answer_key": len(expected),
                "keys": sorted(expected),
                "missing_contract": bool(contract_id) and contract is None,
            }
        )

    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print(f"§5.9 corpus, against {args.registry}\n")
        for row in rows:
            state = "NO CONTRACT" if row["missing_contract"] else f"{row['answer_key']} keys"
            print(f"  {row['case']:<30} {state:<14} {row['note']}")
        print(
            "\nNo model is called. Generating a response needs Task 7's AI worker; six\n"
            "hand-written recorded responses would measure this harness rather than any\n"
            "prompt, while looking exactly like a measurement."
        )

    absent = [row["case"] for row in rows if row["missing_contract"]]
    if absent:
        print(f"\nthese cases name a contract the registry does not have: {absent}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
