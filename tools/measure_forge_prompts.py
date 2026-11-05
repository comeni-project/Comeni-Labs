"""Measure the forge's question and review prompts before and after, as rates (#453).

`tools/measure_prompts.py` measures the builder's prompts; this replays one adaptation's own
request (its module, items and the registry, as `compose` builds it) under each prompt version,
`--runs` times, with the configured forge model. It makes real model calls and records each
as any call is recorded; nothing it replies is stored as a proposal or a review.

The checks are quast's walk (#412): `consensus` is one sample's assembly, `fasta` the reference
and `gff` a GFF annotation. Needs the database `.env` names and a forge model in Settings:

    uv run python tools/measure_forge_prompts.py <adaptation-id> --runs 5

`--model chatgpt/gpt-6.1-sol` measures another model than Settings names, for example a
ChatGPT subscription signed in through LiteLLM (#457), without changing Settings.
"""

import argparse
from collections import Counter

from comeni_ai import Client
from comeni_ai.access import ModelAccess
from comeni_core.declared.signature import split
from mendel_api.forge.replies import QuestionsReply, ReviewReply
from mendel_api.invocations import InvocationPurpose
from mendel_api.services import forging, forging_ai
from mendel_forge.forging.model import Piece

DRAFTERS = ("forge.questions.v4", "forge.questions.v5")
REVIEWERS = ("forge.review.v1", "forge.review.v2")


def _suggested(reply: QuestionsReply, name: str) -> str | None:
    for question in reply.questions:
        if question.key == f"questions:input_type:{name}" and question.suggested:
            try:
                return split(question.suggested)[0]
            except ValueError:
                return question.suggested
    return None


def drafter(adaptation_id: str, prompt: str, runs: int) -> Counter:
    """A first draft, as the walk's was: no items yet, so no findings to lean on."""
    adaptation = forging.row(adaptation_id)
    state = forging.load(adaptation_id).model_copy(update={"items": {}})
    client = forging_ai._client(InvocationPurpose.ANALYSIS)
    counts: Counter = Counter()
    for _ in range(runs):
        request = forging_ai.compose(adaptation, state, Piece.QUESTIONS, prompt=prompt)
        reply, _ = forging_ai._call(prompt, request, QuestionsReply, client, adaptation_id, 1,
                                    attempts=1)
        counts["runs"] += 1
        if reply is None:
            counts["unusable"] += 1
            continue
        consensus, fasta, gff = (_suggested(reply, n) for n in ("consensus", "fasta", "gff"))
        counts["consensus is not genome.fasta"] += consensus not in (None, "genome.fasta")
        counts["consensus and fasta differ"] += bool(consensus and fasta and consensus != fasta)
        counts["gff is not annotation.gtf"] += gff not in (None, "annotation.gtf")
    return counts


def reviewer(adaptation_id: str, prompt: str, runs: int) -> Counter:
    adaptation, state = forging.row(adaptation_id), forging.load(adaptation_id)
    client = forging_ai._client(InvocationPurpose.REVIEW)
    counts: Counter = Counter()
    for _ in range(runs):
        request = forging_ai.compose(adaptation, state, Piece.QUESTIONS, prompt=prompt)
        request = request.model_copy(update={"items": [
            i for i in request.items if i.key.startswith("questions:")]})
        sources = {"main.nf": request.module.main_nf, "meta.yml": request.module.meta_yml,
                   "tests/main.nf.test": request.module.nf_test}
        reply, _ = forging_ai._call(prompt, request, ReviewReply, client, adaptation_id, 1,
                                    attempts=1)
        counts["runs"] += 1
        counts["items"] += len(request.items)
        if reply is None:
            counts["unusable"] += 1
            continue
        counts["comments"] += len(reply.comments)
        counts["verbatim quote"] += sum(bool(c.quote) and c.quote in sources.get(c.file, "")
                                        for c in reply.comments)
        counts["names an engine finding's input"] += sum(
            any(n in c.comment for n in ("consensus", "fasta", "gff")) for c in reply.comments)
    return counts


def _rate(counts: Counter, key: str, of: str) -> str:
    total = counts[of]
    return f"{counts[key]}/{total} ({100 * counts[key] / total:.0f}%)" if total else "—"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("adaptation")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--model", help="a LiteLLM model id to measure instead of Settings'")
    parser.add_argument("--temperature", type=float, default=0.0,
                        help="with --model; a reasoning model accepts only 1")
    args = parser.parse_args()
    if args.model:
        access = ModelAccess(model=args.model, temperature=args.temperature)
        forging_ai._client = lambda _purpose: Client(access)
    print(f"model: {args.model or 'as Settings names it'}")
    for prompt in DRAFTERS:
        counts = drafter(args.adaptation, prompt, args.runs)
        print(f"\n{prompt}")
        for key in ("unusable", "consensus is not genome.fasta", "consensus and fasta differ",
                    "gff is not annotation.gtf"):
            print(f"  {key}: {_rate(counts, key, 'runs')}")
    for prompt in REVIEWERS:
        counts = reviewer(args.adaptation, prompt, args.runs)
        print(f"\n{prompt}")
        print(f"  unusable: {_rate(counts, 'unusable', 'runs')}")
        print(f"  comments per item: {_rate(counts, 'comments', 'items')}")
        print(f"  with a verbatim quote: {_rate(counts, 'verbatim quote', 'comments')}")


if __name__ == "__main__":
    main()
