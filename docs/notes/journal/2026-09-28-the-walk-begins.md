# 2026-09-28 — the walk begins, and the protocol for what it finds

**The living pipeline met a real model and a browser for the first time, and the first hour found
ten defects before a single goal was confirmed.** That was expected. What changed today is how
they are handled: the operator called this a new phase, *Living Pipeline Plan 2*
([`the plan`](../../superpowers/plans/2026-09-28-the-living-pipeline-2-the-walk.md)), with a
protocol written down before the second defect was fixed.

Read this entry for the protocol; read the plan for the scenarios and the issue ledger.

---

## The thesis, restated by the operator

The system was designed from theory. **Comeni is a balance between flexibility and restraint**:
typed questions, closed vocabularies, declared doors and admission checks are the restraint that
makes a model's contribution checkable. The walk shows which way each rule is wrong. If it's too
strict for the system to function, loosen the protocol. If it's too loose, tighten it.

**The failure named: "you have a tendency to try to make things work no matter what."** A
workaround hides which rule was wrong, and the rules are the product. So:

- **Every defect gets a GitHub issue first**, mechanical ones too, *so we don't lose track of
  things*.
- **Mechanical** defects are fixed directly, test first, and closed citing the commit.
- **Rule or protocol** defects are brainstormed, the operator chooses, the choice is commented on
  the issue, and only then implemented.
- Rounds: walk → issues → fix and decide → walk again from the start.

## What the first hour found

The model is `gemma3:12b`, local, on an 8 GB AMD card. It's **deliberately weak**, because it
fails where a stronger model would paper over a protocol problem, and it costs no tokens while the
loop is rough.

1. **The first real call failed MA0004** (#106). `GoalUnderstanding` had a prose `have` beside a
   nested `goal` with a typed `have`, and the prompt described the typed one as plain `have`. The
   model did what the prompt said, in the wrong place. **The finding came from `output_tokens` on
   the `ai_invocation` row**: 256, exactly, looked like a cap, and ruling that out led straight to
   reproducing the call.
2. **The refusal didn't say where** (#107), and **the goal card hid states** (#108): the model
   wrote `fastq.reads[deduplicated]` and the chip said `fastq.reads`. The one field the model got
   wrong was the one the card exists to check. All three fixed in `36d22a3`.
3. **The protocol question, #105.** For *paired-end RNA-seq*, the model writes a state:
   `deduplicated` (declared, so it passes every check and skips a step) or `paired` (undeclared,
   refused). Paired-endness is a *measurement* in this registry and the prompt never says so. One
   paragraph fixed it on 2 of 2 runs, **and that is exactly the fix not to take silently**: whether
   the answer is the prompt, the vocabulary, the reply shape, admission or the card is the design
   question. The `LivingGoal` artboard draws `fastq.reads[paired]`, so design and registry already
   disagree.
4. **Mechanical, open:** a refused goal offers no retry and the header stays on *reading your goal* (#110); the
   card can't remove a state (#111); nothing says what to do after *Not quite* (#112); *New
   pipeline* opens the RNA-seq example (#113).

**What worked, first time:** the Assistant tab as a way in on a populated installation; reload
restoring a pending proposal with no duplicate turn; typing the request again after a refusal.

## Setup a later session needs

- **Ollama's default context is 2048 tokens and it truncates silently.** The goal prompt is
  ~4,300. `OLLAMA_CONTEXT_LENGTH=16384` in `.env`; compose passes it through.
- **Run the authoring tests against a throwaway Postgres** (`127.0.0.1:5442`). Their fixtures
  truncate, and the stack's database holds the walk.
- A prompt change is a new version: `builder.goal.v2` now, `v1` kept loadable as
  `prompts.RETIRED` because rows cite it.

**A wrong issue, corrected the same session (#109).** I filed *assistant turns reach the model
blank* from an empty `text` column, without reading `_spoken()`, which sends each turn's summary.
The model saw its own *deduplicated* and the person's *not deduplicated*, and it still repeated
itself. That makes it evidence for #105 and not a bug. **Read the code that composes a prompt
before filing a claim about what the prompt holds.**

## What to do next

Fix #110–#112, rebuild, and walk round 2 from scenario 1. Bring #105 to the operator as a
brainstorm with options before touching the prompt.
