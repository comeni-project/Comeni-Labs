# 2026-08-25 — W2 against its artboards, and the run screens under use

**Method.** The nine artboards in [`docs/design/w2-mockups/`](../../docs/design/w2-mockups/) were
served and rendered beside the running app, screen by screen, at 1568×815 in the operator's own
Chrome (dark). Interaction was driven twice — headless Chromium at 1440×900 and the operator's
browser — so anything reported here reproduced in both engines unless it says otherwise. The
forge was excluded by instruction; it is being reworked.

**The artboards are the authority**, per the W2 journal. Where this file says *diverges*, it
means the build and the drawing disagree and the drawing wins unless somebody decides otherwise.

**Two of my own first results were wrong and are corrected here rather than quietly dropped** —
a `Shift+F10` "failure" that was my test focusing the wrong element, and tab-switch timings that
were measuring my own `sleep`. Both are recorded in *What passed* with the real numbers.

---

## 1. The one blocker

**A setting cannot be typed into.** `Builder.tsx:623` renders the settings card from
`data.steps` — the server's echo, a TanStack query with `placeholderData: (previous) => previous`
— while `:625` writes to `builder.setParam`, local state. The displayed value therefore never
advances between keystrokes, so every `onChange` receives `"" + newChar`. Typing `ILLUMINA`
leaves `A`. Reproduced by real keyboard and by native-setter events, 120ms apart, in both engines.

`useGraph.setParam` and `edit()` are both correct — this is purely the read path.

**Why 87 green steps missed it:** `Settings.test.tsx:137` is the only coverage and fires a single
`fireEvent.change` carrying the whole value, which never depends on the displayed value. No test
in `frontend/src/` types character-by-character. `<select>` params are unaffected, which is why
the enum path looks healthy.

**This is the builder's only route to answering a tier-4 question.**

---

## 2. Global divergences — every run screen

These are not per-screen bugs; they are one set of decisions the build did not carry over.

| # | artboard | built | note |
|---|---|---|---|
| G1 | second nav group `Board · This run` | absent | the artboards carry it on all nine |
| G2 | `↩ pipeline` link, top right | absent | the run→pipeline route back |
| G3 | elapsed right-aligned on the title line (`7m12s`) | own line below, `38S ELAPSED` | |
| G4 | phase dot inline after the run id (`run 85bbe6a0ing`) | far right of the header | |
| G5 | progress bar inline beside `3 of 5 steps finished`, `DECLARED BY THE ARTIFACT` to its right | full-width bar on its own row, caption inline | |
| G6 | active tab is a **filled pill** | bold text only | |
| G7 | a **bottom caption bar** on every panel, uppercase letterspaced — `DAG-CORE'S LAYOUT · …`, `KEPT, AND NO LONGER THE FRONT DOOR · …` | folded into a lowercase footer, or absent | the captions carry the design's argument |
| G8 | `NOT STARTED` rows: name dimmed, status stacked under it | plain dimmed text in the Tasks cell | |

---

## 3. Per-artboard

### `Graph.dc.html` — the largest divergence, and it is currently unusable

**The tab does not render.** `[data-testid=canvas]` computes to **15px tall** while the SVG
inside it is **568px**. The data is intact — four nodes, three wires. The cause is CSS: the canvas
carries `flex-1 min-h-0`, but its parent `<section>` is `bg-surface border … overflow-hidden`
with no `flex flex-col` and no height, so it wraps to content and `flex-1` has nothing to expand
into. Adding `flex flex-col flex-1 min-h-0` to that `<section>` took it from 15px to 690px live in
the page — the diagnosis is demonstrated, not asserted.

This is the same class as `6172b76` on `main` ("the canvas had no height, so the graph rendered
into nothing"), now in the run graph.

Once it renders, it still diverges:

| artboard | built |
|---|---|
| **horizontal**, left to right | **vertical**, top to bottom |
| an `entry · reads / 12 samples` node | no entry node |
| three edge kinds — solid done, **orange dashed active**, faint dotted not-started | one thin grey edge |
| node subtitles in words: `12 done · 1 retried`, `3 done · 9 more seen`, `not started` | `1 / 1` |
| node borders encode state — green solid, **orange dashed retried**, orange solid partial, grey | green box |
| the caption sits in the bottom bar | caption at the top, **overlapped by the first node** |

`Show in graph` on the process-row menu navigates correctly to `?view=graph` — and therefore
lands the reader on the broken panel.

### `Console.dc.html`

| artboard | built |
|---|---|
| `process ▾` and `status ▾` filter controls | **neither exists** |
| `filtered from the overview — show everything` | absent |
| `tailing` indicator | absent from the console |
| `20:31:04 ✓ STAR_ALIGN (sample_01)` | `STAR_GENOMEGENERATE (STAR_GENOMEGENERATE (genome.fasta))` — **the process name twice** |
| right column carries duration / `exit 137` in red | `—` on nearly every line |
| a failed line has a red left border and a red-tinted row | `✗` glyph only, no row treatment |
| indented annotation: `retrying · attempt 2 of 3, memory doubled by errorStrategy` | absent |
| `— 38 of 412 events · STAR_ALIGN only —` | `— 14 events · not following —` |

The console shipped without its filtering, which is the artboard's stated point: *"kept, and no
longer the front door · zoom and filter, not tail -f."* Without filters it is tail -f.

### `Main.dc.html` — the overview

**The bars are the finding.** The artboard draws **thick filled blocks (~8px) above the number**,
one hue per column — memory orange, cpu green, time and io grey. The build draws **1px hairlines
under the number**, coloured green/orange by value.

That single change is why Checkpoint 3's own question fails: *"does a column of bars let you name
the memory hog in under two seconds?"* Against the artboard, yes. Against the build, no — every
memory bar is a nub and you must read the digits, which is what the bars exist to avoid.

Also diverging: `STAR_ALIGN v2` retry badge (absent), `3 done / 9 MORE SEEN` as two lines
(built shows one line), `PROGRESS` as a bar alone (built adds `1/1` text).

### `Tasks.dc.html` — the closest match

Genuinely good, and the only screen where the numbers are formatted correctly. Diverges on:
the **`attempt any ▾` filter is missing**; `↻ retried only` is a plain checkbox rather than the
artboard's chip button; columns are right-aligned where the artboard left-aligns; the
`↻ retried once` in-row annotation is absent; and the artboard's `404 more · only what fits the
window is drawn` overflow note has no equivalent.

### `Failure.dc.html`

The build has the *information* and not the *design*.

| artboard | built |
|---|---|
| a **resource bar** in the banner — `peaked at 63.8 of 64 GB asked` | absent |
| the error block is a **3-line excerpt** of the salient lines | the whole `errorReport`, ~650px in a 254px scroll box, clipped mid-line |
| the failing process row is **auto-expanded**, failing task highlighted, `killed — out of memory`, `9 more · the failing task and its siblings first` | nothing expands |
| red-tinted banner background, full border | dark background, red left border |
| `FROM THE RECORD · NOTHING INTERPRETED` top-right, uppercase | under the headline, lowercase |

**Not judgeable from current data:** the artboard's banner names the tag
(`STAR_ALIGN (sample_07) …`). Every failed run in the database predates A200's `labels` column —
all five carry `tag: null` — so whether the banner names a tag cannot be tested until a run fails
*after* today's projection. The journal already flags this for `0d3a4e3d` as an expected
fallback. **Checkpoint 4 cannot fully validate the banner without a fresh failed run.**

---

## 4. Defects independent of the artboards

**The overview destroys measured values.** `memory_peak_bytes: 3809280` — 3.8 MB — renders
`0.0 / 31 GB`, under a footer that says *"— means nothing was reported, never zero."* The screen
asserts a zero the record contradicts. The **Tasks tab formats the same field correctly as
`3.6 MB`**, so the formatter exists and the overview does not call it. `1273368576` also renders
`1.2`, not `1.3` — it truncates.

**The CPU column changes basis between parent and child.** Header promises `CPU USED / ASKED` and
one number appears. Process row `8%`; expand it and its only task says `100%`. Both derive from
`cpu_used_pct: 100.2` and `cpus_asked: 12` — correct arithmetic, same `%` glyph, different
denominators, one click apart.

**`bar-time` is duplicated four times.** Every other bar testid is suffixed
(`bar-mem-STAR_ALIGN`); the time bar is a bare `bar-time` on all four rows. Any
`getByTestId('bar-time')` is a strict-mode violation or a silent first-match.

**The builder rail renders ghost state after Keep** — literally `kept kept`, and Lint/Preview
drawn twice, a dead pair above a live pair. Transient; clears on the next state change.

**The provenance legend disagrees with the rest of the screen** — legend `6 Undecided`, header
`5 needs your decision`, title `5 to decide`, review rail `5`.

**The builder canvas lays out ~266px underneath the right rail** — `canvasRight: 1243` while the
rail begins near 977; the `genome.index.star` wire label is drawn into the hidden strip. The
canvas is also not fitted on load, and `alignment.bam` has a wire drawn through it.

**The runs board is unfinished relative to its neighbours** — a ~540px column in a 1440px
viewport while every other screen is full-width, ~91px rows for three fields, and no filter, sort
or search across 17 runs, while the Tasks tab inside a single run offers three filters.

---

## 5. What passed

**Checkpoint 5 is a clean pass**, including the trap. Menus open on the board row, process row,
task row, console line, graph node and graph background; `Shift+F10` and the `ContextMenu` key
both open one on a focused row; `Escape` closes it and returns focus to the row; `ArrowDown`
enters it; and **right-clicking a text selection yields Chrome's own menu**, so *Copy* is not
stolen. W4 verbs are listed and dimmed. *(My first pass reported "NO MENU" — that was my error:
focus was on a tab button, not a row.)*

**Checkpoint 6's hardest question passes.** Change a kept pipeline and the rail retreats, in
words, without a hover: *"You have changed it since you kept it. Keep again to gate the new
version."* Gate and Run re-disable; the review rail updates to *"set in the builder, drawn by a
person, with no reason given."*

**The zero-task failed run is handled better than the artboards asked.**
`456388f9` renders *"no task failed — the run stopped before one started"* — a precise sentence
for a case no artboard draws.

**Views are linkable.** `?view=console`, `?view=graph`, `?view=tasks` all round-trip, and the
failure banner correctly stays pinned above every view rather than living on the Overview.

**Health.** Zero console errors and zero failed network requests on `/`, `/runs`, `/runs/:id` and
`/build`. Page loads ~1.2s. Tab switches **16–32ms**, measured rAF-to-rAF with no sleeps.

---

## 6. Why it reads uglier than the artboards — measured, not eyeballed

**Every colour token matches. What diverges is size, weight, shape and emphasis.** The build
took the palette and applied it at roughly half scale, and the result is a screen with the right
hues and no hierarchy. These are computed styles, artboard and app side by side, dark, 1568×815.

| element | artboard | build | effect |
|---|---|---|---|
| **bar track height** | **7px** (8px on the header bar) | **2px** | the small-multiple reading is gone; a memory bar is a hairline |
| bar track colour | `--surface-2` `rgb(31,36,38)` | `--line` `rgb(42,49,52)` | the groove reads as a rule, not a well |
| bar shape | `3px` radius — a slab | `rounded-full` (`3.4e7px`) — a pill | at 2px tall a pill is a lozenge |
| bar / label order | **bar above, number below** | **number above, bar below** | the eye lands on digits first, which is what the bars were for |
| **row height** | **55px** (64 for a two-line cell) | **41px** | 25% tighter; no breathing room between rows |
| **active tab** | a **pill** — `--surface` fill, `5px 13px`, `3px` radius | transparent, `0` padding, `0` radius | the tab strip reads as four words, not a control |
| **tab strip** | **48px**, padding `9px 16px` | **29px**, padding `4px 10px` | the whole strip is 40% shorter |
| ~~panel shadow~~ | ~~`--e2`, two layers~~ | ~~transparent~~ | **WRONG — withdrawn, see below** |
| column header letterspacing | `.08em` (0.8px) | `.14em` (1.4px) | wider and looser than drawn |
| caption bar | its own bar — `margin-top:auto`, `border-top`, `--surface-2`, `10px 24px` | 15px of unstyled text, no bar | the design's argument reads as a stray line |

**Three of the five bar tints are wrong, and two of them are misleading:**

| column | artboard | build |
|---|---|---|
| progress | `--pea` green | `--pea` ✓ |
| memory | `--measured` orange | `--measured` ✓ |
| **cpu** | `--pea` **green** | `--measured` orange ✗ |
| **worst realtime** | `--ink-2` **grey** | `--pea` green ✗ |
| **read / written** | `--ink-2` **grey** | `--pea` green ✗ |

Realtime and I/O are **neutral measurements** in the artboard — grey, because longer is not
worse and there is nothing to be pleased about. The build paints them `--pea`, the same green it
uses for *done* and for a passing gate. That is why the failed run's `28ms` realtime draws a
**full-width green bar on the row that killed the run**: the column is scaled to its own maximum,
that row is the maximum, and green is the app's word for success.

**Two rows above were wrong, and are withdrawn rather than quietly deleted.**

- **The panel shadow is correct.** It computes to `--e2` exactly, in both themes. My probe
  truncated `boxShadow` at 50 characters and read only Tailwind's four transparent placeholder
  layers, which sit *before* the real ones — `rgba(0,0,0,0) 0px 0px 0px 0px` ×4, then
  `rgba(0,0,0,.5) 0px 1px 2px` and `0px 6px 16px -10px`. Nothing was wrong and nothing was
  changed. A measurement that slices a value is not a measurement.
- **The `6 Undecided` / `5 needs your decision` split is not a disagreement.** They count
  different things: `provenance` tallies tier-4 **decisions**, `needs_review` lists **steps**.
  Six decisions over five steps — both true. What was missing was the noun, so the header now
  reads *"5 steps need your decision"*. No number moved.

**So the honest summary of "uglier" is three things, in order of effect:**

1. **No emphasis.** Bars at 2px and rows at 41px flatten every level of the hierarchy the
   artboards drew.
2. **No focal control.** The active-tab pill is the one piece of solid fill on the panel and it is
   absent, so nothing on the screen says *you are here*.
3. **Colour doing the wrong job.** Green on neutral columns spends the palette's only positive
   signal on facts that carry no valence.

None of this needs new design work — every value above exists in the artboards and every token
already exists in `tokens.css`.

## 7. Suggested order

1. The settings-card read path — it blocks the builder's purpose, and it is a small fix.
2. The run graph's `<section>` height — four classes, and it un-breaks a whole tab.
3. **§6 in one pass** — bar height, track colour, bar/label order, the three tints, the tab pill,
   the panel shadow, row height. Every value is already drawn and every token already exists, so
   this is transcription rather than design, and it is the single largest change in how the app
   reads. The two wrong tints are also a correctness fix, not only a visual one.
4. The overview's number formatting — `pair()`'s one-unit rule is deliberate and documented, so
   the fix is not "call `bytes()`": keep one unit **unless the shared unit would print the used
   half as `0.0`**, and fall back to per-half units there. That preserves comparison at a glance
   in the normal case and stops the table contradicting its own "never zero" footer.
5. The console's two filters and the doubled process name.
6. `bar-time`'s testid; the `kept kept` ghost; the `6`/`5` legend.

Everything in §2 is a decision rather than a bug: the artboards carry a sub-nav, a pill tab and a
caption bar the build does not, and somebody should say whether those are being adopted or
dropped before the branch merges.

---

## 8. What was fixed — 2026-08-25

Frontend only. `tsc -b` clean, **266 of 266** frontend tests pass, `oxlint` 0 errors, and every
change below was checked in a browser against a real run rather than only in a test.

| # | change | files |
|---|---|---|
| 1 | **The settings card reads the local graph over the server's echo.** `withTypedValues` overlays `value` only — the tier, domain and reason stay the server's to stamp. | `useBuilder.ts`, `Builder.tsx` |
| 2 | **The run panel is a flex column that fills.** The graph canvas gets its height, and the panel's caption bar sits at its foot. | `Run.tsx` |
| 3 | Graph legend became the artboards' **bottom caption bar** — it was an unpositioned flow child under an absolute stage, so the first node covered it. | `Graph.tsx` |
| 4 | **Bars: 7px, `--surface-2` track, 3px radius, bar above the number.** | `Overview.tsx` |
| 5 | **Tints: cpu green, realtime and I/O grey.** The two grey ones are a correctness fix — a full `--pea` bar sat on the row that killed a failed run. | `Overview.tsx` |
| 6 | `bar-time` → `bar-time-${process}`. | `Overview.tsx` |
| 7 | Row `13px 18px 13px 24px`, gap `18px`, header letterspacing `.08em`, footer a real `--surface-2` bar on `mt-auto`. | `Overview.tsx` |
| 8 | **The active tab is a pill**, and the strip is the artboards' height. | `Run.tsx` |
| 9 | `pair()` falls back to per-half units where one unit would round a real peak to `0.0`. | `units.ts` |
| 10 | Console gained **`process` and `status` filters**, both derived from the events in hand. | `Console.tsx` |
| 11 | Console line prints the **tag**, not `PROCESS (PROCESS (tag))`. | `Console.tsx` |
| 12 | `keptAt` is a real time, so the rail says `kept 12:28:38` rather than `kept kept`. | `useKeep.ts`, `Builder.tsx` |
| 13 | The Gate step's duplicate Lint/Preview pair removed — `GatePanel` already renders them with state these could not have. | `Walk.tsx` |
| 14 | `5 steps need your decision`, to separate steps from decisions. | `Provenance.tsx` |

**Three guards were added or corrected, and the first was watched failing against the defect:**

- `Builder.test.tsx` — types `ILLUMINA` one key at a time with `userEvent` and asserts the field
  accumulates. It failed with `''` before the fix. The pre-existing `Settings.test.tsx` fires one
  `change` carrying the whole value and passes on the broken code either way, which is why 87
  green steps missed this.
- `units.test.ts` — new; asserts a 3.8 MB peak against a 31 GB ask never draws as `0.0`.
- `Overview.test.tsx` — was reading `getAllByTestId("bar-time")` and indexing into it, so it
  **passed because of** the duplicate testid. Now addresses `bar-time-SLOW` / `bar-time-FAST`.

**`npx tsc --noEmit` is not the gate — `tsc -b` is.** A real type error in the overlay
(`DraftParam.value` is `string | number | boolean`, `SettingView.value` is `string`) passed
`--noEmit` and failed the production build. Use `npm run build` or `tsc -b`.

### A second pass, the same day — §2 and §3 taken on

The operator walked the screens and the answer to §2/§3 was *adopt them*. What that took:

| area | change |
|---|---|
| the expanded / Tasks table | the `1fr` was on **tag**, so it ate the width and pushed every figure to the right edge. Now the artboard's `120px 60px 70px 110px 90px 100px 1fr`, indented 46px, `1fr` last as the annotation slot |
| Tasks `attempt` filter | needed a **backend filter**, not just a control — see the NULL trap below |
| the console | rewritten as flowing mono text: no row rules, `line-height 1.95`, duration floated right, a failed line lifted out as a tinted block |
| the run graph | horizontal, word subtitles, stroke-carries-state on a plain surface, dashed `--measured` retry ring, three edge kinds, the well instead of the builder's dotted grid |
| the header | the `--surface-2` shelf, phase inline beside the id, elapsed right, progress bar inline and capped at 520px |
| the failure banner | a tinted `--undecided-soft` block with a full border — it was a white card with a red stripe, which is the treatment the console gives one *line* |
| the caption | `every bar shares its column's scale · …` deleted at the operator's request |
| **the board** | built from the new artboard: four tiles, a fortnight of runs per day, filters, pagination. `GET /api/runs` is now a page; `GET /api/runs/summary` is new |

**Two honest deviations from the drawing**, both forced by what the API can afford: the board
says **TASKS** rather than `STEPS` (`steps_declared` is in the artifact, and reading one per row
is the cost the old board's comment was right about — tasks are one `GROUP BY` over `run_task`),
and it has **no `PIPELINE` column**, because no field names what was run.

The graph also kept the **full** `errorReport` rather than the artboard's three-line excerpt:
cutting a real report at three lines hides the half that matters.

### Three defects of one family, and the family is the lesson

`tsc` clean, tests green, rendered wrong. **None was reachable except by opening the page.**

- **The run graph's canvas computed to 15px** — `flex-1` with no flex parent.
- **A Tailwind class built by concatenation** (`"grid-cols-[" + "...]"`) is never generated,
  because the scanner reads source text. The board's every row collapsed into a vertical stack.
  A computed track list belongs in `style`.
- **A `position: fixed` menu inside a `transform`ed ancestor** is positioned against that
  ancestor. The graph's context menu drifted by exactly the pan. `Builder.tsx` renders its menu
  as a sibling for this reason; the run graph did not.

**And one that a test was hiding.** `Overview.test.tsx` read `getAllByTestId("bar-time")` and
indexed it — passing *because of* the duplicate testid it should have caught.

### The NULL trap under the attempt filter

`attempts` is a JSON column. `json_array_length` answers NULL for SQL NULL but **0** for the
JSON value `null`, which is what SQLAlchemy stores for a Python `None`. A bare `= 1` therefore
returned an empty table for *attempt 1* — precisely the rows it was asked for, and silently,
since an empty table looks like a filter that matched nothing. The filter mirrors `TaskOut`'s
`len(row.attempts or []) or 1` in SQL: `coalesce(nullif(json_array_length(...), 0), 1)`.

### Guards watched failing, not merely written

- the settings field, typed one key at a time — failed with `''`
- `/runs/summary` declared after `/runs/{run_id}` — failed with `404`
- the graph menu moved back inside the stage — failed with `expected true to be false`

### Still not done

`wiener_core.overview` counts `ABORTED` as failed, so one run reads *1 failed* on the overview,
carries a `✗` without the console's failed-block, and is not named in the banner — it was
aborted, collateral of another process's failure. Three surfaces, three readings of one word.
That is a meaning decision in a **pure** package with determinism guarantees, so it is the
operator's to make and was left alone.

The artboards' `Board · This run` sub-nav and `↩ pipeline` link (§2 G1/G2) are adopted only
where a run was reached from a pipeline; the sub-nav is still absent.

`pair()` also rounds `61.2 GB` to `61` where the artboard draws `61.2` — a decimal only below 10
is its existing rule. Left alone: changing it moves every number on the screen.
