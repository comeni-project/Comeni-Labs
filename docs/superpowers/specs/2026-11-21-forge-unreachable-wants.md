# Forge home: what builds asked for that the registry cannot make

Issue: #534 (part of #511; tracked in #600). Operator authorised proceeding without a separate
approval round (2026-11-20). Board: `docs/superpowers/specs/2026-11-15-frontend-redesign-board/ForgeHome.dc.html`,
the *Your registry can't yet* strip under the tool search.

## The gap

A build learns a want is unreachable (`services/gaps.py`, `Unreachable(type_id)`: no contract
produces it) in the agent's `what_is_needed` and in `explain`, and says so, but records nothing.
The Forge home has nothing to count, so the strip was left out.

## What changes

1. **No new record.** Each analysis's wants are already current decision rows
   (`pipeline_want` / `pipeline_want_revision`). One query reads every present want.
2. **Derive, don't decide**: `GET /api/forge/unreachable` counts analyses per type and returns only
   types **no contract in the current registry produces**, so a want leaves the strip the moment a
   tool for it lands. No status column, nothing to clear. Sorted by count, then type id.
   Each row: `type_id`, its vocabulary name, `builds` (how many analyses asked).
3. **Strip** (board): under the search, `Your registry can't yet` and one chip per type, its name
   and *asked in N build(s)*; clicking a chip searches the catalogue for that type's name. Hidden
   when there is nothing to show (the board's starters with no asks are examples, not data).

## Out of scope

- The board's static starters that nobody asked for (they were illustrations).
- Suggesting which nf-core module would make the type (the search does that).

## Verification

- API: an unreachable want is counted once per analysis; a type the registry produces is not
  listed; a want taken back is not counted.
- Frontend: vitest for the strip (shown, hidden, chip searches); a browser check of Forge home at
  desktop width against the board.

## Deviation (2026-11-21)

The first draft of this spec added an `unreachable_want` table written where `gaps()` returns
`Unreachable`. Reading the decision store showed the wants are already rows, so the list is derived
with one query and no migration, table or write path (the operator's *derive, don't decide*).

Browser check (headless Chrome, 1440×900, dark): the strip sits under the search as on the board,
one chip *Make assembly sequences (FASTA) · asked in 1 build*, from a temporary analysis created
and then deleted for the check (after the delete the endpoint returned no wants).
