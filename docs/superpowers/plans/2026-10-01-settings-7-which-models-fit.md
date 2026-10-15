# Settings 7 — which models fit the 8 GiB card, per purpose — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure gemma3:4b, qwen2.5:7b and gemma3:12b on the builder's real calls, per purpose, and set the model for each purpose through the settings menu, choosing with the operator from the numbers.

**Architecture:** A hand-run measuring tool, `tools/measure_models.py`, drives the running stack through its own APIs: it sets the default model with `PUT /api/settings/models.default`, starts a builder session per sentence, sends one scripted reply, waits for the session to settle, and reads every call's purpose, state, duration and tokens from `GET /api/pipeline/authoring/{id}/calls`. It prints one table per model. No model is called from a test; the numbers are recorded on #187, as `tools/probe_prompt_cache.py`'s were on issue 185.

**Tech Stack:** Python 3.12, httpx, the running stack (`make dev`, `make ai-up OLLAMA_GPU=rocm`), Ollama on the RX 7600.

**Spec:** `docs/superpowers/specs/2026-10-01-settings-design.md` (§10, part 14.7.5.7). Issue #187, part 14.7.5.7 of #181. Needs part 4 (connections and a model per purpose).

## Global Constraints

- **No model is pulled without the operator's OK.** gemma3:4b, qwen2.5:7b and gemma3:12b are already pulled (2026-09-29). Anything else is asked first, with its size.
- The tool changes the installation's default model while it runs and **puts back what was there** when it finishes, even after an error.
- Do not spam: one pass per model per sentence; a second pass only if the first is inconclusive, and say so.
- Measured on the operator's card; a number here is a fact about that card, not about the model.
- The operator chooses the model per purpose; the tool only measures.

## Review Focus

1. **A session that never settles** (a stuck job): the tool gives up after its ceiling, records the session as *timed out*, and moves on. Task 1.
2. **The default model restored after a crash:** the original value is put back in a `finally`. Task 1.
3. **A model that is not pulled:** the tool checks the connection's model list first and skips it with a message, rather than timing out on every sentence. Task 1.
4. **Comparing like with like:** every model gets the same sentences, the same scripted reply and the same family-step setting; the table prints the setting it ran with. Task 1.
5. **Card placement:** each model's CPU/GPU split from `ollama ps` is recorded beside its numbers, because a split model's time is the card's, not the prompt's. Task 2.

---

### Task 1: The measuring tool

**Files:**
- Create: `tools/measure_models.py`

**Interfaces:**
- Consumes: `PUT /api/settings/{key}`, `GET /api/settings` (part 2), `POST /api/settings/models.connections/items/{name}/models` (part 4), `POST /api/pipeline/authoring` (`beginAuthoring`, body `{"prompt": str}`), `GET /api/pipeline/authoring/{id}` (`row_version`, `phase`), `POST /api/pipeline/authoring/{id}/messages` (body `{"text": str}`), `GET /api/pipeline/authoring/{id}/calls` (`purpose`, `model`, `state`, `duration_ms`, `input`, `output`).

- [x] **Step 1: Write the tool**

```python
"""Measure which local model serves each builder purpose — issue 187, part 14.7.5.7.

Drives the running stack through its own APIs. For each model it sets the installation's default
model (Settings → Models), starts one builder session per sentence, answers the first question
with a fixed reply, waits for the session to settle, and reads every call it made. Prints, per
model and purpose: calls, admitted, refused, failed, and the median time and tokens.

    uv run python tools/measure_models.py --connection "Local Ollama" \
        ollama_chat/gemma3:4b ollama_chat/qwen2.5:7b ollama_chat/gemma3:12b

A measuring tool, run by hand; its numbers are recorded on issue 187. It puts the default model
back as it found it, even after an error.
"""

import argparse
import statistics
import sys
import time
from collections import defaultdict

import httpx

SENTENCES = (
    "gene counts from my RNA-seq",
    "gene counts from paired-end RNA-seq, 150 bp reads, against the human reference genome",
    "variant calls from my exomes",
)
"""The walk's sentences (#194, #198): a short one, a full one, and one no type fits."""

REPLY = "I have it"
SETTLE_SECONDS = 15
CEILING_SECONDS = 600


def _settled(http: httpx.Client, session: str) -> bool:
    """Settled when nothing has changed for `SETTLE_SECONDS`, or the session failed."""
    last, since, started = None, time.monotonic(), time.monotonic()
    while time.monotonic() - started < CEILING_SECONDS:
        view = http.get(f"/api/pipeline/authoring/{session}").json()
        calls = len(http.get(f"/api/pipeline/authoring/{session}/calls").json())
        now = (view["row_version"], calls)
        if view["phase"] == "failed":
            return True
        if now != last:
            last, since = now, time.monotonic()
        elif time.monotonic() - since >= SETTLE_SECONDS:
            return True
        time.sleep(2)
    return False


def _session(http: httpx.Client, sentence: str) -> tuple[list[dict], bool]:
    started = http.post("/api/pipeline/authoring", json={"prompt": sentence}).json()
    session = started["session"]["id"]
    done = _settled(http, session)
    if done:
        http.post(f"/api/pipeline/authoring/{session}/messages", json={"text": REPLY})
        done = _settled(http, session)
    return http.get(f"/api/pipeline/authoring/{session}/calls").json(), done


def _table(model: str, calls: list[dict], timed_out: int) -> str:
    by = defaultdict(list)
    for call in calls:
        by[call["purpose"]].append(call)
    lines = [f"\n## {model}" + (f"  ({timed_out} session(s) timed out)" if timed_out else ""),
             "| purpose | calls | admitted | refused | failed | median ms | median in | median out |",
             "|---|---|---|---|---|---|---|---|"]
    for purpose, rows in sorted(by.items()):
        states = [r["state"] for r in rows]
        med = lambda key: statistics.median([r[key] for r in rows if r[key] is not None] or [0])
        lines.append(
            f"| {purpose} | {len(rows)} | {states.count('succeeded')} | {states.count('refused')} "
            f"| {states.count('failed')} | {med('duration_ms'):.0f} | {med('input'):.0f} "
            f"| {med('output'):.0f} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+")
    parser.add_argument("--connection", required=True)
    parser.add_argument("--api", default="http://localhost")
    args = parser.parse_args()

    with httpx.Client(base_url=args.api, timeout=60) as http:
        menu = http.get("/api/settings").json()
        entries = {e["setting"]["key"]: e["shown"] for s in menu["sections"] for e in s["entries"]}
        before = entries["models.default"]
        if before["locked"]:
            print("models.default is pinned by .env; unset COMENI_AI_MODEL to measure", file=sys.stderr)
            return 2
        listed = http.post(
            f"/api/settings/models.connections/items/{args.connection}/models"
        ).json()["values"]
        # Not a setting (spec §7): the family step is whatever the api's environment says.
        print("family step: MENDEL_FAMILY_STEP_FROM as set in .env (record its value with these)")
        try:
            for model in args.models:
                if model not in listed:
                    print(f"\n## {model}\nskipped: not on {args.connection} ({', '.join(listed)})")
                    continue
                http.put(
                    "/api/settings/models.default",
                    json={"value": {"connection": args.connection, "model": model}},
                ).raise_for_status()
                calls, timed_out = [], 0
                for sentence in SENTENCES:
                    got, done = _session(http, sentence)
                    calls += got
                    timed_out += not done
                print(_table(model, calls, timed_out), flush=True)
        finally:
            if before["value"] is not None:
                http.put("/api/settings/models.default", json={"value": before["value"]})
                print(f"\ndefault model restored to {before['value']}")
            else:
                # A PUT of null is refused (MI0301), so an unset default cannot be put back.
                print("\nthe default was unset; set it again in Settings → Models if it should be")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 2: Check it**

Run: `uv run ruff check tools/measure_models.py && uv run python tools/measure_models.py --help`
Expected: clean; the usage line

- [x] **Step 3: Commit**

```bash
git add tools/measure_models.py
git commit -m "tools: measure which model serves each builder purpose (#187)"
```

---

### Task 2: Measure

- [x] **Step 1: Prepare, with the operator**

Ask the operator: the default model must not be pinned by `.env` while measuring (the tool refuses if it is). If `COMENI_AI_MODEL` is set, they comment it out and restart, or say to skip. Then: `make ai-up OLLAMA_GPU=rocm`, `make dev`, and in Settings → Models a *Local Ollama* connection at `http://ollama:11434` (from part 4's walk).

- [x] **Step 2: Run it**

Run: `uv run python tools/measure_models.py --connection "Local Ollama" ollama_chat/gemma3:4b ollama_chat/qwen2.5:7b ollama_chat/gemma3:12b 2>&1 | tee /tmp/claude-1000/measure-models.txt`
Expected: three tables. If any session timed out, say which and why before deciding whether to rerun it; do not rerun silently.

While each model runs, record its placement once: `docker exec mendel-ollama ollama ps` (container name from `.env.example`'s `OLLAMA_CONTAINER_NAME`).

- [x] **Step 3: Record it on #187**

Comment on #187: the three tables, each model's `ollama ps` line, the family-step setting, the sentences, and the date. No interpretation in the same comment.

---

### Task 3: Choose, with the operator, and set it

- [x] **Step 1: Present the choice**

For each purpose (understanding what you want, talking with you, choosing where the rules cannot, reading the plan back, adapting tools), one line: the fastest model whose admitted rate matches the best one, and the cost of the next option. Present it as choices with their costs (`present-decisions-as-choices`). The operator picks.

- [x] **Step 2: Set it in the menu**

In Settings → Models, choose each purpose's model as decided. Check Privacy & data → *Where each purpose goes* says every purpose stays on this machine.

- [x] **Step 3: Record the decision and close**

Comment on #187 with the decision (label `decided`), what is now set, and that `.env`'s `COMENI_AI_MODEL` can go back as the default if the operator wants it pinned. Close #187. Update `docs/notes/now.md`'s model line if it names a model.

---

## Execution record

Executed 2026-10-01, in one hand; #187 closed with the decision.

- **Ruling:** the tool points the five purpose settings at each model rather than the default,
  because the default is pinned by the operator's `.env` and the purposes are not. Nothing in
  `.env` changed, and each purpose was put back as found.
- **Found while writing the tool, fixed on the spot:** *Same as the default* sent `null`, which
  the API refused (`MI0301`), so a purpose could never go back to the default. Only a missing
  value is `MI0301` now; `null` is the setting's own check.
- **Measured** (3 models × 3 sentences, one reply; numbers on #187): no call refused or failed.
  gemma3:4b and qwen2.5:7b fit the card (100% GPU) and answered in about 0.5–2.8 s;
  gemma3:12b runs 36% on the CPU and took 2.8–7.3 s. Only *family*, *goal*, *ask* and *gap* were
  exercised; tier 4, read-back and the forge were not. Well-formed is not correct: accuracy is
  #198.
- **Decided** (operator, option C): the want stays on gemma3:12b until #198; talking with you and
  reading the plan back on gemma3:4b; tier 4 and the forge on the default.
- No fresh review: a hand-run measuring tool and a one-line, tested route change.
