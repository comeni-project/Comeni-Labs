# Redesign 2 — the shell

**Issue:** #372 (parent #370). **Status:** proposed, awaiting the operator's approval.
**Board:** *Home — what needs you, then your pipelines* on the redesign canvas (its header), and
the header of every other board there.

## Why

The header is on every screen, so it is the second thing every later part is compared against,
after the tokens (#371). Today it is the word `Comeni`, three text tabs (*Builder*, *Runs*,
*Registry*) and a `⚙` glyph. The boards draw the product's mark, *Build* rather than *Builder*,
a way to jump to a pipeline or run, help and settings.

## What changes

### 1. The bar

From left to right, one row 60 px tall on `--paper` with a `--line` bottom border:

- **The mark and the name, linking home.** The metro-line mark (three stations on a `--done`
  line, drawn as inline SVG in tokens) and *Comeni Labs* at the brand role (17 px, bold).
- **Build · Runs · Registry.** *Builder* becomes *Build*. The current section is shown as on the
  boards: a `--surface` pill with a `--line` border and `--ink` text; the others are `--ink-2`.
  *Registry* still links to `/forge` until the forge (#360) replaces those pages.
- **Jump to a pipeline or run** (section 2), pushed right.
- **Help**, a round `?` button (section 3).
- **Settings**, a round button with a gear icon drawn as inline SVG, opening the existing
  overlay exactly as the `⚙` link does today.

There is no lab chip and no *Learn in Code*: labs are not in the MVP, and Comeni Code does not
exist yet (a link to nothing is refused).

At phone width (below 640 px) the jump box shrinks to a search icon button that opens the same
palette, and the row wraps rather than scrolling sideways.

### 2. Jump to a pipeline or run

**Operator's choice, 2026-10-19: build it small.**

- **Opening it:** a click on the box, or ⌘K (Ctrl+K off macOS), from any page. It opens as a
  dialog over the page with a text field, focused.
- **What it lists:** the saved pipelines (`GET /pipeline/drafts`, the list Home already reads)
  and the 25 most recent runs (Wiener's `GET /api/runs?limit=25`, as Home reads it). Nothing new
  on the server.
- **Filtering:** as you type, a case-insensitive match on a pipeline's name or a run's name or id
  prefix. Pipelines first, then runs, at most eight of each.
- **Each row says what it is:** a pipeline shows its name and step count; a run shows its name
  (or `run <id8>`), its phase in the phase's `-ink` and when it started.
- **Choosing:** ↑/↓ move, Enter or a click opens it (a pipeline at `/build?draft=<id>`, a run at
  `/runs/<id>`, the links Home already uses), Esc closes and returns focus to where it was.
- **When a half is unavailable:** if Wiener does not answer, the palette still lists pipelines
  and says *Runs could not be read*. With nothing typed it shows the most recent of each.
  With no match it says *Nothing matches "…"*.
- **Not in this part:** describing a new analysis from this box. The describe box stays on Home
  (#378).

The palette is a dialog: `role="dialog"`, labelled, focus kept inside while open, the list a
`listbox` with the active option announced.

### 3. Help

**Operator's choice, 2026-10-19: the `?` opens the docs.** No documentation site is published
yet; the wiki is only served by the development stack. **My call:** the button opens the
documentation index in this public repository
(`https://github.com/comeni-project/Comeni-Labs/blob/main/docs/index.md`) in a new tab, from one
constant in the shell, so the address changes in one place when a site is published.

## Not in this part

- No page below the header changes. Home is #378, describe/build #377.
- Search over tools, settings or the registry.

## Testing

- **The bar:** the mark links to `/`; the sections are *Build*, *Runs*, *Registry* with
  `aria-current="page"` on the current one; help opens the docs index in a new tab
  (`target="_blank"`, `rel="noreferrer"`); settings still opens the overlay; no lab name and no
  *Learn in Code* anywhere in the shell.
- **The palette** (recorded responses for the two lists, no live server):
  - ⌘K and Ctrl+K open it from any route, the field is focused, and Esc closes it and restores
    focus;
  - typing filters both halves case-insensitively, by name and by run id prefix;
  - ↓ then Enter navigates to the chosen pipeline's or run's address;
  - a Wiener that answers with an error still lists pipelines and says runs could not be read;
  - no match says so.
- A browser check at 1440 px and 390 px, light and dark, against the boards' header.
