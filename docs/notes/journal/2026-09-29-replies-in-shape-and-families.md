# 2026-09-29 — replies in the right shape, and types chosen by family

## Where things stand

- **14.7.4 parts 5 and 6 are built and walked.** Their plans are ticked with execution records,
  and #194 is closed.
- **`comeni-registry` has an unpushed branch, `families` (`c7208bd`)**, branched from the
  submodule's `bdd4c72`. `registry/` and the stack's `.run/registry` clone both point at it.
  Pushing is the operator's call; until then, a fresh clone of this repository has a `registry/`
  pointer GitHub does not hold.
- **`make check`** reports the 5 known failures and 1 strict xfail (#201).

## What changed

- **Part 5** (6fee2d2 → 40b41bf):
  - `comeni_ai/formats.py`: one `ReplyFormat` per provider, and a factory. Ollama is on; OpenAI
    and Anthropic are scaffolds, switched off.
  - Allowed lists go only into an enforced format.
  - `ai_invocation.reply_format`, migration `c3e8f1a57d20`.
- **Part 6** (d2a58fb → 7a85ec3):
  - `declares: family` and `MD0316`; the loader holds every type to a family.
  - `builder.family.v1` then `builder.goal.v7`; `goal.v6` stays live as the one-step path
    (`MENDEL_FAMILY_STEP_FROM`).
  - A `family` node in the protocol, and the diagram regenerated.

## Decisions, and why

- **The allowed lists are never written into an in-prompt schema.** The prompt's own text
  already lists the options, and writing them in the schema too moved every recorded fixture's
  key.
- **The api test suite runs one step by default.** Nearly every test feeds the goal answer first.
  The family step is covered by its own tests and by the walk.

## Measured (gemma3:12b, three sentences, paced)

| Setup | Refused | Input per session |
|---|---|---|
| Before (schema written into the prompt) | 4 of 18 phrasings | ~9k |
| Format enforced (part 5) | 0 of 24 calls | ~4.5k |
| Family step on (part 6) | 0 of 27 calls | ~4.7k (+~200 at 22 types; built for hundreds) |

## What is next

1. **The operator: #201** (a turn answered with a question also runs the follow-up call, which
   wastes one call; mechanical) **and #202** (a request no family fits is forced into the
   nearest family, and the session fails instead of asking; protocol).
2. **#198, the benchmark**, before 14.7.5: format on/off × one step/two × three local models, on
   the walk sentences, the no-fit sentences and a synthetic ~300-type layer; plus prose quality
   (#200, #195).
3. **Then 14.7.5**, the settings menu.

## Traps

- **The stack does not read `registry/`.** `docker-compose.yml` mounts `.run/registry`, a clone
  `make dev` creates. A registry change needs that clone moved too, or the api fails to load
  with the new check.
- **`make verify` stops at the known failures inside `check`**, so `slow` and `guards` must be
  run on their own to be run at all.
- **The family step's way out is not enough on its own** (#202): the model took the nearest
  family despite a bold instruction not to. A no-fit sentence belongs in every walk.
