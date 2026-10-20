# 2026-10-20 — Redesign parts 3 to 7: describe, build, the file, Home, runs, settings

Parts 3–7 of the platform redesign (#370), each with its spec and plan in
`docs/superpowers/` (the plans' *Deviations* sections are the long form), on stacked local
branches: `redesign-describe-build` (#377) → `redesign-pipeline-file` (#379) → `redesign-home`
(#378) → `redesign-runs` (#380) → `redesign-settings` (#381), all on `forge-0-remove-old`.

## Where things stand

- **Not pushed and not merged, by the operator's choice:** the redesign lands on `main` as one
  pull request once it is done, not part by part. The forge (#360) comes next; it brings the
  registry release setting that #381 left to it.
- Describe is a page; build is the canvas beside *Step* (the plan line, the card waiting, changes
  from the chat) and *Assistant* (speech only). The pipeline file is a page of values with their
  reasons beside the file. Home leads with describing, then cards drawn only when they have
  something. The runs board is by pipeline under outcome tabs; a run opens on its failure.
- **Removed:** the runs board's five summary tiles and per-day chart; Home's `/attention` read
  (Needs you reads the drafts' open values); the artifact drawer (`Drawer.tsx`); the rail
  (`DecisionLog.tsx`).
- GitHub issues #373–#376 are duplicates of #377–#380 and were not closed: the `gh` write was
  refused by the permission check in this session.

## Traps

- **Do not `make dev` on these branches against a development database you want to keep:**
  part 0's migration drops the old forge tables. The browser checks here used Vite with the API
  answered from fixtures by a Chrome DevTools script instead.
- `.living` and `.tbl` set `display`/`min-width` in `main.css` and beat Tailwind utilities of the
  same specificity (`hidden`, `min-w-[…]`); use an inline style where one must win.
- `tokens.test.ts` reads `#` followed by hex digits anywhere in source, test titles included, as
  a colour.
