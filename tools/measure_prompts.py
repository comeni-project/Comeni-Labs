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
    "before": {"GOAL": "builder.goal.v9", "CHAT": "builder.chat.v6", "ASK": "builder.ask.v3"},
    "after": {"GOAL": "builder.goal.v9", "CHAT": "builder.chat.v7", "ASK": "builder.ask.v3"},
}
"""The prompt sets compared: walk 4 ran `before` (#354). #327 compared goal.v8, chat.v5 and
ask.v2 with what is now `before`."""

CLAIM = re.compile(r"\b(I'?ve|I have|I'll|I will|I)\s+(recorded|saved|noted|set|added)\b"
                   r"|[—-]\s*(recorded|saved|noted)\b|\bis now\b", re.I)
PROMISE = re.compile(r"(recorded that you want|will (do|run|perform|add|include))", re.I)
STOCK = "I cannot see that from here"
ADD_STEP = re.compile(r"\badd (a |another |the )?steps?\b|need to add|(can|could) add", re.I)
ACCEPTS = re.compile(r"\b(got it|understood|okay|noted|updated|corrected|changed it|will use)\b",
                     re.I)


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
    # A question about the request is the walks' failure; another question (the replay sends no
    # goal, so `purpose` is open) is counted apart, not as that failure.
    about = [q for q in out.reply.questions if "differential" in q.asks.lower()]
    return ((["nothing not_offered"] if not out.reply.not_offered else [])
            + (["asks about it"] if about else [])
            + (["asks something else"] if len(out.reply.questions) > len(about) else [])
            + _say_ok(out.reply))


STEPS = (("star_align", "nf-core/star/align@1.11.0"), ("trimgalore", "nf-core/trimgalore@0.6.10"))


def chat_mid_build(stack, client):
    """Walk 2: the type `measurement.read_length` for the measurement, as a retract and a want;
    walk 3: as a requirement."""
    out = _chat(stack, client, "actually the reads are 50 bp", steps=STEPS)
    if not out.admitted:
        return [f"refused {out.code}"]
    fact = _facts(out.reply).get("read_length")
    found = [] if fact is not None and fact.value in (50, "50") else ["read length not a fact"]
    mistaken = any("measurement." in str(getattr(i, "type", "") or getattr(i, "subject", ""))
                   for i in [*out.reply.wants, *out.reply.retract, *out.reply.requires])
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


WALK3_TAIL = (
    ("person", "Gene counts from paired-end RNA-seq of yeast."),
    ("model", "Gene counts from paired-end RNA-seq of yeast — got it."),
    ("model", "5 steps; 1 needs you."),
    ("person", "also I want differential expression between fed and fasted yeast"),
    ("model", "Differential expression between fed and fasted yeast is not offered here. The "
              "current pipeline builds a gene counts matrix."),
)
WALK3_STEPS = (("star_genomegenerate", "nf-core/star/genomegenerate@1.11.0"),
               ("trimgalore", "nf-core/trimgalore@0.6.10"),
               ("star_align", "nf-core/star/align@1.11.0"),
               ("samtools_sort", "nf-core/samtools/sort@1.21.0"),
               ("subread_featurecounts", "nf-core/subread/featurecounts@2.0.6"))
WALK3_GOAL = {"have": [{"type_id": t} for t in ("annotation.gtf", "fastq.reads", "genome.fasta")],
              "want": ["counts.matrix"],
              "profile": {"measurements": [
                  {"measurement": "paired", "value": True, "source": "goal"},
                  {"measurement": "quality_encoding", "value": "phred33", "source": "measured"},
                  {"measurement": "read_length", "value": 101, "source": "measured"},
                  {"measurement": "strandedness", "value": "reverse", "source": "goal"}]}}
WALK3_MEMORY = """What is known (recorded; do not ask for it again):

What you want:
- gene counts matrix · you said · "Gene counts"

Inputs you have:
- gene annotation (GTF) · you said
- sequencing reads (FASTQ) · measured from your sample
- reference genome (FASTA) · you said

Facts about your data:
- paired: yes · you said · "paired-end"
- quality encoding: phred33 · measured from your sample
- read length: 101 · measured from your sample
- strandedness: reverse · you said

The goal is confirmed; changes are offered to the person before they apply."""
"""Walk 3's call when *read length is 50* was typed, as `describe.turn_context` built it: the
sample had measured 101 and the build was complete."""


def chat_contradicts_measured(stack, client):
    """Walk 3: *read length is 50* against a measured 101 came back as the type
    `measurement.read_length` required, then as a retraction, each with *— noted.* The person's
    value is handed over as a fact; the engine asks *are you sure?* (#345)."""
    out = ai.follow_up(ai.compose(prompt="sorry, I was wrong earlier: read length is 50",
                                  turns=WALK3_TAIL, goal=gathering.as_goal(WALK3_GOAL),
                                  steps=WALK3_STEPS),
                       stack=stack, memory=WALK3_MEMORY, client=client)
    if not out.admitted:
        return [f"refused {out.code}"]
    fact = _facts(out.reply).get("read_length")
    mistaken = any("measurement." in str(getattr(i, "type", "") or getattr(i, "subject", ""))
                   for i in [*out.reply.wants, *out.reply.retract, *out.reply.requires])
    return ((["no fact of 50"] if fact is None or fact.value not in (50, "50") else [])
            + (["retracts it"] if any(i.subject == "read_length" for i in out.reply.retract)
               else [])
            + (["a type for the fact"] if mistaken else []) + _say_ok(out.reply))


def _walk3(stack, client, text, tail=WALK3_TAIL):
    return ai.follow_up(ai.compose(prompt=text, turns=tail, goal=gathering.as_goal(WALK3_GOAL),
                                   steps=WALK3_STEPS),
                        stack=stack, memory=WALK3_MEMORY, client=client)


def chat_no_step_to_add(stack, client):
    """Walk 4: *To perform differential expression, you would need to add a step for that
    analysis.* — no step can be added for what nothing here makes."""
    out = _walk3(stack, client, "also I want differential expression between fed and fasted yeast",
                 tail=WALK3_TAIL[:3])
    if not out.admitted:
        return [f"refused {out.code}"]
    return ((["nothing not_offered"] if not out.reply.not_offered else [])
            + (["suggests adding a step"] if ADD_STEP.search(out.reply.say or "") else [])
            + _say_ok(out.reply))


def chat_does_not_accept(stack, client):
    """Walk 4: *Read length is 50 — got it.* above the engine's *Are you sure?* (#345). A value
    against the record is the engine's to question, so the reply does not accept it first."""
    out = _walk3(stack, client, "sorry, I was wrong earlier: read length is 50")
    if not out.admitted:
        return [f"refused {out.code}"]
    fact = _facts(out.reply).get("read_length")
    said = out.reply.say or ""
    return ((["no fact of 50"] if fact is None or fact.value not in (50, "50") else [])
            + (["accepts it"] if ACCEPTS.search(said) else [])
            # The prompt's example measured 150 and was told 75; its numbers are not these.
            + (["copies the example"] if re.search(r"\b(150|75)\b", said) else []))


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
    "chat: against measured": chat_contradicts_measured,
    "chat: no step to add": chat_no_step_to_add,
    "chat: does not accept": chat_does_not_accept,
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
