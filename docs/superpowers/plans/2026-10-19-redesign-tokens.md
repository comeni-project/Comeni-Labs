# Redesign 1 — Tokens and Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repaint the whole frontend in the hybrid identity — colour tokens named by meaning, light-first, Lexend and Geist Mono, rounder shapes, no arc field — without changing any layout.

**Architecture:** `frontend/src/tokens.css` holds every value; `frontend/src/main.css`'s `@theme` mirrors them as Tailwind utilities; components only name tokens. Each task changes the token file, its mirror and every call site together, guarded by `frontend/src/tokens.test.ts`, which reads the stylesheets and sources as text.

**Tech Stack:** React 19, Tailwind v4 (`@theme`), Vitest, `@fontsource-variable/*`.

**Spec:** `docs/superpowers/specs/2026-10-19-redesign-tokens-design.md` (issue #371).

## Global Constraints

- No layout changes: only colours, fonts, sizes of the type roles, radii, shadows and the removed field.
- Components never name a colour (the existing *names no colour outside the token file* test stays green).
- Fonts are bundled with `@fontsource`, never fetched (invariant 13).
- No backward compatibility before v0.1.0: retired names are deleted, not aliased.
- Text tokens reach 4.5:1 against every ground they are listed against, in both themes.
- Run frontend checks from `frontend/`: `npx vitest run`, `npx tsc -b`, `npm run lint`. Run each separately before committing; stage explicit paths only (never `git add -A`: `docs/notes/research/2026-10-17-why-not-mcp.md` is someone else's).

## Review Focus

1. **A dark OS with Appearance set to Light** must paint light: the dark media block is guarded by `:root:not([data-theme="light"])`. Pinned in Task 1's structure test.
2. **The focus ring** must survive the rename: `--ring` uses `--now`. Pinned in Task 1.
3. **Arbitrary-value call sites** (`text-[var(--link)]`, `border-[var(--fault)]`) escape a utility-only scan. Task 1's retired-name test scans `--name` anywhere, not only utilities.
4. **A chip's text on its own soft ground in dark mode.** Task 1's contrast test pairs each `-ink` with its `-soft`.
5. **A label that shows data** (an id or a digest) must keep `font-data` when its uppercase goes. Task 3 removes `font-data` only from className strings that also carry `uppercase`.

---

### Task 1: The palette, named by meaning

**Files:**
- Modify: `frontend/src/tokens.css` (all colour blocks)
- Modify: `frontend/src/main.css` (`@theme` colour mirror, lines ~76-103)
- Modify: every `.tsx`/`.ts`/`.css` under `frontend/src` that names a retired token
- Test: `frontend/src/tokens.test.ts`

**Interfaces:**
- Produces (test helpers in `tokens.test.ts`, used by Tasks 3-5): `palette(theme: "light" | "dark" | "media"): Map<string, string>` — the custom properties set in `:root {…}`, in `:root[data-theme="dark"] {…}`, and in the `@media (prefers-color-scheme: dark)` block; `contrast(a: string, b: string): number` — the WCAG 2 ratio of two `#RRGGBB` colours.
- Produces (tokens): `--done`, `--done-soft`, `--done-ink`; `--action`, `--on-action`, `--action-edge`; `--measured`, `--measured-soft`, `--measured-ink`; `--needs-you`, `--needs-you-soft`, `--needs-you-ink`; `--now`, `--now-soft`, `--now-ink`, `--now-line`; `--canvas`; and their `--color-*` mirrors.

The values (light / dark):

| Token | Light | Dark |
|---|---|---|
| `--paper` | `#F4F5F8` | `#12141B` |
| `--paper-2`, `--surface` | `#FFFFFF` | `#1A1D27` |
| `--surface-2`, `--canvas` | `#F8F9FB` | `#161820` |
| `--line` | `#E1E4EC` | `#282C3A` |
| `--line-2` | `#C9CEDB` | `#3A3F52` |
| `--line-soft` | `#ECEFF5` | `#232736` |
| `--ink` / `--ink-2` / `--ink-3` | `#171A26` / `#474D63` / `#666C84` | `#E8EAF2` / `#B0B5C8` / `#8C92A8` |
| `--done` / `-soft` / `-ink` | `#0F9D7A` / `#DDF3EC` / `#0B6B53` | `#2FC79B` / `#113529` / `#2FC79B` |
| `--action` / `--on-action` / `--action-edge` | `#0B7F63` / `#FFFFFF` / `#075C48` | `#2FC79B` / `#06201A` / `#1E8C6C` |
| `--measured` / `-soft` / `-ink` | `#9A5B00` / `#FBF0DC` / `#7A4800` | `#F0B840` / `#35290F` / `#F0B840` |
| `--needs-you` / `-soft` / `-ink` | `#C92F36` / `#FCE5E6` / `#A1242B` | `#FF6E73` / `#3A1B20` / `#FF6E73` |
| `--now` / `-soft` / `-ink` / `-line` | `#2F6FEB` / `#E6EEFD` / `#1F57C3` / `#A9C2F5` | `#6EA2FF` / `#172642` / `#6EA2FF` / `#2A4170` |
| `--node` | `#FFFFFF` | `#1A1D27` |
| `--node-line`, `--port-line` | `#C9CEDB` | `#3A3F52` |
| `--node-rule` | `#E1E4EC` | `#282C3A` |
| `--rail`, `--mark` | `#B3B9CA` | `#4A5068` |
| `--grid-1` / `--grid-2` | `rgba(40, 60, 110, .055)` / `rgba(40, 60, 110, .028)` | `rgba(140, 170, 255, .06)` / `rgba(140, 170, 255, .03)` |
| `--shadow` | `rgba(23, 26, 38, .25)` | `rgba(0, 0, 0, .7)` |
| `--scrim` | `rgba(23, 26, 38, .38)` | `rgba(0, 0, 0, .6)` |

`--grid-3` goes (the boards draw two rulings); its call sites use `--grid-2`. `--ring` becomes `0 0 0 2px var(--paper), 0 0 0 4px var(--now)`. `--panel`, `--scan-line` and `--rule-line` stay until Task 5.

The rename map for call sites (`var(--x)`, `[var(--x)]`, and the utilities `text-/bg-/border-/fill-/stroke-/ring-/outline-/decoration-x`):

| Old | New |
|---|---|
| `pea` that fills a button whose text is `on-pea` | `action` (and `on-pea` → `on-action`) |
| every other `pea`, `pea-soft` | `done`, `done-soft` |
| `undecided`, `undecided-soft`, `fault` | `needs-you`, `needs-you-soft`, `needs-you` |
| `running`, `running-soft`, `link`, `link-soft` | `now`, `now-soft`, `now`, `now-soft` |
| `link-line` | `now-line` |
| `ink-4` | `ink-3` |
| `text-pea`, `text-fault`, `text-undecided`, `text-running`, `text-link` on words (not a filled mark) | `text-done-ink`, `text-needs-you-ink`, `text-needs-you-ink`, `text-now-ink`, `text-now-ink` |

- [ ] **Step 1: Write the failing tests** in `tokens.test.ts`, with the helpers above:

```ts
it("sets the same tokens in every theme", () => {
  const light = [...palette("light").keys()].sort();
  expect(light.length).toBeGreaterThan(30);
  expect([...palette("dark").keys()].sort()).toEqual(light);
  expect([...palette("media").keys()].sort()).toEqual(light);
  expect(palette("media")).toEqual(palette("dark"));
});

it("lets an explicit light choice beat a dark system", () => {
  const css = readFileSync(join(SRC, "tokens.css"), "utf8");
  expect(css).toMatch(/@media \(prefers-color-scheme: dark\)\s*{\s*:root:not\(\[data-theme="light"\]\)/);
  expect(palette("light").get("--ring")).toContain("var(--now)");
});

it("keeps every text colour readable on the grounds it is drawn on", () => {
  const TEXT_ON_GROUNDS: [string, string[]][] = [
    ["--ink", ["--paper", "--surface", "--canvas"]],
    ["--ink-2", ["--paper", "--surface", "--canvas"]],
    ["--ink-3", ["--paper", "--surface", "--canvas"]],
    ["--done-ink", ["--paper", "--surface", "--done-soft"]],
    ["--now-ink", ["--paper", "--surface", "--now-soft"]],
    ["--measured-ink", ["--paper", "--surface", "--measured-soft"]],
    ["--needs-you-ink", ["--paper", "--surface", "--needs-you-soft"]],
    ["--on-action", ["--action"]],
  ];
  const failing: string[] = [];
  for (const theme of ["light", "dark"] as const) {
    const p = palette(theme);
    for (const [text, grounds] of TEXT_ON_GROUNDS) for (const ground of grounds) {
      const ratio = contrast(p.get(text)!, p.get(ground)!);
      if (ratio < 4.5) failing.push(`${theme}: ${text} on ${ground} is ${ratio.toFixed(2)}`);
    }
  }
  expect(failing).toEqual([]);
});

it("keeps retired colour names retired", () => {
  // A utility prefix or `--` is required: `dead-link` is a word, `text-link` is a token.
  const NAMES = "pea|on-pea|undecided|fault|running|link|ink-4";
  const RETIRED = new RegExp(`--(?:${NAMES}|grid-3)\\b|\\b(?:text|bg|border|fill|stroke|ring|outline|decoration|accent|caret|divide|placeholder|from|via|to)-(?:${NAMES})(?:-soft|-line)?\\b`);
  const found = sources().filter(([, text]) => RETIRED.test(text)).map(([path]) => path);
  expect(found).toEqual([]);
});
```

Also update *reaches the utilities it checks*: `text-ink-4` → `text-ink-3` and `text-now-ink`.

- [ ] **Step 2: Run them and watch them fail**

Run: `npx vitest run src/tokens.test.ts`
Expected: the retired-name test lists ~60 files; *sets the same tokens* fails on the missing dark block; *contrast* fails reading undefined `--canvas`. Note the exact failures for the guard ledger (Task 6).

- [ ] **Step 3: Rewrite the colour blocks of `tokens.css`** — `:root` light, `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }` and `:root[data-theme="dark"] {…}` with the dark values, both dark blocks identical. Replace the Observatory header comment with a short one saying what the file is and pointing to `docs/explanation/visual-identity.md` (written in Task 6). Mirror every new token in `main.css`'s `@theme` as `--color-<name>: var(--<name>)`, removing the retired ones.

- [ ] **Step 4: Rename the call sites** by the map above, one token family per commit (`pea`, `undecided`/`fault`, `running`/`link`, `ink-4`), running `npx vitest run && npx tsc -b` after each. Where `pea` is ambiguous, the rule is the table's: a fill behind `on-pea` text is `action`.

- [ ] **Step 5: Run the full suite**

Run: `npx vitest run` then `npx tsc -b` then `npm run lint`
Expected: all pass; component tests that asserted an old class name are updated to the new one, not deleted.

- [ ] **Step 6: Commit** each family as it lands (`refactor(frontend): <family> becomes <meaning> (#371)`), the tokens and tests first.

### Task 2: Light-first

**Files:**
- Modify: `frontend/src/app/useTheme.ts`
- Test: `frontend/src/app/useTheme.test.tsx`

**Interfaces:**
- Consumes: nothing new. Produces: `painted(theme: Theme): "light" | "dark"` — unchanged signature.

- [ ] **Step 1: Write the failing tests**: with `matchMedia` stubbed so `(prefers-color-scheme: dark)` matches, `painted("system")` is `"dark"`; with nothing matching (a browser that reports no preference), `painted("system")` is `"light"`; `painted("light")` and `painted("dark")` return themselves.
- [ ] **Step 2: Run** `npx vitest run src/app/useTheme.test.tsx` — expected FAIL on the no-preference case (today it returns `"dark"`).
- [ ] **Step 3: Implement**: `painted` queries `(prefers-color-scheme: dark)`; delete `forgetOldToggle` and its call.
- [ ] **Step 4: Run** the file again — PASS; then `npx vitest run`.
- [ ] **Step 5: Commit** `feat(frontend): light-first, dark when the system asks (#371)`.

### Task 3: Type

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json` (via `npm install @fontsource-variable/lexend@5.3.0 && npm uninstall @fontsource-variable/geist`)
- Modify: `frontend/src/main.css` (font imports, `--text-*` roles), `frontend/src/tokens.css` (`--font-*`)
- Modify: call sites of `text-object` and of labels carrying `uppercase`
- Test: `frontend/src/tokens.test.ts`

**Interfaces:**
- Produces: `--font-ui` and `--font-display` = `"Lexend Variable", "Lexend", system-ui, sans-serif`; `--font-data` unchanged (Geist Mono). Type roles in `@theme`: `--text-hero: 32px`, `--text-title: 22px`, `--text-heading: 16px`, `--text-lede: 15px`, `--text-body: 14px`, `--text-secondary: 13px`, `--text-label: 12px`, `--text-brand: 17px`. `--text-object` is renamed `--text-heading` (6 call sites).

- [ ] **Step 1: Update the failing tests.** In *sets every face…*: `--font-ui` and `--font-display` match `/Lexend/`, `--font-data` matches `/Geist Mono/`; `main.css` imports `@fontsource-variable/lexend` and `@fontsource-variable/geist-mono` and not `@fontsource-variable/geist"`. Add:

```ts
it("draws labels in the interface face, not shouted", () => {
  const shouting = sources()
    .filter(([path]) => path.endsWith(".tsx"))
    .flatMap(([path, text]) => [...text.matchAll(/className=(?:"|{`)([^"`]*)/g)]
      .filter((m) => /\btext-label\b/.test(m[1]) && /\buppercase\b/.test(m[1]))
      .map(() => path));
  expect(shouting).toEqual([]);
});

it("sizes the type roles as the boards do", () => {
  const main = readFileSync(join(SRC, "main.css"), "utf8");
  for (const [role, px] of [["hero", 32], ["title", 22], ["heading", 16], ["lede", 15],
    ["body", 14], ["secondary", 13], ["label", 12], ["brand", 17]] as const) {
    expect(main).toMatch(new RegExp(`--text-${role}: ${px}px;`));
  }
});
```

- [ ] **Step 2: Run** `npx vitest run src/tokens.test.ts` — expected FAIL (Geist, 13 px body, 61 shouting labels).
- [ ] **Step 3: Implement**: swap the packages and imports; set the font tokens and type roles; rename `text-object` → `text-heading`; in every className string that carries both `text-label` and `uppercase`, remove `uppercase`, its `tracking-[…]` and `font-data`, leaving `text-label text-ink-3` (or its existing colour). Leave `font-data` on any className without `uppercase` (Review Focus 5).
- [ ] **Step 4: Run** `npx vitest run`, `npx tsc -b`, `npm run lint`, `npm run build` (the build proves the font import resolves) — all PASS.
- [ ] **Step 5: Commit** `feat(frontend): Lexend for the interface, the boards' type sizes (#371)`.

### Task 4: Shape and the raised button

**Files:**
- Modify: `frontend/src/main.css` (`@theme` radii and shadows), `frontend/src/tokens.css` (`--r` removed)
- Modify: call sites of `rounded-r`, `rounded-[3px]`, `rounded-[2px]`, `var(--r)`; the primary buttons (`bg-action`)
- Test: `frontend/src/tokens.test.ts`

**Interfaces:**
- Produces: `@theme` radii `--radius-control: 8px`, `--radius-button: 10px`, `--radius-panel: 14px` (utilities `rounded-control`, `rounded-button`, `rounded-panel`; chips use Tailwind's `rounded-full`); `--shadow-raise: 0 3px 0 var(--action-edge)` (utility `shadow-raise`).

- [ ] **Step 1: Write the failing test**:

```ts
it("rounds corners with the three named radii only", () => {
  const square = sources().filter(([, text]) =>
    /\brounded-r\b|rounded-\[\d+px\]|var\(--r\)|--radius-r:/.test(text)).map(([p]) => p);
  expect(square).toEqual([]);
});

it("raises every main button", () => {
  const flat = sources().flatMap(([path, text]) => [...text.matchAll(/className=(?:"|{`)([^"`]*)/g)]
    .filter((m) => /\bbg-action\b/.test(m[1]) && !/\bshadow-raise\b/.test(m[1])).map(() => path));
  expect(flat).toEqual([]);
});
```

- [ ] **Step 2: Run** — expected FAIL listing the ~52 square call sites and the flat main buttons.
- [ ] **Step 3: Implement**: fields, inputs, selects, small toggles → `rounded-control`; buttons → `rounded-button`; bordered panels and bands → `rounded-panel`; canvas nodes → `rounded-button`; the `var(--r)` uses in `main.css` take the radius of what they draw. Add `shadow-raise` beside every `bg-action`.
- [ ] **Step 4: Run** `npx vitest run`, `npx tsc -b`, `npm run lint` — PASS.
- [ ] **Step 5: Commit** `feat(frontend): rounder shapes and a raised main button (#371)`.

### Task 5: The arc field goes

**Files:**
- Delete: `frontend/src/ui/Field.tsx`
- Modify: `frontend/src/app/Shell.tsx:5,125`, `frontend/src/build/Canvas.tsx:3,74`, `frontend/src/main.css` (the `.field-*` rules and their comment block), `frontend/src/tokens.css` (`--panel`, `--scan-line`, `--rule-line`), the 7 `bg-panel` and 4 `var(--panel)` call sites (→ `bg-surface` with the border they already have, or `border border-line` where they had none)
- Test: `frontend/src/tokens.test.ts`

- [ ] **Step 1: Replace** *draws the ground the artboards sit on* with:

```ts
it("paints a plain ground: no field, no translucent panels", () => {
  const shell = readFileSync(join(SRC, "app/Shell.tsx"), "utf8");
  expect(shell).not.toMatch(/<Field\b/);
  const left = sources().filter(([, text]) =>
    /\bfield-(?:breathe|spin|scan|rule|vignette)\b|--(?:panel|scan-line|rule-line)\b|\bbg-panel\b/.test(text))
    .map(([p]) => p);
  expect(left).toEqual([]);
});
```

- [ ] **Step 2: Run** — expected FAIL naming `Shell.tsx`, `Canvas.tsx`, `main.css`, `tokens.css` and the panel call sites.
- [ ] **Step 3: Implement** the deletions and replacements above. `body` keeps `background: var(--paper)`.
- [ ] **Step 4: Run** `npx vitest run`, `npx tsc -b`, `npm run lint` — PASS.
- [ ] **Step 5: Commit** `refactor(frontend): the arc field goes; panels are opaque (#371)`.

### Task 6: The rules get a home, and the guards a ledger

**Files:**
- Create: `docs/explanation/visual-identity.md`
- Modify: `docs/explanation/index.md` (one line linking it), `frontend/src/tokens.css` and `frontend/src/main.css` header comments (point to it; no Observatory history)
- Modify: `tests/fixtures/guard-ledger.md` (append rows)

- [ ] **Step 1: Write `visual-identity.md`** following `docs/how-to/development/documentation.md`: why Labs shares Comeni Code's identity; the five meanings (settled spends none; measured amber; needs you red; selected/now blue; valid/done teal-green) with their token names; text wears `-ink`, never the mark colour, and status ships with an icon and words; light-first with the dark palette kept; Lexend and Geist Mono, bundled; the type roles and radii; where the values live (`frontend/src/tokens.css`) and which test guards them. Derive no counts into prose.
- [ ] **Step 2: Link it** from `docs/explanation/index.md`, and replace the stale `docs/design/dashboard.md` references in `tokens.css` and `main.css` with it.
- [ ] **Step 3: Run** `make docs`, `make links`, `make doc-paths` (from the repository root) — PASS.
- [ ] **Step 4: Ledger.** For each new guard (Task 1's four, Task 3's two, Task 4's two, Task 5's one), break the code the smallest way (for example set `--ink-3` light to `#9AA0B4`; add `text-[var(--link)]` to one component; add `uppercase` back to one label), run it, record the failure message, revert, re-run green. Append one row per guard to `tests/fixtures/guard-ledger.md` under a `## Redesign 1, 2026-10-19` heading.
- [ ] **Step 5: Commit** `docs: the visual identity gets one home; guard ledger rows (#371)`.

### Task 7: Look at it

- [ ] **Step 1:** `make dev`, then in a browser at 1440×900 and 390×844, in light and in dark (Settings → Appearance): Home, the living builder canvas, a run page, and the Settings overlay. Compare palette, fonts and meanings against the *One meaning per colour* board on the redesign canvas. Layouts will differ (later parts); a wrong colour meaning, an unreadable text, a serif or an uppercase label is a defect.
- [ ] **Step 2:** Fix any defect test-first in the task that owns it; a defect outside this part's scope becomes a GitHub issue.
- [ ] **Step 3:** Tick this plan, record deviations under a *Deviations* heading here, and open the pull request for `redesign-tokens` against `main`.
