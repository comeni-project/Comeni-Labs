# Redesign 1 — tokens and type

**Issue:** #371 (parent #370). **Status:** approved 2026-10-19; implemented on `redesign-tokens` (plan: `docs/superpowers/plans/2026-10-19-redesign-tokens.md`).
**Boards:** the *Comeni Labs redesign* canvas (2026-10-19), above all *One meaning per colour*;
the forge canvas uses the same identity.

## Why

Every later redesign part is compared against boards drawn in the hybrid identity: Lexend and
Geist Mono, light-first, one meaning per colour. The app still paints Observatory: dark by
default, Geist for everything, a purple for *running* and a separate blue for *links*, and an
animated arc field behind the shell. Until the tokens change, no screen can match its board,
so this part comes first and changes how everything looks without changing any layout.

## What changes

### 1. Colours carry their meaning in their name

The hybrid identity gives each colour one meaning, and settled values spend none. The token
names change to say that meaning, so a call site reads as what it shows:

| Meaning | New token (with `-soft` and `-ink`) | Replaces | Light | Dark |
|---|---|---|---|---|
| Valid / done | `--done` | `--pea` | `#0F9D7A` | `#2FC79B` |
| The main button | `--action`, `--on-action`, `--action-edge` | `--pea`, `--on-pea` where it is a button | `#0B7F63` | `#2FC79B` |
| Measured | `--measured` | `--measured` | `#9A5B00` | `#F0B840` |
| Needs you (open, or went wrong) | `--needs-you` | `--undecided`, `--fault` | `#C92F36` | `#FF6E73` |
| Selected / now (running, on offer, inputs, links) | `--now` | `--running`, `--link` | `#2F6FEB` | `#6EA2FF` |

- **`-soft`** is the tinted background behind a chip or a selected row; **`-ink`** is the shade
  of the colour that text may wear on a white or soft ground (for example `#0B6B53`, `#1F57C3`,
  `#7A4800`, `#A1242B` in light). Text never wears the plain mark colour where it fails 4.5:1.
- **`--running` and `--link` are retired.** Running is *now*, so it is blue; a link is
  something you can select, so it is blue too and stops being its own colour.
- **`--fault` merges into `--needs-you`.** The boards draw a failure and an open value the same
  red, distinguished by icon and words, never by shade.
- Neutrals keep their roles with the hybrid values: `--paper` (`#F4F5F8`), `--surface`,
  `--canvas` (new: the builder's ground, `#F8F9FB`), `--line`, `--line-2`, `--line-soft`,
  `--ink`, `--ink-2`, `--ink-3`. **`--ink-4` goes:** at the hybrid's lightest grey it fails
  contrast as text, so its 43 uses move to `--ink-3`.
- Canvas tokens (`--node`, `--rail`, `--port-line`, the grid rulings) take the hybrid values;
  the grid becomes the boards' two rulings (80 px and 16 px).

**My call, for the operator to check:** renaming rather than re-valuing the old names. With
no users before v0.1.0 there is nothing to keep compatible, and `--pea` drawn blue-green
on a button and green on a done stage is the confusion this part exists to remove. The cost is
mechanical: about 500 call sites in about 60 files, renamed with the Tailwind utilities that
mirror them (`text-pea` → `text-done`).

### 2. Light-first, following the system

`:root` is the light palette. The dark palette applies under
`@media (prefers-color-scheme: dark)` (unless `data-theme="light"`) and under
`[data-theme="dark"]`. `painted()` in `app/useTheme.ts` flips to match: *system* is light
unless the system asks for dark. The Appearance setting is unchanged. The leftover
`forgetOldToggle` migration goes (no backward compatibility before v0.1.0).

### 3. Type

- **Lexend for the interface, Geist Mono for data.** Both are bundled with `@fontsource`
  (`@fontsource-variable/lexend` is added; `@fontsource-variable/geist` is removed). Self-hosted,
  not a Google Fonts link: an installation with no egress must render the same page
  (invariant 13).
- **The type roles take the boards' sizes:** hero 32, title 22, heading 16, lede 15, body 14,
  secondary 13, label 12, brand 17. The current body is 13 and labels are 10, which the boards
  never use. Labels stop being uppercase mono at 10 px; they are Lexend at 12 px in `--ink-3`.

### 4. Shape and depth

- Radii: 8 px (fields, small controls), 10 px (buttons, canvas nodes), 14 px (panels),
  full (chips). `--radius-r: 3px` and its 13 `rounded-[3px]` uses go.
- The main button is raised: `box-shadow: 0 3px 0 var(--action-edge)`.
- The elevation ramp stays, with `--shadow` set from the hybrid (`rgba(23,26,38,.25)`-based).

### 5. The arc field goes

`ui/Field.tsx`, its use in `app/Shell.tsx` and `build/Canvas.tsx`, the `field-*` rules in
`main.css`, and `--panel`, `--scan-line` and `--rule-line`. A panel is an opaque `--surface`
with a `--line` border again, as on every board.

### 6. The design rules get a home

`tokens.css` calls `docs/design/dashboard.md` §2 authoritative, but that page was deleted on
2026-09-02 (`83c873d5`), so nothing documents the colour rules today. A new
`docs/explanation/visual-identity.md` becomes their one home: the meanings table above, the
contrast rule, the type roles, light-first, and why Labs shares Comeni Code's identity. It is
linked from `docs/explanation/index.md`. `tokens.css`'s header comments are rewritten to say
what the file is now and point there; the Observatory history stays in the journal archive.

## Not in this part

- **No layout changes.** Screens keep their structure and only repaint. The shell is #372,
  Home and its first run follow, describe/build is #377.
- The registry's own boards and pages (the forge, #360) are built on these tokens later.

## Testing

`frontend/src/tokens.test.ts` already proves every referenced `var(--x)` is defined. It gains:

1. **Both palettes define the same tokens:** every name in the light `:root` is set in the dark
   block and in `[data-theme="dark"]`, so a token cannot exist in one theme only.
2. **Text contrast:** each text token (`--ink`, `--ink-2`, `--ink-3`, each `-ink`) against
   `--paper`, `--surface` and its own `-soft`, in both themes, is at least 4.5:1. This is
   computed from the hex values in `tokens.css`, not eyeballed.
3. **Retired names stay retired:** `--pea`, `--undecided`, `--fault`, `--running`, `--link`,
   `--ink-4`, `--panel` and their utilities (`text-pea`, `bg-link-soft`, …) appear nowhere in
   `src/`.

Each new check is watched failing before the change it guards: the contrast check against
today's `--ink-4`, the retired-name check against today's tree. The evidence goes in
`tests/fixtures/guard-ledger.md`.

Then a browser check at 1440 px and 390 px, light and dark: Home, the builder canvas, a run
page and Settings, compared against the *One meaning per colour* board. They will not match
their own boards yet, because their layouts are later parts. What must match is the palette,
the fonts and the meanings.

## Left to the plan

- The exact `-ink` shades in dark mode, chosen so that check 2 passes.
- The order of the rename, which can be one mechanical commit per token family, each with the
  suite green.
