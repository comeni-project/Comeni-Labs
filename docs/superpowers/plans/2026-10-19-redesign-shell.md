# Redesign 2 — The Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redraw the header every page sits in — mark, Build · Runs · Registry, jump search, help, settings — and build the jump search.

**Architecture:** `app/Shell.tsx` keeps the bar; a pure `app/jump.ts` filters pipelines and runs into targets; `app/Jump.tsx` draws the box and the dialog and owns ⌘K. The two lists come from the queries Home already makes, under the same query keys, so the cache is shared.

**Tech Stack:** React 19, react-router 7, TanStack Query 5, Tailwind v4 tokens from #371, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-19-redesign-shell-design.md` (issue #372).

## Global Constraints

- No layout change below the header.
- Colours, radii and type only from the tokens (`tokens.test.ts` must stay green): the current section is `bg-surface border border-line text-ink`, others `text-ink-2`; round buttons `rounded-full border border-line-2`.
- No lab name and no *Learn in Code* anywhere in the shell.
- The help address is one constant: `DOCS_URL = "https://github.com/comeni-project/Comeni-Labs/blob/main/docs/index.md"`.
- Nothing new on the server; tests use stubbed `fetch`, never a live server.
- Run from `frontend/`: `npx vitest run`, `npx tsc -b`, `npm run lint`, each separately before committing; stage explicit paths.

## Review Focus

1. **⌘K while typing in a field** (the describe box, a reason textarea) must still open the palette — unlike `useKeys`, which ignores fields. Pinned in Task 2.
2. **Two ⌘K presses** must not stack two dialogs; the second press while open keeps one open. Pinned in Task 2.
3. **A run with an empty name** is listed as `run <id8>`. Pinned in Task 2's filter test.
4. **Wiener down** (the runs request rejects) must not blank the palette. Pinned in Task 2.
5. **The settings overlay and the palette together:** opening one closes nothing else unexpectedly; Esc in the palette closes only the palette. Pinned in Task 2.

---

### Task 1: The bar

**Files:**
- Modify: `frontend/src/app/Shell.tsx` (the `<nav>` and its comments, the `Tab` helper)
- Create: `frontend/src/app/Shell.test.tsx`
- Modify: `frontend/src/app/router.test.tsx` only if an assertion names *Builder*

**Interfaces:**
- Produces: `export const DOCS_URL: string` in `app/Shell.tsx`; the bar keeps `aria-label="Comeni — home"` on the mark link (router tests rely on it) and is the page's only `navigation` landmark outside the Registry subnav.

- [ ] **Step 1: Write the failing tests** in `app/Shell.test.tsx`, rendering `routes` in a memory router at `/build` with `fetch` stubbed to answer `{}`:
  - `getByLabelText("Comeni — home")` has `href="/"` and contains the text *Comeni Labs* and an `svg`;
  - the navigation's links read `["Build", "Runs", "Registry"]` in order, and *Build* has `aria-current="page"` at `/build`;
  - `getByRole("link", { name: "Help" })` has `href` = `DOCS_URL`, `target="_blank"`, `rel` containing `noreferrer`;
  - `getByRole("link", { name: "Settings" })` has an `href` containing `settings=`;
  - `queryByText(/Learn in Code/)` and `queryByText(/lab$/i)` are null.
- [ ] **Step 2: Run** `npx vitest run src/app/Shell.test.tsx` — expected FAIL (*Builder*, no mark, no help).
- [ ] **Step 3: Implement** the bar per the spec: 60 px row (`h-[60px] flex items-center gap-[26px] gutter border-b border-line bg-paper`), the mark as inline SVG (a `--done` line, three stations with `--surface` fill and `--ink` stroke, `aria-hidden`), *Comeni Labs* at `text-brand font-bold`, tabs as `NavLink`s drawing the current one as the pill, then (pushed right with `ml-auto`) a slot for `<Jump />` (Task 2 fills it; render nothing yet), the help link, and the settings link with an inline gear SVG (`aria-label="Settings"`). Below 640 px the row is `flex-wrap`. Rewrite the header comments to describe the bar as it now is.
- [ ] **Step 4: Run** `npx vitest run` and `npx tsc -b` — PASS.
- [ ] **Step 5: Commit** `feat(frontend): the shell's bar — mark, Build, help, settings (#372)`.

### Task 2: Jump to a pipeline or run

**Files:**
- Create: `frontend/src/app/jump.ts`, `frontend/src/app/jump.test.ts`
- Create: `frontend/src/app/Jump.tsx`, `frontend/src/app/Jump.test.tsx`
- Modify: `frontend/src/app/Shell.tsx` (render `<Jump />` in Task 1's slot)

**Interfaces:**
- Consumes: `DraftsPage` (`components["schemas"]["DraftsPage"]`, rows with `id`, `name`, `steps`, `updated_at`) from `get("/pipeline/drafts")` under query key `["drafts"]`; `RunsPage` (Wiener, rows with `id`, `name`, `phase`, `submitted_at`) from `fromWiener("/api/runs?limit=25")` under `["runs", "board"]` with `retry: false` — the keys and calls `home/Home.tsx` uses.
- Produces:
  - `type Target = { kind: "pipeline" | "run"; id: string; label: string; detail: string; to: string; phase?: string }`
  - `function jumpTargets(query: string, drafts: DraftRow[], runs: RunRow[]): { pipelines: Target[]; runs: Target[] }` — case-insensitive; a pipeline matches on `name`, a run on `name` or an `id` prefix; at most 8 of each; pipelines most recently updated first, runs in the order given; an empty query returns the first 8 of each. A run's `label` is its name or `run <id8>`; `to` is `/build?draft=<id>` or `/runs/<id>`; a pipeline's `detail` is `<n> steps`, a run's is its phase.
  - `function Jump(): JSX.Element` — the box (a `button` reading *Jump to a pipeline or run* with a `⌘K` hint; at phone width an icon-only button with the same `aria-label`) and, when open, the dialog.

- [ ] **Step 1: Write the failing unit tests** in `jump.test.ts`: `"STAR"` matches pipeline `rnaseq-star` and run name `star-test` but not `chip-peaks`; `"b71e"` matches run id `b71e04d2…`; a run named `""` gets label `run b71e04d2`; nine matching pipelines return eight; empty query returns the newest pipeline first; `to` values are `/build?draft=<id>` and `/runs/<id>`.
- [ ] **Step 2: Run** `npx vitest run src/app/jump.test.ts` — FAIL (module missing). **Step 3:** implement `jumpTargets`. **Step 4:** PASS.
- [ ] **Step 5: Write the failing component tests** in `Jump.test.tsx` (routes in a memory router, `fetch` stubbed per URL as `home/Home.test.tsx` does):
  - Ctrl+K and Meta+K on `document` open `getByRole("dialog", { name: /jump/i })` with the field focused — **also when focus is in a `textarea`** (Review Focus 1);
  - a second Ctrl+K while open leaves exactly one dialog (Review Focus 2);
  - typing `star` lists the matching pipeline and run as `option`s; ArrowDown then Enter navigates to the second option's address (assert the router's `location.pathname` + `search`);
  - with `/api/runs` rejecting, pipelines are listed and the text *Runs could not be read* is shown (Review Focus 4);
  - typing `zzz` shows *Nothing matches "zzz"*;
  - Esc closes the dialog, focus returns to the jump button, and a settings overlay opened beforehand is still open (Review Focus 5).
- [ ] **Step 6: Run** `npx vitest run src/app/Jump.test.tsx` — FAIL. **Step 7: Implement** `Jump`: open state, a `keydown` listener on `window` for `(metaKey || ctrlKey) && key === "k"` (prevent default; set open; idempotent), a dialog (`role="dialog"`, `aria-modal`, `aria-label="Jump to a pipeline or run"`) on `--scrim` with a `rounded-panel bg-surface` box, an `input` with `role="combobox"` controlling a `role="listbox"` whose rows are `role="option"` with `aria-selected`; Esc handled on the dialog with `stopPropagation` so the settings overlay does not also close; focus returned to the opener on close. Run phase words wear `inkOf[phase]` from `runs/phases.ts`.
- [ ] **Step 8: Run** `npx vitest run`, `npx tsc -b`, `npm run lint` — PASS.
- [ ] **Step 9: Commit** `feat(frontend): jump to a pipeline or run, ⌘K (#372)`.

### Task 3: Look at it, and record it

- [ ] **Step 1:** In the browser (the dev stack, `API_HOST_PORT=8002` while port 8000 is taken), at 1440×900 and in 390 px frames, light and dark: the header on Home, Build, Runs and Registry; ⌘K from the describe box; a search; Esc. Compare against the redesign canvas's Home header.
- [ ] **Step 2:** Fix defects test-first; anything outside the shell becomes an issue.
- [ ] **Step 3:** Add a CHANGELOG line under `frontend` → *Changed* (the header, jump search, help), tick this plan with a *Deviations* heading, set the spec's status, and record any new guard in `tests/fixtures/guard-ledger.md`.
- [ ] **Step 4:** Final whole-branch review, then merge locally as for #371.
