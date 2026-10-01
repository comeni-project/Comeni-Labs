# 2026-09-29 — 14.7.4, the consultant's words, fast and cheap

## Where things stand

- **14.7.4 parts 1–4 are built and walked.** The four plans in `docs/superpowers/plans/` named
  `2026-09-29-14.7.4.*` are all ticked, each with an execution record. `make check`: 2,870
  passed; the 5 failures are the known ones (`test_forge_jobs.py` ×4 and
  `test_full_cycle::test_the_loop_closes`). Guards, slow and the doc checks pass.
- **Issue #180 (14.7.4) stays open** with #192, #193, #194 and #195 under it:
  `gh api repos/:owner/:repo/issues/180/sub_issues`.
- **Local models:** `gemma3:12b`, `gemma3:4b` and `qwen2.5:7b` are in the Ollama volume
  (`docker exec mendel-ollama ollama list`). Only `gemma3:12b` is configured.
- **Model server:** Ollama `0.34.4-rocm` (the operator's `.env`), `OLLAMA_KEEP_ALIVE=1h`,
  `OLLAMA_NUM_PARALLEL=1`.

## What changed

- **Part 1, keep and show each call** (9a1dfe4..988a750). Every builder call stores its reply,
  session and cached tokens. The session view carries a `usage` total on the existing poll. The
  header counts tokens and calls and opens the call list (`GET /authoring/{id}/calls`, fetched
  only when the panel opens).
- **Part 2, the model server** (bc6c2e8, 7a50f62). Compose defaults for keep-alive and one slot,
  and a probe, `tools/probe_prompt_cache.py`.
- **Part 3, the split** (172caff..cc3d643). Prompts are sent as a fixed system message and a
  per-call user message, with the cache marker used for Anthropic only. goal.v5, chat.v2, gap.v2
  and tier4.v2.
- **Part 4, the consultant's words** (a8ca4fd..80da9b1).
  - `goal.v6` only acknowledges, and its constraints become suggestions.
  - `builder.ask.v1` phrases each gap, prefetched per subject.
  - `builder.readback.v1` reads back the composed goal.
  - The loosening is recorded in `docs/design/authoring-protocol.md` (fd7eb7a).

## Decisions, and why

- **What the model server does is the deployment's business.** The app sends no keep-alive and
  assumes no slot count. Docker sets defaults and Kubernetes will set its own (operator).
- **Phrasing and the read-back are prose inside the authoring AI point, not a new `AiPoint`.**
  They produce no value the engine uses; the person's click still makes every fact.
- **A fact the person stated wins** over the phrasing model's guess at what they said earlier.
- **#180 stays open** while findings sit under it, although the plan said to close it once parts
  1–4 were done.

## Measured

| | Time |
|---|---|
| Identical prompt, 0.6.5 → 0.34.4 | 11.2 s → 0.4 s |
| Shared fixed part, before → after the split | 24.2 s → 1.2 s |

| Model on the RX 7600 (8 GiB) | Placement | Generation |
|---|---|---|
| gemma3:4b | 100% GPU | 73 tok/s |
| qwen2.5:7b | 100% GPU | 52 tok/s |
| gemma3:12b | 36%/64% CPU/GPU | 13.5 tok/s |

One session costs about 9k input tokens:

| Call | Input tokens |
|---|---|
| Reading the request (mostly the vocabulary) | ~3.4k |
| Six phrasings, ~850 each | ~5.1k |
| Read-back | ~0.5k |

On a hosted model that is 1–3 cents. Locally the cost is time, so model size matters more than
the token count.

## What is next, in the operator's order

1. **#194**: the phrasing call echoes its schema on sparse sentences. Strip the schema's
   `description` keys before they reach the model; this also cuts tokens on every structured
   call.
2. **The visual check** of the call panel, the header count, the phrased gap card, the read-back
   and the suggested row. It was pending because the Chrome extension was disconnected.
3. **Report back to the operator before 14.7.5**, the settings menu, which picks a model per
   purpose (#117, #187). It starts with a brainstorm.
4. **A token-budget brainstorm.** Options: phrase all gaps in one call (about 4k fewer tokens per
   session, but no per-question prefetch), or send only part of the vocabulary to the want call
   (a protocol question, because the model cannot choose what it is not shown). It should cover
   #195 as well.

## Open questions

- **#193:** a fact the model reports as stated reads as the person's own ("you mentioned it").
- **#195:** phrased questions call a kind of file by its id ("the file named genome.fasta").
- **#192:** a fresh prompt reads slower on 0.34.4. Much of that is probably the 12B model
  spilling onto the CPU.

## Traps

- **`cached` reads 0 on Ollama.** LiteLLM reports no cached tokens for `ollama_chat`. On the local
  lane, reuse shows only as speed.
- **A walk script that answers instantly measures phrasing latency, not prefetch.** Pace it
  (about 10 s per answer) to see prefetch land.
- **The first call after a rebuild is a cold load:** about 70 s against 7.6 s warm.
