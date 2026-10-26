# 2026-10-22 — The redesign walked with a real model, and its quick fixes

The board-match pass (#370) had been checked in Chrome from fixtures only. On the operator's
main PC (RX 7600, gemma3:12b on Ollama) the stack was brought up on a fresh database and a build
walked end to end: *gene counts from paired-end RNA-seq of mouse liver*. Findings are issues
#384–#397 under #370. The quick ones are fixed on `redesign-walk-fixes`, stacked on
`redesign-board-match`.

## Where things stand

- **Fixed:** #384 (optional open values; operator delegated the rule), #385 (Run stays locked
  while a value needs you; operator's decision), #386, #387, #388, #389, #390, #397. Each was
  checked in the browser against the live stack.
- **The rule chosen for #384:** an unanswered tier-4 setting is optional when its route leaves
  the tool its own behaviour (`OMITTABLE`: `ext`, `directive`). It stays tier 4 and flagged, is
  asked as optional, and stops nothing. `positional` (MD0224) and `meta` (a module reading
  `meta.<name>` gets `null`) still need the person. Derived from the route, not declared per tool.
- **A regression of #268, fixed:** the redesign's step card chip printed tier 3's served name,
  *Measured*, for a rule over a typed value; #268 had settled that tier 3 is never called
  measured (its premise may be typed, measured or model-read). The chip says tier 3's served
  group, *Check the premise* (#387). Counts follow the evidence (#397, operator: option A):
  `SettingView.evidence` is *measured* only when every premise was measured.
- **Design, for a separate session:** #391 (Describe's questions), #392 (a conversation between
  the engine's asks), #393 (a summary when a build finishes), #394 (the pipeline file page puts
  the file first), #395 (one builder: manual and conversation). #396 belongs to the registry.

## Traps

- **A change to a stored shape needs every writer restarted.** After the shape-2 migration,
  `mendel-worker` (mounted, not reloaded) still wrote shape-1 proposals, and the API refused
  them (`MI0400`). Restart `mendel-worker`, rebuild the baked `ai-worker`, then migrate again.
- **Restarting Vite alone loses the API port:** run it with `API_HOST_PORT=8020` or every call
  returns 502.
- `#384` in frontend source reads as a colour to `tokens.test.ts`; write *issue 384*.
- **A new migration needs `make test-db` again** before `make check`: the test database's
  server default still writes the old shape, and the shape guard refuses the row (`MI0400`).
- Shape 2 of saved previews (`optional`, `evidence`) was amended once before pushing, so the
  dev database was downgraded and upgraded to rewrite its rows.
