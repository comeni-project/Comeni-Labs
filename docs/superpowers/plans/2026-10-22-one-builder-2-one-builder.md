# One builder, plan 2 — one builder, no fork

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every pipeline opens in one builder at `/build`, and a hand edit to it, at any time
(during the walk or after it), is read as the person's intent, confirmed in the chat and
recorded in the same pipeline. The fork goes.

**Architecture:** A canvas edit stops being a graph save. The server reads it with plan 1's
`read_edit`, and offers each reading as a **suggestion** (the existing table, card and apply
path), grouped per edit and worded by the engine. Applying one performs `c.Change` as the
person, which already re-resolves and re-reviews like a correction. `DecisionChange` learns the
three structural kinds. With nothing left that a re-plan can lose, `ownership`, the fork
command, its handler and its columns are deleted. On the client, `LivingBuilder` becomes the
only builder: it gains the manual builder's missing controls and `Builder.tsx` is deleted.

**Tech Stack:** Python 3.12, pydantic v2, SQLAlchemy + Alembic, FastAPI, pytest; React 19,
TanStack Query, vitest.

**Spec:** `docs/superpowers/specs/2026-10-22-one-builder-design.md` (sections *One builder*,
*Structural hand edits are intent the engine honours*). Plan 1:
`docs/superpowers/plans/2026-10-22-one-builder-1-structural-intent.md`.

## Global Constraints

- **The engine decides; the model phrases.** A reading's sentence is composed by the engine
  (`read_edit`), never by a model; no new AI point.
- **Nothing changes silently:** a structural edit changes nothing until the person confirms its
  reading in the chat; what a confirmed reading changes reaches the log as a receipt.
- Provenance kept: a confirmed reading is written with `who` = the person, `actor_kind` person,
  through `services/changes.apply` (the one writer).
- One command per transaction through `mendel_api/services/session.py`; a session moves only by
  a drawn arrow. **Removing `fork_correction` is a protocol change**: delete its node and arrows
  in `protocol.py`; the generated protocol diagram and its tests change with it.
- Stored JSON shapes are versioned: a widened `DecisionChange` is
  `pipeline_authoring_suggestion` **shape 2**, with an identity-upgrade migration and golden,
  as plan 1 did for turn blocks. Restart `mendel-worker` and `ai-worker` after migrating.
- **No backward compatibility before v0.1.0:** old forked drafts stay separate pipelines,
  unlinked; the fork columns and `ownership` are dropped, not kept for reading.
- Every feature on the inventory below works in the one builder before `Builder.tsx` is deleted.
- UI changes are checked in a browser at 1440×900 and 390 wide (CLAUDE.md); DOM tests do not
  establish layout.
- Python tests through the test database (`make test-db`; `make test`), never bare pytest
  against the dev DB. Tick steps here as they are done; record deviations at the end.

## Feature inventory (the spec's checklist; each stage ticks it)

Manual builder (`frontend/src/build/Builder.tsx`), and where it lives after this plan:

- [ ] add a step from Browse — living has it (`LivingSurface` → `Browse`)
- [ ] swap a tool (`Swap`), with its consequences — living has it (`StepTools`)
- [ ] settings with typed values (`Settings`) — living has it (`StepTools`)
- [ ] remove a step — living has it (`StepTools`)
- [ ] **remove the selected step with Delete / Backspace** — Task 7
- [ ] **wire ports by dragging from an output to an input; remove a wire** — Task 7
- [ ] **pick a step for an open port (`Picker`)** — Task 7
- [ ] drag a step; Tidy; Fit; minimap — living has them (`LivingCanvas`)
- [ ] **zoom in / zoom out / reset the view buttons** — Task 7
- [ ] **rename the pipeline** — Task 7
- [ ] **findings panel (`Findings`), selecting a step from a finding** — Task 7
- [ ] status line (`Status`): kept, lint, run state — living has it (`LivingHeader`)
- [ ] keep, lint gate, run sheet with samplesheet and sources — living has them (`useKeep`,
  `useGate`, `useRun`, `RunSheet`)
- [ ] the artifact (`ArtifactView`) — living has it (`PipelineFile`)
- [ ] entry channels drawn (`Sources`) — living has it (`SourceNode`, `Flowline`)
- [ ] the example at a bare `/build` (`useExample`) — **retired**: a bare `/build` opens a new,
  empty pipeline (Task 6); the example stays at `examples/rnaseq.yml` and in the docs. *My call.*

Conversation builder: step line, step on offer (dashed), question cards, alternatives and
previews, *Assistant* tab, motion and reveal, review states, header status and *needs you*
chip, suggestions, sample upload, *What was understood*, pipeline file — all stay; nothing here
removes them.

## Review Focus

1. **A second edit to the same thing while its reading waits** (remove STAR, then swap the
   aligner): the older reading must go stale, never both apply. Test in Task 3.
2. **A confirmed reading the engine cannot honour** (exclude the only sorter, MD0320): the person
   gets the coded sentence in the chat and nothing is written. Test in Task 4.
3. **An edit sent against an old revision** (two tabs): refused with MI0201 and nothing offered.
   Test in Task 3.
4. **A drag, a Tidy, a rename**: offer nothing and write no receipt. Test in Task 3.
5. **Opening `?draft=` twice at once** (two tabs, a double click): one session, both get it.
   Test in Task 6.

---

### Task 1: `read_edit` reads from the blueprint's sites; `read_graph` reads a drawn pipeline

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/intent.py`
- Test: `packages/mendel-authoring/tests/test_intent.py`

**Interfaces:**
- Produces: `read_edit(before: DraftGraph, after: DraftGraph, sites: Mapping[str, Site],
  registry: Registry) -> list[Reading]` (the plan parameter becomes the node → site map a
  `Blueprint` already stores as `sites`); `read_graph(graph: DraftGraph, registry: Registry)
  -> list[Reading]`; `Reading.change() -> DecisionChange` (Task 2's kinds).

- [ ] **Step 1:** Change the fixture to pass `{n.id: n.site for n in ir.nodes if n.site}`; the
  eight tests keep their assertions. Add:

```python
def test_a_drawn_pipeline_reads_as_every_tool_pinned_and_its_ends_wanted(planned):
    graph, ir, registry = planned
    readings = read_graph(graph, registry)
    pinned = {r.intent.contract for r in readings if r.kind == "pin"}
    assert pinned == {n.contract_id for n in graph.nodes}
    assert [r.intent for r in readings if r.kind == "want"] == ["counts.matrix"]

def test_an_empty_drawing_reads_as_nothing(planned):
    assert read_graph(DraftGraph(), planned[2]) == []
```

- [ ] **Step 2:** Run `make test` on the file — FAIL (signature, `read_graph` missing).
- [ ] **Step 3:** Implement. `read_graph` pins every node at `_output_site(contract)` and wants
  each output nothing reads; the sentence is *"So this is your pipeline: …, with these tools —
  right?"* on the first reading, `…` on the rest. Unknown tools are skipped (validation names
  them).
- [ ] **Step 4:** Run — PASS. **Step 5:** Commit `feat(authoring): read an edit from the
  blueprint's sites, and a drawn pipeline whole`.

### Task 2: a structural change is a `DecisionChange`

**Files:**
- Modify: `packages/mendel-authoring/src/mendel_authoring/payloads.py` (`DecisionChange.kind`,
  `Correction.kind`), `packages/mendel-authoring/src/mendel_authoring/intent.py`
  (`Reading.change`), `packages/mendel-api/src/mendel_api/services/changes.py` (`check`,
  `retracts_something`, `apply`, `describe`), `shape_versions.py`, `shapes.py`
- Create: migration `…_suggestion_change_v2.py` (identity upgrade, after `7ea478ea7f3b`), golden
  `tests/golden/shapes/pipeline_authoring_suggestion.change.v2.json`,
  `tests/infrastructure/test_suggestion_change_v2.py`
- Test: `packages/mendel-api/tests/authoring/decisions/test_intent_changes.py`

**Interfaces:**
- Produces: `DecisionChange.kind` gains `"role" | "exclude" | "source"`, encoded on the
  existing fields — **role**: `subject` = role; **exclude**: `subject` = type id, `states`,
  `value` = contract (as `pin`); **source**: `subject` = `decisions.source_key(consumer, port)`,
  `value` = producer. `retract=True` releases each through `decisions.release_intent`.

- [ ] **Step 1: tests.** `test_a_role_change_switches_it_off_and_back_on`,
  `test_an_exclude_change_excludes_at_the_site`, `test_a_source_change_pins_the_port`,
  `test_an_undeclared_role_tool_or_port_is_refused_with_MI0204` (a role no contract declares, a
  contract not in the registry, a consumer without that port), and
  `test_reading_change_round_trips` (each `Reading` kind's `.change()` applied through
  `changes.apply` puts its intent in `decisions.goal(draft).constraints`).
- [ ] **Step 2:** Run — FAIL on the `Literal`.
- [ ] **Step 3:** Implement; `describe` returns the reading's own words for the new kinds
  (*"no trimming here"*, *"not STAR_ALIGN for the alignments"*, *"featureCounts reads its bam
  from MARKDUP"*). Bump the suggestion shape to 2 with migration and golden.
- [ ] **Step 4:** Run the file and `tests/infrastructure` — PASS. **Step 5:** Commit.

### Task 3: a hand edit is read and offered, at any phase

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/stages/building/walk.py` (`record_edit`),
  `services/suggestions.py` (`offer` takes `edit: str | None`, `says: str | None`; `pending`,
  `apply`, `dismiss` act on an edit's group), `models.py` (`PipelineAuthoringSuggestion.edit`,
  `.says`, both nullable), `routes/authoring.py` (`AuthoringEdited.offered: list[str]`,
  `AuthoringSuggestionView.edit: str | None`)
- Create: migration `…_suggestion_edit_group.py`
- Test: `packages/mendel-api/tests/authoring/test_edit_reading.py`;
  modify `tests/authoring/test_authoring_routes.py` (the MI0217-during-walk test becomes
  `test_an_edit_during_the_walk_is_read_not_refused`)

**Interfaces:**
- Consumes: `read_edit` (Task 1), `Reading.change()` (Task 2), `Blueprint.sites`.
- Produces: `record_edit(session_id, graph, *, by, expected_revision=None) -> Edited` with
  `Edited(revision: int, offered: list[str])`. A **typed value** (a param that differs) is
  applied at once as `DecisionChange(kind="parameter")` — it is explicit, as today. A
  **structural** difference saves nothing: each reading is offered as a suggestion with
  `heard=False`, `invocation_id=None`, `says=reading.said` and one shared `edit` id.
  **Layout and labels only**: nothing offered, no receipt. A new reading on the same
  `(kind, subject)` as a pending one makes the older stale.

- [ ] **Step 1: tests** (session in phase `building` from the existing walk fixture):
  `test_removing_trimgalore_mid_walk_offers_the_role_reading_and_changes_nothing`
  (graph and decisions unchanged; one pending suggestion whose `says` is
  *"So you never want trimming here — right?"*),
  `test_adding_a_step_offers_one_group_of_two`,
  `test_applying_one_of_a_group_applies_the_group_in_order`,
  `test_dismissing_one_of_a_group_dismisses_the_group`,
  `test_a_second_reading_on_the_same_subject_stales_the_first` (Review Focus 1),
  `test_an_edit_on_an_old_revision_is_refused_and_offers_nothing` (MI0201, Focus 3),
  `test_a_drag_offers_nothing_and_writes_no_receipt` (Focus 4),
  `test_a_typed_value_is_applied_at_once_as_the_persons`.
- [ ] **Step 2:** Run — FAIL (MI0217 raised during the walk).
- [ ] **Step 3:** Implement. Remove the MI0217 refusal in `record_edit`; keep
  `draft_mutations.save_in`'s MI0217 for a plain draft `PUT` of a graph while authoring (a graph
  must come through the session). Sites come from `Blueprint.sites` when the session has a
  blueprint, `{}` otherwise.
- [ ] **Step 4:** Run the file and `tests/authoring` — PASS. **Step 5:** Commit
  `feat(api): a hand edit is read as intent and offered in the chat (#395)`.

### Task 4: a confirmed reading re-plans; a conflict is said, not swallowed

**Files:**
- Modify: `packages/mendel-api/src/mendel_api/stages/correcting.py` (catch `IntentConflict` where
  `UnroutableError` is caught), `services/suggestions.py`
- Test: `packages/mendel-api/tests/authoring/test_edit_reading.py`

**Interfaces:**
- Consumes: `router.IntentConflict` (plan 1), `c.Change`.

- [ ] **Step 1: tests:** `test_confirming_trimming_off_re_plans_without_trimgalore` (after apply,
  the blueprint has no `trimgalore`, the draft is re-projected, a receipt says *"no trimming
  here"*), `test_confirming_star_excluded_mid_walk_offers_the_next_aligner` (the pending step card
  is for the replacement, its reason starts *"you excluded"*),
  `test_confirming_an_impossible_exclusion_is_refused_with_its_code_and_writes_nothing`
  (MD0320 in the refusal; `decisions.goal(draft).constraints.exclusions == []`; the suggestion
  stays pending so the person can dismiss it) — Review Focus 2.
- [ ] **Step 2:** Run — FAIL on the third (500 / written exclusion).
- [ ] **Step 3:** Implement: the conflict is raised before the transaction commits, so the
  intent is not kept; the route answers 422 with the coded sentence.
- [ ] **Step 4:** Run — PASS. **Step 5:** Commit.

### Task 5: the fork goes

**Files:**
- Modify: `mendel_authoring/types.py` (`Command.FORK_CORRECTION`), `commands.py`
  (`ForkCorrection`, the `takes` sets), `payloads.py`, `protocol.py` (node and arrows);
  `mendel_api/stages/correcting.py` (`fork`, `fork_key`, `existing_fork`, `fork_correction`, the
  `ownership == "manual"` branches), `stages/describe.py` (`start="fork_correction"`, the
  `ownership` write), `services/draft_mutations.py` (the `ownership = "manual"` flip),
  `services/authoring_canvas.py` (no frame for a manual draft), `services/session.py`
  (`ownership`, `forked_from`, `forked_from_session` in the view; `progress` for manual),
  `services/decisions.py` (history inherited from `forked_from`), `services/deletion.py`,
  `services/decision_migration.py`, `models.py` (`ownership`, `forked_from`, `fork_key`,
  `fork_sequence`, `fork_at`, `uq_pipeline_draft_fork`, `complete_fork`),
  `routes/authoring.py` (`AuthoringSessionView` fields)
- Create: migration `…_drop_the_fork.py` (drops the columns and constraints; downgrade re-adds
  them empty)
- Tests that encode the fork, changed and listed (spec's open question):
  `tests/authoring/decisions/test_correction_forks.py` — **deleted**, replaced by
  `test_a_correction_after_a_hand_edit_lands_in_the_same_pipeline`;
  `tests/authoring/test_authoring_canvas.py` (three `ownership = "manual"` cases → *a hand-edited
  draft is still framed*); `tests/pipelines/test_draft_mutations.py` (ownership assertions
  removed; the MI0217 PUT test stays); `tests/authoring/decisions/test_fact_views.py`
  (`ownership`, `forked_from` fields); `tests/authoring/decisions/test_draft_deletion.py` (fork
  unlinking); `mendel-authoring/tests/test_protocol.py` (`fork_correction` entries);
  `tests/infrastructure/test_models.py`.

- [ ] **Step 1:** Write `test_a_correction_after_a_hand_edit_lands_in_the_same_pipeline` (a
  confirmed reading, then `correct` a fact: same `draft_id`, same session, no new draft row).
- [ ] **Step 2:** Run — FAIL? It may already pass once Task 3 stops flipping `ownership`; if it
  does, show it fails against `ownership = "manual"` set by hand, and record that in the guard
  ledger.
- [ ] **Step 3:** Delete the machinery listed above; `grep -rn "fork\|ownership"` over
  `packages/` and `frontend/src` returns only the protocol's unrelated `fork` (pacing branches,
  `fork_keys`) and `test_migrations`' "chain has forked".
- [ ] **Step 4:** `make check` — PASS. **Step 5:** Commit `refactor: no fork — a hand edit
  stays in its pipeline (#395)`.

### Task 6: every pipeline has a session; `/build` opens it

**Files:**
- Modify: `stages/describe.py` (`open_session(start="draw")` → phase `complete`, no blueprint),
  `protocol.py` (the `draw` start and its arrow to `complete`), `routes/drafts.py` or
  `routes/authoring.py` (`POST /api/pipeline/drafts/{id}/session`, operation `openDraftSession`,
  → `{session_id}`: the existing session, or one opened with `start="draw"` whose first turn
  offers `read_graph` of the saved graph as one edit group)
- Modify (client): `frontend/src/app/BuildRoute.tsx` (always `LivingBuilder`; `?draft=` →
  `openDraftSession` then `navigate(?session=…, {replace: true})`; bare `/build` → create a
  draft, open its session, replace), `frontend/src/app/router.tsx` (`/build/living` goes; the
  fakes answer at `/build?fake=…`), `frontend/src/build/address.ts`, `frontend/src/runs/Run.tsx`
- Test: `packages/mendel-api/tests/authoring/test_draft_session.py`,
  `frontend/src/app/BuildRoute.test.tsx`

- [ ] **Step 1: tests:** `test_opening_a_drawn_draft_starts_an_empty_conversation_that_reads_it`
  (phase `complete`, one edit group pending, graph unchanged),
  `test_opening_a_draft_with_a_session_returns_it`,
  `test_two_opens_at_once_make_one_session` (two threads; one row; both get its id — Focus 5),
  and client tests `?draft=d1 lands on ?session=s1`, `bare /build lands on a new session`.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement; the race is the unique index's
  `IntegrityError`, caught and answered with the winner's id.
- [ ] **Step 4:** Run, `make client`, `npx tsc -b` — PASS. **Step 5:** Commit.

### Task 7: the manual builder's missing controls, in the one builder

**Files:**
- Modify: `frontend/src/build/living/LivingCanvas.tsx`, `LivingNode.tsx`, `LivingSurface.tsx`,
  `LivingHeader.tsx`, `BuildPanel.tsx`; reuse `Port.tsx`, `Picker.tsx`, `Findings.tsx`,
  `Wires`' remove control, `useCompatibility`, `graphOps.ts` (add `withEdge`, `withoutEdge` if
  absent)
- Test: `frontend/src/build/living/OneBuilder.test.tsx`

**Interfaces:**
- Every control calls `onEdit(nextGraph)` (→ Task 3), except rename (`PUT` name, as today) and
  the view controls (no request).

- [ ] **Step 1: tests**, one per inventory row marked Task 7: Delete removes the selected step
  (one `/edits` call whose graph lacks it); a port drag from `star_align.bam` to
  `samtools_sort.input` calls `/edits` with that edge; a wire's remove control drops it;
  `Picker` on an open input lists compatible tools and adds one wired; the zoom buttons change
  the view transform; rename `PUT`s the name; `Findings` lists the preview's findings and
  selecting one selects its step.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement, reusing the manual components rather than
  redrawing them. **Step 4:** Run — PASS.
- [ ] **Step 5: browser.** `make dev`; on a session mid-walk: delete trimgalore → the chat offers
  the role reading; *Yes* → the canvas re-plans and the log says so. Draw a wire, use Picker,
  zoom, rename. 1440×900 and 390 wide. Screenshots in the journal.
- [ ] **Step 6:** Commit `feat(build): the manual builder's controls in the one builder (#395)`.

### Task 8: the readings show as the engine's, and the manual builder goes

**Files:**
- Modify: `frontend/src/build/living/blocks/SuggestionCard.tsx` (a card with `edit` set reads
  *from your edit* instead of the model's label, and a group shows as one card with one
  *Yes* / *No, undo*), `CurrentFacts.tsx` (the manual-work note), `LivingSurface.tsx` (*Open
  preserved manual work*), `useAuthoringSession.ts` (`onFork`, `edit`'s response),
  `LivingBuilder.tsx`
- Delete: `frontend/src/build/Builder.tsx`, `Builder.test.tsx`, `usePipelineDraft.ts` and its
  test, and every component only it imported (check each with `grep` before deleting: `Rail`,
  `Canvas`, `Node`, `Status`, `Panels`, `Shell.test` cases …); tests of reused pieces move.
- Test: `frontend/src/build/living/blocks/SuggestionCard.test.tsx`

- [ ] **Step 1: tests:** a grouped edit suggestion renders once, says the engine's sentence,
  is labelled *from your edit*, and *Yes* posts one apply.
- [ ] **Step 2:** Run — FAIL. **Step 3:** Implement and delete. **Step 4:**
  `npx vitest run && npx tsc -b`, `make check` — PASS; every inventory row ticked.
- [ ] **Step 5:** Commit `refactor(build): one builder (#395)`.

### Task 9: documents and the walk

- [ ] Docs: `docs/design/authoring-protocol.md` (no fork, `draw` start, edits read as intent),
  user-facing build pages that mention the manual builder or *preserved manual work*,
  `CHANGELOG.md` (mendel-api, mendel-authoring, frontend), guard ledger rows for Tasks 3–5,
  journal entry, this plan ticked with deviations; `make doc-sizes`.
- [ ] `make verify` — PASS.
- [ ] The spec's walk, as far as this plan reaches: open a pipeline from Home, ⌘K and by URL —
  one page; mid-walk hand edit read and confirmed; a drawn pipeline opened and read; Ollama up
  only for the walk, then down.
- [ ] Commit `docs: one builder plan 2 — ticked, deviations, journal (#395)`.

## Deviations

(recorded during execution)
