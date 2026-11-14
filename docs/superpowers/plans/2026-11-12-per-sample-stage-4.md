# Per-sample stage 4: branches — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** A tool chosen from a fact that differs between samples is chosen per sample. Samples
whose read length is 70 or more go to STAR, shorter ones to HISAT2, in one pipeline. A step only
some samples need (a skippable one) is skipped for the rest. Every branch and the samples it
takes are listed before the run, and the run records which path each sample took.

**Architecture:**
- An `implementation` (or `presence`) decision whose rows read only per-sample facts the run
  has (cells or measurements, on the step's own input) is a **branch point**.
- The resolver routes the goal once for each outcome its rows can reach, with that tool pinned
  (`ProducerPin`, or `absent_roles` for a skipped step), and merges the routes. Steps on every
  route are shared. A step on only some routes carries a **guard**: the rows that send a
  sample its way.
- Where routes rejoin, the next step's input has an edge from each branch; the emitter mixes
  them. A guarded step reads only the samples its guard admits.
- A step that only feeds guarded steps (STAR's index) starts only once one of its samples
  arrives.

**Tech Stack:** Python 3.12, Nextflow DSL2, React + TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-11-per-sample-design.md`: stage 4, Goal D ("Which tool a
sample goes through", "Whether a sample goes through a step", "A sample no row covers").

## Global Constraints

- Keep it simple (operator, 11-12): routes are merged from ordinary resolutions with pins, never a new router.
- The same goal gives the same pipeline: outcomes in row order, merged nodes and edges sorted as the resolver sorts them.
- Every run-time condition is written from the closed tests (`groovy_lookup.condition`).
- Branches must rejoin at the same type and states; otherwise the build refuses (MD0339) and the decision stays a question.
- A sample no row covers gets the decision's fallback, asked once at build time: a tool, or "stop the run and name the sample".
- Per task: targeted tests; full checks at the end of the part. Commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Two routes that differ upstream of the branch point** (each would pick a different trimmer). Refused (MD0339): only what the branch point changes may differ. Pinned in Task 2.
2. **Every sample stated to one side** (read length stated 150 for the study). No branch at all; today's pipeline exactly. Pinned in Task 1.
3. **A sample whose read length comes back undetermined.** It takes the fallback, which the step card lists. It never vanishes. Pinned in Task 3 (slow).
4. **An index nobody's sample needs.** With all samples at 150 bp, HISAT2's index never starts. Pinned in Task 3 (slow).
5. **A branch inside the measuring branch** (the fact is measured after trimming). The measured facts are rejoined before the guard reads them (stage 1's `_remeta`). Pinned in Task 3.

---

### Task 1: Branch points and their outcomes

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/at_run.py` (`branch_points(ir, registry, rules, premises, measurements, goal) -> list[BranchPoint]`)
- Modify: `packages/comeni-core/src/comeni_core/plan/at_run.py` (`Guard`: `rows: list[list[AtRunCondition]]`, any row admitting; `facts: list[AtRunFact]`)
- Test: `packages/mendel-resolver/tests/test_branches.py` (new)

**Interfaces:**
- Produces: `BranchPoint(site, decision, facts, sources, outcomes: list[tuple[str, Guard]], fallback)`. `outcomes` holds each contract the rows can reach over `cases()`, in row order, with the rows that reach it. The rules are as for a run-time setting (stage 1): every unknown fact comes from the run and rides the step's own input; `hit: first`, or `unique` without overlaps.

- [x] **Step 1: Write the failing tests:**
  - with `read_length` measured in the run, `implementation:alignment` is a branch point with outcomes STAR (`read_length >= 70`) and HISAT2 (`< 70`), and its fallback asked;
  - with `read_length: 150` stated, there is no branch point (Review Focus 2);
  - a decision whose rows reach one contract over every case is no branch point.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** `packages/mendel-resolver/tests`. Expected: pass.
- [x] **Step 5: Commit** `feat: a tool chosen from a per-sample fact is a branch point (#466)`.

### Task 2: Routes merged, guards on their steps

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py` (after the run-time pass: per branch point, resolve each outcome with its pin; merge)
- Modify: `packages/comeni-core/src/comeni_core/plan/ir.py` (`IRNode.guard: Guard | None`), `artifact/pipeline.py` (`Step.guard`), `artifact/materialise.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/validate.py` (several edges into one port are allowed when their producers are alternatives of one branch point)
- Modify: `diagnostics.yml` (`MD0339`: routes differ outside the branch, or do not rejoin at one type)
- Test: `packages/mendel-resolver/tests/test_branches.py` (extend)

- [x] **Step 1: Write the failing tests:**
  - the merged IR has STAR's align and index and HISAT2's align and index, each guarded; trimming and featureCounts are shared and unguarded; featureCounts' `bam` has two incoming edges;
  - routes differing upstream are refused (Review Focus 1);
  - the merge is deterministic.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the resolver and core tests. Expected: pass.
- [x] **Step 5: Commit** `feat: each sample's tool routed, the routes merged with guards (#466)`.

### Task 3: The emitted branches

**Files:**
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`:
  - a guarded step's sample-grain first input is filtered by its guard;
  - an input fed by several producers is `.mix`ed;
  - a study-grain input of a step that only feeds guarded steps waits for the first admitted sample (`.combine(<guarded channel>.first().map { true }).map { it[0..-2] }`);
  - the fallback for a sample no row admits is a tool's branch or a stop;
  - `routed/<decision>.tsv` records each sample and the tool it took.
- Modify: `packages/wiener-api/src/wiener_api/services/measured.py` (read `routed/`), `wiener_core/measured.py` (`RoutedSample`)
- Test: `tests/emit/test_branches.py` (new: pure, and slow: two stub samples at 150 and 50 bp go to STAR and HISAT2; Review Focus 3, 4 and 5)

- [x] **Step 1: Write the failing tests** above.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement.**
- [x] **Step 4: Run** the pure tests, then the slow ones. Expected: pass.
- [x] **Step 5: Commit** `feat: each sample goes down its own branch in the run (#466)`.

### Task 4: Shown before and after the run

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/services/build.py` (`StepView.guard`: "for samples whose read length ≥ 70"), the graph's branch drawing in `frontend/src/build/living/` (a guarded step marked with its guard), `frontend/src/runs/Measured.tsx` (each sample's path)
- `make client`
- Test: the step card, canvas and run page tests

- [x] **Step 1: Write the failing tests:**
  - the step card says which samples a guarded step takes;
  - the canvas marks guarded steps;
  - the run page says each sample's tool.
- [x] **Step 2: Run them.** Expected: FAIL.
- [x] **Step 3: Implement** with the design tokens.
- [x] **Step 4: Run** `npx vitest run` and `npx tsc -b`. Expected: pass.
- [x] **Step 5: Commit** `feat: the builder and the run page show each sample's path (#466)`.

### Task 5: Docs and the end of the part

- [x] **Step 1:** Docs (the rule schema's "Decided at run time", the pipeline schema's `guard`), `CHANGELOG.md`, the journal. Tick this plan; record its deviations.
- [x] **Step 2:** Run `make check`, `make guards`, `make slow`, `npx vitest run` and `npx tsc -b`, separately. Expected: pass.
- [x] **Step 3: Commit** `docs: per-sample branches (#466)`.

## Deviations

- Only a fact a person said varies makes a branch; an unknown fact nobody said varies stays
  today's question (branching on every measurable unknown would build both aligners whenever
  read length was unknown).
- One branch point per pipeline; a second per-sample tool choice stays a question (#489).
- `Guard` was added in Task 2, where it is first used. `validate.py` was not changed: it has no
  one-edge-per-port check.
- Several producers into one input are saved as `source` plus `mixed`, not a list of sources.
- Each sample's tool is recorded as `decided/<role>.tool.tsv` and read by Wiener as a decided
  value (`<role>.tool`), not in a new `routed/` folder with its own event payload.
- Tools are written in the run as tokens (`nf-core.star.align:2.7.11b`): `/` and `@` are outside
  the substitutable class.
- A fallback still a question stops the run for the sample, as a stop does.
- The measuring branch is never gated: faidx for `genome_length` runs even when no STAR sample
  arrives, so the measured-fact join always matches.
- The fallback question is shown as a generic question (#489).
- A step only some samples need (presence per sample) was not built: only the tool is chosen per
  sample (#489).
- Final review fixes (94f003f1): a goal that never reaches the choice builds as before; a
  person's pinned, excluded or switched-off tool is no branch; an unanswered fallback stops the
  run (the stop is the first candidate); a tool's per-sample rules read only its branch's
  samples; a guarded step carrying samples inside the measuring branch is refused (MD0330).
