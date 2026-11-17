# Registry · Tools to the board — plan

**Board:** "7 · Registry" on claude.ai/artifact/CUvvKjirdRqZQG572q4eP6 (source:
`docs/superpowers/specs/2026-11-15-frontend-redesign-board/Registry.dc.html`); written design in
#511, comment "Registry, revised (2026-11-15)". Part of plan 2 (#513), pulled forward for the
demo. Each step: build to the board, check it beside the board in the browser, tests pass.

## What differs today (board ← current)

| Area | Board | Current |
|---|---|---|
| Page top | search bar first, no title | an h1 "Tools" and a registry-version line |
| Rail | Registry → Tools 2,150 · Vocabulary 41 · Releases "1 waiting" (the open one filled); **Topic** bars only | Tools · Releases · Learned rules, no counts; "Filter" with Topic, No topic and Tool suite |
| Status | pill chips with a coloured dot: All · In your registry · Newer version upstream · Waiting for a release · Not in your registry | a segmented control with icons and other words; a Format flow / Your registry / Hide switch |
| Format flow | title + one-line explanation; Takes and Makes columns, each row tinted by family; no search boxes | search boxes on each side; picture switch |
| List | card "Best matches · N shown" + sort "Fits your registry"; rows with a coloured dot, path, version, description, coloured chips; selected row has a left bar; scrolls inside the card | longer card, icon per row, footer |
| Detail | name + state pill; does; nf-core page + one action named by state (Update to x · Use in a build · Forge this · Open forging) | "Open the tool"/"Forge" |
| | takes → tool → makes diagram on a tinted panel, tool box with short name and "here x" | flat row |
| | three tiles: In your registry · Upstream · Topic | two, no topic |
| | Fits: rows with the shared format on the right ("trimgalore · fastq") | paths only |
| | Rules: "No rule needed: nothing else in your registry does this job…" or a decision table per rule (When · Choose · Because + citation), this tool's row highlighted, others greyed; not in registry: "Forging drafts its rules." | table, highlight, no citation, no empty-state words |
| | an amber note for formats nf-core mentions but does not declare | a grey line |

## Steps

- [x] 1. API: `ModuleRow.topics`; `Fits` lists each fit with the format it shares (`path`, `via`).
  Tests first (catalogue service). Regenerate the client.
- [x] 2. Rail: Registry's pages Tools · Vocabulary · Releases with counts, the open one filled;
  Topic bars only. Learned rules stays reachable from Releases (rules are per tool on the board).
  Vocabulary: a plain list of the registry's types, measurements and what measures them — the
  board names the page but has not designed it (#511 open item).
- [x] 3. Page: no title; search; status chips as the board; no picture switch.
- [x] 4. Format flow as the board: explanation line, Takes/Makes captions, family tints, no
  search boxes.
- [x] 5. List card as the board.
- [x] 6. Detail card as the board: header and state-named action, diagram panel, three tiles,
  fits with formats, rules (empty states, citation, greyed alternatives), the amber note.
- [x] 7. Browser check beside the board; tests, tsc, lint; commit.

Deviation, decided: the board's small-capital labels (TAKES, IN YOUR REGISTRY) are drawn in
sentence case, since the token test allows capitals only in the rail's group captions.

## Deviations

- Forging left Registry's rail (it is Forge's); Learned rules is reached from Releases.
- Vocabulary and Releases are not on the board; drawn in the Tools page's grammar (operator asked for
  them built; the Vocabulary design is acknowledged as weak, to revisit).
- The "Your registry" diagram and its graph layout are deleted: not on the board.
