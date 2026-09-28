# Living Pipeline Plan 2 — the walk: test, issue, decide, close

> **Not "Plan 2".** That number belongs to the forge (2026-08). This is the living pipeline's
> second plan, and it **is Task 14** of the first one, from the point it turned from building
> into testing. There is no Task 15 or 16.

## Where things are: Task 14 → step → substep

Each line is a GitHub issue, and each level is a sub-issue of the one above it.

```
#119 Task 14 — Cut over, walk the real loop, and update documentation
├─ #120–#125  14.1–14.6   cutover, ladder, stack                        done
├─ #126       14.7        the walk
│   ├─ #131   14.7.1  round 1: #106–#112, #115, #116                    done
│   ├─ #132   14.7.2  the protocol as code                              spec §5
│   ├─ #133   14.7.3  gathering without files (#105, #113, #114)        spec §6–7
│   ├─ #180   14.7.4  the consultant's words, fast and cheap (#167 #176 #182–#186)
│   ├─ #181   14.7.5  the settings menu (#117, #187)
│   ├─ #134   14.7.6  samples + the FASTQ inspector                     spec §6
│   ├─ #135   14.7.7  the characteriser                                 spec §6
│   ├─ #136   14.7.8  the consultant build, provisional                 spec §8
│   └─ #137   14.7.9  the nine scenarios, round by round
├─ #127       14.8        artboards beside the page
├─ #128       14.9        ai_invocation rows and pipeline.yml provenance
├─ #129       14.10       handbook from observed behaviour
└─ #130       14.11       journal + CLAUDE.md pointer (#118, docs cleanup)
```

Spec: [`2026-09-28-the-consultant-design.md`](../specs/2026-09-28-the-consultant-design.md).

**Date:** 2026-09-28

**Status:** in progress — round 1

**Goal:** Take the living pipeline from *passes its tests* to *works for a person with a real
model behind it*, by walking it in a browser, repeatedly, and changing the system where it
breaks. The first plan built the loop from theory; this plan finds out which parts of the theory
hold.

**What it continues:** [`2026-09-07-the-living-pipeline.md`](2026-09-07-the-living-pipeline.md)
Task 14, steps 6–11 (stack, walk, artboards, audit rows, handbook, journal). Those steps are
carried here as the scenario list below. The first plan's completion criteria still apply, and
this plan is complete when they hold in a browser.

---

## 1. The thesis this plan tests

**Comeni is a balance between flexibility and restraint.** Typed questions, closed vocabularies,
declared doors and admission checks are restraint: they are what make a model's contribution
checkable. Each one was designed before anything drove it. A walk shows which way each one is
wrong:

- **Too strict to function.** The system blocks, or it pushes a model into the nearest *legal
  wrong* answer, which is worse than a refusal because it passes every check. **Loosen the
  protocol.**
- **Too loose to mean anything.** A wrong answer is admitted, or a person cannot see what they
  are confirming. **Tighten it.**

**Never make it work anyway.** A workaround hides which rule was wrong, and the rules are the
product. The operator named "make things work no matter what" as the failure to avoid.

## 2. The protocol

**Every defect gets a GitHub issue before anything else**, mechanical ones included, so nothing
is tracked only in a conversation. Then:

| Kind | Examples | Path |
|---|---|---|
| **Mechanical** | a missing button, a stale label, a wrong join, a field that does not reach its reader | fix, test first, watched failing → commit → close the issue citing the commit |
| **Rule / protocol** | a closed set a model cannot express a fact in; a check that admits a wrong answer | brainstorm options → **the operator chooses** → the choice is commented on the issue → implement → close |

A round is: walk until a batch of defects is found → open the issues → fix the mechanical ones
and put the protocol ones to the operator → walk again from the start. **Expect many.** The
forge's first driven day found nine; this plan's first hour found ten.

**Subagents:** review and design options inside a brainstorm only, as `CLAUDE.md` already says.
Implementation stays in one hand.

## 3. The setup

- **Model:** `ollama/gemma3:12b`, local, AMD RX 7600 (8 GB, gfx1102) via
  `docker-compose.ollama-rocm.yml`. Deliberately weak. It fails where a stronger model would
  paper over a protocol problem, and it costs no tokens while the loop is still rough. A call
  takes 35–55 s.
- `.env`: `COMENI_AI_MODEL`, `COMENI_AI_BASE_URL=http://ollama:11434`,
  `COMENI_AI_TIMEOUT_SECONDS=300`, `OLLAMA_CONTEXT_LENGTH=16384` (Ollama's default of 2048
  silently truncates the goal prompt, which is ~4,300 tokens), `HSA_OVERRIDE_GFX_VERSION=11.0.0`,
  `RENDER_GID`/`VIDEO_GID`.
- **Tests against a throwaway Postgres on `127.0.0.1:5442`**, never the stack's. The authoring
  fixtures truncate tables, and the stack's database holds the walk's sessions.
- APIs run from a baked image: `docker compose up -d --build api ai-worker web` after a change.

## 4. Scenarios

From the first plan's Task 14, walked in order, each round starting again at 1:

- [ ] 1. Build: *paired-end RNA-seq → gene counts*
- [ ] 2. Spawn: the same request
- [ ] 3. many FASTA/FASTQ items with an ambiguous grouping answer
- [ ] 4. one alternative module
- [ ] 5. one parameter correction
- [ ] 6. a *why?* follow-up
- [ ] 7. reload while a turn is pending
- [ ] 8. a refusal and the no-model state
- [ ] 9. Keep → lint → run sheet on the completed draft

Then: artboards beside the page at designed widths (reduced motion, keyboard, touch, long
content, a 15-module graph); `ai_invocation` rows and `pipeline.yml` provenance; the handbook
from observed behaviour; the journal.

## 5. Issue ledger

| Round | # | Defect | Kind | State |
|---|---|---|---|---|
| 1 | [#105](https://github.com/comeni-project/Comeni-Labs/issues/105) | a model with no place for *paired-end* writes the nearest legal state, `deduplicated` | **protocol** | brainstorm |
| 1 | [#106](https://github.com/comeni-project/Comeni-Labs/issues/106) | the goal reply shape named two different fields `have`: MA0004 | mechanical | closed, `36d22a3` |
| 1 | [#107](https://github.com/comeni-project/Comeni-Labs/issues/107) | MA0004 did not say which fields failed | mechanical | closed, `36d22a3` |
| 1 | [#108](https://github.com/comeni-project/Comeni-Labs/issues/108) | the goal card hid states | mechanical | closed, `36d22a3` |
| 1 | [#109](https://github.com/comeni-project/Comeni-Labs/issues/109) | ~~assistant turns reach the model blank~~ — they don't; `_spoken()` sends the summary. The model ignored a correction it could see: evidence for #105 | — | closed, not a defect |
| 1 | [#110](https://github.com/comeni-project/Comeni-Labs/issues/110) | a refused goal has no retry; header stays *reading your goal* | mechanical | closed, `bce66df` |
| 1 | [#111](https://github.com/comeni-project/Comeni-Labs/issues/111) | the goal card cannot remove a state | mechanical | closed, `bce66df` |
| 1 | [#112](https://github.com/comeni-project/Comeni-Labs/issues/112) | after *Not quite*, nothing says what to do next | mechanical | closed, `bce66df` |
| 1 | [#113](https://github.com/comeni-project/Comeni-Labs/issues/113) | *New pipeline* opens the RNA-seq example | product choice | open, with the brainstorm |
| 1 | [#114](https://github.com/comeni-project/Comeni-Labs/issues/114) | a goal missing its genome is confirmed, then cannot resolve; nobody asked | **protocol** | brainstorm, with #105 |
| 1 | [#115](https://github.com/comeni-project/Comeni-Labs/issues/115) | a resolve failure was a toast, written nowhere, a dead end | mechanical | closed, `a9e94cb` (MI0207; the way forward is #114) |
| 1 | [#116](https://github.com/comeni-project/Comeni-Labs/issues/116) | an edited goal left the model's sentence saying the opposite | mechanical | closed, `a9e94cb` |

## 6. Execution record

| Round | What | Result |
|---|---|---|
| 1 | stack up with the local model; scenario 1 to goal confirmation | ten defects, three fixed (`36d22a3`); the round stopped to set this protocol down |
| 1 | mechanical fixes #110–#112 (`bce66df`); scenario 1 continued past the goal to resolving | resolving failed on a missing genome (#114, #115, #116); #115/#116 fixed (`a9e94cb`); scenario 1 is blocked on #114 |
