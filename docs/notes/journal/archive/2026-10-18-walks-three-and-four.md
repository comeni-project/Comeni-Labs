# 2026-10-18 — Part I.0 walks three and four: the conversation holds

Since 2026-10-16: #332 and `facts-a-step-needs` (#343) merged; walk 3 (#348) and its fixes
(#349 walk polish, #350 follow-ups) merged; a Dependabot bump surfaced a wrong test (#352, fixed by
#353; #351 merged); walk 4 on `main` closed out #327's items and found five smaller defects (#354),
fixed on `walk4-fixes` (#355). Every walk used one sentence, *"Gene counts from paired-end
RNA-seq of yeast."*, and `SRR6357070_1/_2.fastq.gz`, on gemma3:12b.

## Where things stand

- **The walk meets the bar** (#338): three input questions, read length 101 / paired / phred33
  measured, *Set it up*, one tier-4 stop for strandedness (forward / reverse / unstranded), complete.
- **A value against a measured one is asked about** (#345, operator): *Are you sure the read length
  is 50? Your sample measured 101.* Yes records it as said and re-routes (STAR → HISAT2); No keeps
  the measurement. Derived when the card is read, nothing new stored (`suggestions._says`).
- **`measurement.<id>` types are no builder door's** (#346): `registry.builder_types(stack)` is the
  one filter for the goal card, every prompt's type list and every admission; `mendel profile`
  still uses them.
- **A not-offered request is a note**, recorded without a card before and after confirmation
  (#347). Once built it makes no revision and no review: *Nothing in the pipeline changes.* (#355).
- **Prompts in use:** `family.v4`, `goal.v9`, `chat.v7` (#355), `ask.v3`, `readback.v2`.
- **Measuring a prompt:** `tools/measure_prompts.py --runs 5` compares two prompt sets on the walks'
  own sentences, in-process. Walk 4's context is captured in it (`WALK3_*`, same 1,991 input tokens
  as the recorded call).

## What changed

- `73d0bb7a` asking before overriding a measurement; `b645c1b3` goal.v9 / chat.v6 / ask.v3;
  `78fab6d7` the fact card's tier, reason and buttons, turn blocks to shape 2 (#341).
- `70546070` #346; `b0a43afc` #347; `39709074` registry `strandedness` reads *Library strandedness*
  (#344, registry PR 19).
- `4d478716` the stream-cap test asserts a bound: `MAXLEN ~` trims by node, fakeredis 2.40 agrees.
- On #355: `56f5000e` receipts (a note changes nothing; the diff a sentence of its own; a wrap-up
  said once per revision); `bfb80e94` a withdrawn tier-4 offer reads *answers changed*;
  `bc0ef59b` chat.v7.

## Decisions (operator)

- #345: ask *are you sure?* and then follow what they said, not offer or override.
- #346 one shared filter; #347 record without a click; #344 the shorter description.
- #327 is closed by walk 4 (item 6 no longer arises: strandedness is the tier-4 card's).

## Rulings worth knowing

- **One walk reply is a sample.** Walk 4's *Read length is 50 — got it.* did not recur in 5 replays
  of the same context at temperature 0; a model fix is judged on rates, before and after.
- A first `chat.v7` draft dropped the fact itself (1/5), which would have stopped the engine asking:
  a *do not* in `say` must keep the change required.
- `chat.v6` told the model the engine asks about any differing value; it asks only against a
  measured one. Prompts must describe the engine as built.
- `"· open"` on a decided tier-4 row was kept (it may mean *flagged for review*); only withdrawn
  offers lose it.

## Next

1. Merge #355; close #327, #348, #321.
2. Plan B (the save file, #307), after the operator's `comeni_core/artifact/` audit.
3. Then Part I.2/I.3; #342 minors; #339 strandedness at run time (protocol choice).

## Traps

- **Ports on this machine:** other projects hold 5432 and 8000. Start with
  `API_HOST_PORT=8020 DB_HOST_PORT=5433 make dev` (the wiki owns 8010), and Ollama with
  `make ai-up OLLAMA_GPU=rocm`. `.env`'s `MENDEL_DATABASE_URL` points at 5432: give host tools
  (`measure_prompts.py`) the test database explicitly.
- `docker compose down` removes the network a stopped Ollama container still names: recreate it
  (`up -d --force-recreate ollama`).
- `ai_invocation` stores replies and digests, not prompt text; a past call is replayed by rebuilding
  its context (`describe.turn_context` answers only a pending turn).
- A GitHub *Closes #a, #b* links only `#a`: one *Closes* per issue.
