# Part I.2: say what was narrowed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** What you asked for and is not offered here is shown where the goal is checked, and the
goal reads in names rather than ids (#293 Part I.2, #268, #306).

**Architecture:** No new kind of record or message. The engine already records a request the
model reads as not offered as an `asked` note (`replies.issue`, kind `asked`), through the
correction path whose receipt says *not offered here* in the chat. The session view gains the
current notes (`not_offered`) and the vocabulary gains the registry's type names (`names`);
the page shows a *Not offered here* row in *What was understood* and on the goal card, and
names instead of ids. Two wording fixes from #306.

**Decided (operator, 2026-10-28):** C — the row is the record, the chat's existing line points
at it. #306 item 3 (questions without a model) is left: **the MVP assumes a model**. #268's
paired-end case stays a note (model variance).

**Spec:** this plan (the decisions above, made in conversation); #293 Part I.2, #268, #306.

## Global Constraints

- The MVP assumes a model; do not add no-model paths.
- No stored-shape, protocol or registry change; names come from `stack.vocabulary.names`.
- An id with no declared name is shown as itself (never invented).
- Frontend traps from one builder plan 3 apply.

## Review Focus

1. **A note retracted later** (*actually I do want counts*): the row goes. Test in Task 1.
2. **A type with no declared name**: the id shows. Test in Task 2.

---

### Task 1: The notes reach the page

**Files:** `packages/mendel-api/src/mendel_api/services/session.py` (`"not_offered"` from
`decisions.read_asked`), `routes/authoring.py` (`AuthoringSessionView.not_offered: list[str] = []`);
`make client`; `frontend/src/build/living/Understood.tsx`, `blocks/GoalCard.tsx` (a row);
tests `packages/mendel-api/tests/authoring/test_authoring_stream.py`, `Understood.test.tsx`,
`Describe.test.tsx`.

- [ ] **Step 1: Failing tests** — after a chat reply whose `not_offered` quotes the person
  (*differential expression*), `facade.read(sid)["not_offered"] == ["differential expression"]`,
  and the turn carries a receipt containing `not offered here`; retracting the note empties
  the list. `Understood` and the goal card show *Not offered here: differential expression* with
  *This pipeline stops before it; the rest is yours.*; absent when the list is empty.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(build): say what was asked for and is not offered here (#293)`

### Task 2: Names, not ids, on the goal

**Files:** `routes/authoring.py` (`AuthoringVocabulary.names: dict[str, str] = {}` — the
builder types' declared names); `make client`; the page's vocabulary hook; `GoalCard.tsx` (have
and want lines); tests `Describe.test.tsx`.

- [ ] **Step 1: Failing tests** — the goal card's have/want lines read the declared name
  (*Paired-end reads* for `fastq.reads` when the vocabulary names it) and fall back to the id when
  no name is declared; the route returns `names` for builder types only.
- [ ] **Step 2–4:** run (FAIL), implement, run (PASS).
- [ ] **Step 5: Commit** `feat(build): the goal reads in names (#306)`

### Task 3: Two wording fixes

**Files:** `blocks/GapCard.tsx` (no `why_open` line when the explanation says why);
`StepLine.tsx` `AnswerLine` (the question wraps instead of being cut); tests `GapCard.test.tsx`,
`LivingSurface.test.tsx`.

- [ ] **Step 1: Failing tests** — a gap whose envelope carries an explanation draws no
  `why_open` line; one without still does; an answered line's question is shown whole.
- [ ] **Step 2–4:** run (FAIL), implement, run (PASS).
- [ ] **Step 5: Commit** `fix(build): no repeated why under a question; answered lines whole (#306)`

### Task 4: Docs

`CHANGELOG.md`, a journal entry, tick this plan, comment on #293, #268 and #306 (item 3 left:
the MVP assumes a model). `make check`.

## Deviations

(Recorded during execution.)
