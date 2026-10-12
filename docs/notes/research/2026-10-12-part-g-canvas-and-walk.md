# Part G: make the canvas and walk agree

Research and approved brainstorming choices. Inspected on 2026-10-12 after Part F,
local baseline `bed410fa`. The [written spec](../../superpowers/specs/2026-10-12-part-g-canvas-and-walk-design.md)
is proposed for operator review; no implementation plan or product changes yet.

## What the work should achieve

The canvas, proposed step, preview, progress and wrap-up should describe the same
current analysis. Keep Part F's retained decisions, truthful corrections and review
cascades. Follow the operator's research → brainstorm → spec → plan → implementation
workflow. Resolve product choices before writing the spec.

## Reported defects and current evidence

Scope: [Part G](https://github.com/comeni-project/Comeni-Labs/issues/291),
[preview](https://github.com/comeni-project/Comeni-Labs/issues/265),
[false inputs](https://github.com/comeni-project/Comeni-Labs/issues/266), assigned items
of [walk checklist](https://github.com/comeni-project/Comeni-Labs/issues/268), and
[duplicate node](https://github.com/comeni-project/Comeni-Labs/issues/294).

These are code findings; the original browser observations are in those issues.
No fresh browser reproduction has been performed during this research.

| Finding | Current evidence | Candidate remedy |
|---|---|---|
| Alternative preview changes only a label | `LivingSurface.tsx` passes an option label as `instead`; `LivingCanvas` retains the original ports, nodes and wires | Server-owned complete alternative view, read-only and tied to its offer |
| Proposed step has false INPUT boxes | `LivingBuilder.useDrawn` adds the node but omits `pending.edges` from its draw request | One coherent proposed graph including its offered wires |
| Duplicate step | `LivingCanvas` concatenates graph ids and ghost id without deduplication | Unique node identity and explicit treatment of a proposal about an existing node |
| Counter exceeds total | `DecisionLog` counts all historical step decisions; session total counts current blueprint order | Current blueprint position/progress separate from historical decision chronology |
| Newly selected alternative has no ports | Canvas renders absent `steps[id]` as empty ports and defaults its footer to zero; graph and draw result arrive independently | Render complete node data with graph, or explicit loading state; do not invent zero |
| Settled nodes acquire red stripe | `/pipeline/draw` → `services.build.drawn` materialises without retained provenance; fallback stamps every module tier 4 | Authored read view preserving stored provenance; manual drawing retains truthful tier-4 fallback |
| Registry gap appears in run requirements | `wrap_up` lists every null setting in `unset`; building `wrap` joins every unset setting to required inputs | Separate registry deficiencies from actual run inputs and deliberately deferred settings |

Part F exposes `review_applicability` and stores projected provenance. Use those
authorities instead of deriving review state from colour or transcript length.
Pending proposal wires already exist after Part A; this is not missing resolver wiring.

## Existing decisions and conflicting descriptions

- `services.blueprint`: resolve the full pipeline, reveal steps incrementally. The
  current session read exposes a total, not the private complete blueprint.
- `alternatives_of` already resolves complete alternatives to obtain their diffs,
  then discards the resolved blueprint. Step offers store amendments and fixed
  options. Any preview must respect those identities and their immutable context.
- `.design/living-pipeline/README.md`, intrinsic versus asserted: avoid overlaying
  full rerouted graphs; substitute one node and list other consequences. Issue 265
  instead explicitly asks for the whole resulting pipeline. Operator decision needed.
- Colour represents tier; author represents stroke. Invariant 6 keeps tier 4 flagged
  even after approval. Fixing lost provenance does not justify painting every
  accepted choice green. Review applicability is a separate state.
- Dev mode setting help and gap type docs promise to show gaps only when enabled.
  Actual pacing policy controls stopping, while `StepProposalCard` displays its
  gaps unconditionally. This discrepancy is another unchecked item in issue 268,
  not explicitly assigned in Part G's initial checklist.
- `needs.py` explicitly calls a no-domain setting a registry gap left to the run.
  Thus the wrap-up correction needs a deliberate classification decision, not
  merely deleting every null setting from the receipt.

## Approaches considered

1. **Recommended: repair the shared authored view and its consumers.** Server supplies
   truthful node data, progress and read-only alternative view; React renders it.
   Pending wires and unique nodes are local repairs. Moderate scope, no intended
   decision-storage redesign. Keep server-side deterministic layout.
2. **Patch each display independently.** Fewer initial interface changes, but would
   require client reconstruction of alternatives and provenance, create duplicate
   logic and risk repeating the same contradictions. Not recommended.
3. **Rebuild the whole canvas/session architecture.** Broadest flexibility, much
   larger scope than these defects justify. Not recommended for Part G.

The implementation boundary still needs investigation when writing the spec:
whether preview data is retained when the immutable offer is created, or fetched
on demand under an unchanged registry/draft/session context. On-demand work must
refuse stale context rather than silently preview different options. Neither
approach may mutate the goal, draft, review history or runtime registry.

## General solution research

[React: Choosing the State Structure](https://react.dev/learn/choosing-the-state-structure)
recommends avoiding duplicate and redundant state and deriving values from their
authority. Applied here: retain a selected option id, not a second hand-built
pipeline; progress derives from current plan, not lifetime transcript events.

[Nielsen Norman Group: Visibility of System Status](https://www.nngroup.com/articles/visibility-system-status/)
explains why accurate, timely state feedback supports predictable interaction.
Applied here: identify preview/loading/re-review explicitly, and do not present
missing drawing metadata as zero settled or a registry defect as a file request.

These are design principles, not evidence that the proposed implementation works.

## Operator decisions recorded during brainstorming

- Complete alternative preview approved: temporarily replace the canvas with the
  actual resulting pipeline, explicitly labelled **Preview — not applied**, then
  restore the current build on exit. Revealing future alternative steps is approved.
- Current-plan progress approved: active cards use the current pipeline position;
  corrections say **Review step 3 of 5 again**, not another extra step. Historical
  entries retain original context and removed/superseded labels.
- Operator constraint: **do not bloat database calls**. Progress must ride the
  existing session read; no additional polling or per-node database queries. Reuse
  alternatives already resolved when a card is offered rather than resolving them
  again on every hover. Choose the precise storage/read boundary in the spec,
  including avoiding large preview payloads on every routine session poll.

- Registry-gap reporting approved: **To run, provide…** lists actual files and
  intentionally deferred settings. Registry deficiencies appear separately;
  anything that prevents running stays visible regardless of Dev mode. This is
  a truthful presentation requirement, not permission to introduce new run gates
  for every registry warning.
- Dev mode approved: add technical details, repository paths and extra review
  stops. Fix its misleading help text and visibility discrepancy within Part G.

## Agreed approach and next stage

Repair the shared authored view and its consumers; preserve stored provenance,
review applicability and fixed proposal context. Include complete alternative
preview, proposed wiring, unique nodes, truthful node loading, current-plan progress
and separate registry-gap reporting. Preserve the existing tier-colour invariant:
an approved tier-4 choice remains flagged; a lost-provenance tier-4 fallback must
not overwrite a real recorded tier. No decision-storage redesign is intended.

No further operator questions are currently needed. The written spec is now
proposed for review, followed by a separately reviewed implementation plan.
Its self-review selected a nullable, deferred snapshot column on the existing
proposal row: storing complete alternatives inside the routinely loaded proposal
JSON would still bloat database reads despite excluding them from HTTP responses.
One additive migration, no new tables or historical backfill. Product code has
not changed during brainstorming/specification.

No need to reopen automatic measurement replacement, history or undo. Undo remains
deferred under issue 302. Differential-expression extraction and its model variance
are separate unchecked findings in issue 268, outside the assigned canvas work.

## Validation to design, not execute yet

Reproduce STAR → HISAT2 preview and acceptance, read-length correction, upstream
dependency re-review, and a re-offered existing node. Cover both pacing modes,
mouse/keyboard/touch preview, returning from preview, failed and stale preview,
reload, and no fabricated INPUT boxes. Check API provenance against the visible
stripe and explicit review state. Draw screenshots against updated artboards at
wide and narrow widths. Focused regression guards should fail for each real defect
before fixes. Broaden verification according to the code actually touched.
