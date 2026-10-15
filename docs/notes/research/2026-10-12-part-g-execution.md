# Part G: completed implementation and execution decisions

Part G is implemented locally on `stage-four-the-consultant-build`, `883675fb` through `ff941e08`,
following the approved [spec](../../superpowers/specs/archive/2026-10-12-part-g-canvas-and-walk-design.md)
and [plan](../../superpowers/plans/archive/2026-10-12-part-g-canvas-and-walk.md), whose execution
record has per-task evidence.

Final verification: `make check` 3,898 passed, with 2 failures that are the Python 3.14
truncated-gzip cases (#303), which pass on 3.12. Types, docs, links, paths, sizes and guards (95)
passed; mendel-api 1,102 passed; Vitest 710 passed with 1 existing skip; `tsc -b` passed. A CDP
browser walk against a throwaway database agreed with the API in every scenario. The
development database was not touched. The baked images were not rebuilt.

The fresh whole-branch review found one Critical defect (a moved registry made sessions 404) and
three Important ones (gap paths sent to the API with Dev mode off, the spec's preview wording,
focus returning to an old trigger). All four were watched RED→GREEN and fixed in `ff941e08`.

## Rulings made during execution

1. Quiet pacing has no pending aligner, so its guard checks the placed graph — cost if wrong: a quiet-mode offer wiring bug shows only in the walk.
2. SQL budgets are per case (together 50, quiet/complete 62), each measured equal with and without the frame — cost: none.
3. A manual frame drops edges to removed steps instead of failing the read — cost: a dangling wire is invisible rather than flagged.
4. No same-type/different-state channel exists in the RNA-seq case; that formatting rests on the build-service suite (the review confirms states come from a channel's first port: deferred).
5. Task 3's preview operation name was added to the OpenAPI guard in Task 4 — cost: none.
6. The `unresolved_settings` guard starts from a goal with HISAT2 pinned, because a swap counts as the aligner's review — cost: none.
7. Gap paths stay in the stored block, filtered at the session view by Dev mode (the first ruling kept them in the view; the review reversed it).
8. Hide-gaps protocol label: *named, no stop* — cost: one label.
9. The surface reads `session.canvas`; fixtures wrap sessions with `framed()` — cost: fixture frames are client-built.
10. The run sheet keeps a lazy `/pipeline/draw` of the saved draft — cost: one request per opening.
11. Keep and edits use the saved draft, not the optimistic graph — cost: an edit mid-accept omits the not-yet-landed step.
12. The pending card shows current progress; history shows each offer's stamp — cost: none observed.
13. A real recorded "0 settled" stays; only a step without metadata shows no count — cost: one footer word.
14. Run is already disabled by phase whenever an offer is pending, so the preview's `!showing` check is defensive and unguarded.
15. The preview selection is derived from its offer and context rather than cleared by an effect.
16. Fixtures read previews through a `readPreview` prop — cost: one optional prop.
17. The walk was seeded through session commands, not a live model — cost: model-phrased paths are unwalked here (Part F walked them).
18. Declined-to-judge items were ruled as follows: the hidden canvas keeps its viewport (same mounted node); a `row_version` bump closes a preview (the context includes it by spec); Escape closes a drawer as well; quietly placed steps count as reviewed.

## Deferred minors

- `step_views` lost its `node.id in by_id` guards; a manual `/pipeline/draw` can `KeyError` on an IR node missing from `Pipeline.steps`.
- The manual frame re-runs `ir_of`, `Pipeline.of` and layout on each poll (CPU, not SQL).
- A Dev-mode wrap receipt stores the fix paths in its transcript text.
- Migration `b9d3e7f5c164`'s `downgrade()` raises.
- The cross-session preview guard uses a session id that does not exist.
- With Dev mode off, a card names only `no_domain` gaps; the Dev mode help implies more.
- A channel's states come from its first port only.
