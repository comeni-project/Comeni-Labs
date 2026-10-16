"""Measure a prompt change on the walks' own sentences, before and after (#327).

Runs each case through the builder's real calls (`understand`, `follow_up`, `phrase_gap`),
once per prompt set, and checks what each reply says. `tools/measure_models.py` compares models
through the API; this compares prompt versions, which the API cannot switch, so it runs
in-process. It makes real model calls and records them as any call is recorded.

Needs the configured model (`COMENI_AI_*` or Settings) and the database `.env` names:

    uv run python tools/measure_prompts.py --runs 3
"""

import argparse
import re
import sys
from collections import Counter
from collections.abc import Callable

from mendel_api.authoring import prompts
from mendel_api.authoring.types import FactKind
from mendel_api.services import authoring_ai as ai
from mendel_api.services import gaps, registry
from mendel_api.services.authoring_jobs import _client
from mendel_api.stages import gathering

SETS = {
    "before": {"GOAL": "builder.goal.v8", "CHAT": "builder.chat.v5", "ASK": "builder.ask.v2"},
    "after": {"GOAL": "builder.goal.v9", "CHAT": "builder.chat.v6", "ASK": "builder.ask.v3"},
}
"""The prompt sets compared: the walks ran `before`."""

CLAIM = re.compile(r"\b(I'?ve|I have|I'll|I will|I)\s+(recorded|saved|noted|set|added)\b", re.I)
PROMISE = re.compile(r"(recorded that you want|will (do|run|perform|add|include))", re.I)
STOCK = "I cannot see that from here"


def _facts(reply) -> dict:
    return {f.subject: f for f in reply.facts}


def _say_ok(reply) -> list[str]:
    said = reply.say or ""
    return [m for m, bad in (("claims to record", CLAIM.search(said)),
                             ("promises", PROMISE.search(said)),
                             ("stock sentence", STOCK in said)) if bad]


def goal_two_by_hundred(stack, client):
    """Walk 1 and 2: *2x100 bp* went unread."""
    out = ai.understand(ai.compose(prompt="Gene counts from paired-end RNA-seq of mouse liver, "
                                          "2x100 bp reads."),
                        stack=stack, families=["counts"], client=client)
    if not out.admitted:
        return [f"refused {out.code}"]
    fact = _facts(out.reply).get("read_length")
    return [] if fact is not None and fact.value in (100, "100") else ["read length not read"]


def goal_not_offered(stack, client):
    """Walk 2: *I've recorded that you want differential expression*, nothing under not_offered."""
    out = ai.understand(ai.compose(prompt="Gene counts from paired-end RNA-seq of mouse liver, "
                                          "then differential expression between fed and fasted "
                                          "mice."),
                        stack=stack, client=client)
    if not out.admitted:
        return [f"refused {out.code}"]
    return (["nothing not_offered"] if not out.reply.not_offered else []) + _say_ok(out.reply)


def _chat(stack, client, text, open_question=None, steps=()):
    return ai.follow_up(ai.compose(prompt=text, steps=steps), stack=stack,
                        open_question=open_question, client=client)


def chat_read_length(stack, client):
    """Walk 1: an invented setting; walk 2: *Okay, I've recorded that.*"""
    out = _chat(stack, client, "I already said: 2x100, so 100 bp", open_question="read_length")
    if not out.admitted:
        return [f"refused {out.code}"]
    fact = _facts(out.reply).get("read_length")
    found = [] if fact is not None and fact.value in (100, "100") else ["read length not a fact"]
    return found + (["a setting"] if out.reply.parameters else []) + _say_ok(out.reply)


def chat_not_offered(stack, client):
    """Walks 1 and 2: promised, or asked about, differential expression."""
    out = _chat(stack, client, "also I want differential expression between fed and fasted mice")
    if not out.admitted:
        return [f"refused {out.code}"]
    return ((["nothing not_offered"] if not out.reply.not_offered else [])
            + (["asks about it"] if out.reply.questions else []) + _say_ok(out.reply))


STEPS = (("star_align", "nf-core/star/align@1.11.0"), ("trimgalore", "nf-core/trimgalore@0.6.10"))


def chat_mid_build(stack, client):
    """Walk 2: the type `measurement.read_length` for the measurement, as a retract and a want."""
    out = _chat(stack, client, "actually the reads are 50 bp", steps=STEPS)
    if not out.admitted:
        return [f"refused {out.code}"]
    fact = _facts(out.reply).get("read_length")
    found = [] if fact is not None and fact.value in (50, "50") else ["read length not a fact"]
    mistaken = any("measurement." in str(getattr(i, "type", "") or getattr(i, "subject", ""))
                   for i in [*out.reply.wants, *out.reply.retract])
    return found + (["a type for the fact"] if mistaken else []) + _say_ok(out.reply)


def chat_quoted(stack, client):
    """Walk 1: *read length is 50* came back unquoted, so it could not be heard."""
    out = _chat(stack, client, "sorry, I was wrong earlier: read length is 50", steps=STEPS)
    if not out.admitted:
        return [f"refused {out.code}"]
    fact = _facts(out.reply).get("read_length")
    if fact is None:
        return ["read length not a fact"]
    return [] if fact.quote and "50" in fact.quote else ["not quoted"]


def ask_strandedness(stack, client):
    """Walk 1 and 2: *how … was determined …, choosing from forward, reverse, unstranded, …*."""
    # Strandedness is no longer a gathering gap (#338); the question is phrased directly.
    found = gaps.Gap(FactKind.MEASUREMENT, "strandedness", "a step reads it to decide")
    options = gathering._gap_options(found, stack, [])
    asks = gathering._gap_question(found, options, stack, 1).asks
    out = ai.phrase_gap(ai.compose(prompt="Gene counts from paired-end RNA-seq of yeast.",
                                   options=list(options)),
                        gap={"subject": "strandedness", "kind": "measurement", "asks": asks,
                             "description": "Library strandedness", "options": options},
                        stack=stack, client=client)
    if not out.admitted:
        return [f"refused {out.code}"]
    said = out.reply.asks.lower()
    return ((["asks how"] if "determined" in said or "how" in said.split()[:3] else [])
            + (["lists answers"] if any(v in said for v in ("forward", "reverse", "unstranded"))
               else []))


CASES: dict[str, Callable] = {
    "goal: 2x100 bp": goal_two_by_hundred,
    "goal: not offered": goal_not_offered,
    "chat: read length": chat_read_length,
    "chat: not offered": chat_not_offered,
    "chat: mid-build fact": chat_mid_build,
    "chat: quoted fact": chat_quoted,
    "ask: strandedness": ask_strandedness,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", choices=sorted(SETS), help="one prompt set, not both")
    args = parser.parse_args()
    client = _client(ai.Purpose.CHAT)
    if client is None:
        print("no model is configured: set COMENI_AI_MODEL or Settings → Models", file=sys.stderr)
        return 2
    stack = registry.stack()
    for name in [args.only] if args.only else list(SETS):
        for constant, prompt_id in SETS[name].items():
            setattr(prompts, constant, prompt_id)
        prompts.GOAL_ONE_STEP = prompts.GOAL
        print(f"\n## {name}: {', '.join(SETS[name].values())}")
        for case, run in CASES.items():
            failures: Counter = Counter()
            passed = 0
            for _ in range(args.runs):
                found = run(stack, client)
                passed += not found
                failures.update(found)
            detail = ", ".join(f"{k} ×{v}" for k, v in failures.most_common())
            print(f"{case:24} {passed}/{args.runs}  {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
