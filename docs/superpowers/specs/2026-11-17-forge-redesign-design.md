# The Forge, to the board

**Status:** approved by the operator on 2026-11-17 ("Everything"; "you can delete any old code, plan
out the new boards, and implement them"). Issue #511.

## Intent

The Forge is where a lab turns an upstream tool into a registry entry the builder can use. The
redesign board (artifact `CUvvKjirdRqZQG572q4eP6`, artboards "5 · Forge" and "6 · Forging") replaces
the piece-by-piece forging page with two places:

- **Forge home** (`/forge`): what tool do you need (search nf-core), what needs you, your forgings.
- **A forging** (`/forge/:id`): three pages — **Tool** (see and shape every part; the AI's choices
  listed for review), **Tests** (prove it runs as declared), **Publish** (pull request → merge →
  release, every blocker with its fix).

A model's contribution stays visible: every AI-proposed item is marked AI and listed under
**Review** until a person says *Looks right* or changes it.

## Goals

- Both artboards built to the board, with the app's tokens and rail grammar.
- Everything shown is derived from the adaptation, the catalogue and the registry. Nothing invented.
- Old forging pages and components the new pages do not use are deleted (no users before v0.1.0).

## Non-goals

- **No change to the forging protocol.** Pieces are still drafted in order and a piece is drafted
  only when the ones before it are settled (`next_piece`). The board's "drafted everything at once"
  is approximated by a *Draft* action on the next piece; the Review list holds what waits.
- **"Your registry can't yet"** (tools asked for in builds) is not built: no build records an
  unreachable want. Filed as an issue; the strip is left out until it has data.
- Board controls with no backing API are left out rather than faked: *Run this test*, *Expect a
  file / value / snapshot*, *Check again / See replay* on rules, *Attach a file*.

## Approaches

1. **Re-host the old page's pieces in the new frame** — cheapest, but the board's Tool page is a
   different model (parts on a canvas, an inspector), so it would not match.
2. **New pages over the existing API, reusing hooks and the command protocol** *(chosen)* — the
   pages are new and match the board; `useAdaptation`, `useForgeActions`, the commands
   (`approve`, `write`, `remove`…), the chat and the tests/publish endpoints stay.
3. **New pages plus a protocol change to draft all pieces at once** — closest to the board's story,
   but a rule/protocol change that needs its own decision. Deferred.

## Design decisions

- **Routes:** `/forge` (home), `/forge/:id` (Tool), `/forge/:id/tests`, `/forge/:id/publish`.
  `/registry/forging*` is deleted; links elsewhere point at the new routes.
- **Rail:** Forge's slot is a "Forging · Open a forging" picker; on home, a *Forgings* list; inside
  a forging, sub-pages Tool / Tests / Publish with status lines, then *Review*: the AI items waiting.
- **Tool canvas:** the process box (name, version, grain), inputs left and outputs right from the
  approved/proposed `contract:input:*` / `contract:output:*` items (removed ones hidden), optional
  inputs dashed, conditional outputs labelled from `produced_when`; neighbours "from your registry"
  from the catalogue's fits. Part cards below: Parameters, Rules, Measurers, Vocabulary.
- **Inspector:** curated fields for ports (name, data type from the vocabulary, format, needed /
  always made) and parameters (name, kind from its domain, default, help); other kinds show their
  value read-only with *Ask AI*. Saving is a `write` command; an AI item waiting shows the AI's
  reason with *Looks right* (`approve`) and *Change* (opens the fields).
- **Tests:** cases from `tests:test:*` items with the latest run's state; expectations from the
  item's `expect`; coverage of outputs, optional inputs and parameter choices derived from the cases.
- **Publish:** the track derived from phase, tests and pull request; the files card derived from
  which pieces have items.
- **Home "Needs you":** waiting AI choices, failed tests, merged-awaiting-release, and tools newer
  upstream (catalogue state counts). `AdaptationSummary` gains `tests_failed` and `pull_request`
  state so the list needs no per-forging fetch.

## Left to the builder

Exact spacing and copy follow the board; derived wording in the app's voice (no assistant voice).
