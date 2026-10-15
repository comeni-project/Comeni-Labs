# Canvas and walk agreement (14.7.8.3d Part G) — design

**Status: approved for planning (2026-10-12).**
Operator: “right go ahead and write the implementatio nplan”.
Implementation still awaits review of the
[written plan](../../plans/archive/2026-10-12-part-g-canvas-and-walk.md).

Scope: [Part G](https://github.com/comeni-project/Comeni-Labs/issues/291),
[265](https://github.com/comeni-project/Comeni-Labs/issues/265),
[266](https://github.com/comeni-project/Comeni-Labs/issues/266),
[294](https://github.com/comeni-project/Comeni-Labs/issues/294), and the assigned
canvas/walk findings plus Dev mode wording in
[268](https://github.com/comeni-project/Comeni-Labs/issues/268).
Evidence: [research](../../../notes/research/2026-10-12-part-g-canvas-and-walk.md).
Code baseline: `bed410fa`, after Part F.

## 1. What the researcher gets

The canvas and conversation describe the same current analysis. A proposed step
has real ports and wires; an input box means an actual external input. Each step
appears once. Swapping tools or correcting answers updates progress without
counting old proposals as extra steps.

Preview shows the complete pipeline an alternative would produce, including its
dependencies, ports and wires. It says **Preview — not applied**. Closing it
restores the current build. A registry deficiency is explained separately from
the files and settings the researcher must provide to run the analysis.

## 2. Choices agreed with the operator

| Choice | Agreed behavior |
|---|---|
| Alternative preview | Temporarily replace the canvas with the complete alternative; future steps may be revealed |
| Current progress | Active cards use current-plan positions; corrections say **Review step 3 of 5 again** |
| History | Preserve historical context and removed/superseded labels |
| Database calls | No extra progress polling or per-node queries; reuse alternatives already computed |
| Run requirements | List actual inputs and intentionally deferred settings separately from registry deficiencies |
| Dev mode | Add technical details, repository paths and extra review stops; fix its misleading help text here |

The implementation choices below are proposed mechanisms for these behaviors.
Part F's decision authority, corrections, review cascades and read-only history
remain the foundation. Undo remains deferred in issue 302.

## 3. One authored canvas view

Extend the existing session response with a typed canvas frame: visible graph,
step metadata, external channels, placement and the context identifying that
frame. Context includes draft revision, decision revision, session version,
registry digest and pending proposal id, where present.

Construct it from the session, draft, stored blueprint, projected provenance and
pending proposal already read by `services.session.read`. Derive progress in that
same read. Do not open another transaction or query each step's decisions.
Build the frame in memory without calling the resolver, compiler gates or model.
Use server-side layout and the existing `StepView`/`ChannelView` conventions.

For an authored projection, the frame contains retained projected steps and the
step currently offered. Merge the pending step's offered edges whose endpoints
are visible. Deduplicate nodes and edges by their full identities. An offer about
an existing node changes its review presentation; it does not create a second
node or silently replace the stored contract.

Use the blueprint's recorded step/setting reasons and tiers. External channels
are calculated for the visible graph with its offered wiring, preserving channel
grouping, states, scope and measured count. A genuinely external input remains
visible; an input already fed by a visible upstream step is never a new INPUT box.
Do not pretend an upstream step is reviewed merely to supply an edge.

For manually owned graphs, materialise the stored graph with its stored provenance.
Recorded decisions preserve their tiers; genuinely unrecorded manual choices keep
the existing tier-4 fallback. Do not accept client-supplied provenance as authority.

The live builder consumes this frame instead of separately posting its graph to
the manual `/pipeline/draw` endpoint. The manual builder retains that endpoint.
Keep frame construction in a focused view adapter; the canvas renders its answer.

## 4. Coherent loading and review presentation

Render a node's identity, ports, settings, channels and wires from the same frame.
Never combine a new graph with metadata from an older revision. Initial loading
and failed reads have explicit states; missing metadata is not **0 settled** and
does not silently imply tier 1.

While a mutation is in flight, preserve the last complete frame with a working
indicator. Do not invent an alternative's ports or optimistically insert a node
without its metadata. On success replace the frame with the returned/refetched
authoritative session. On refusal restore the current frame and show the reason.
Do not increase polling frequency or add a second polling loop.

Tier colour and review status are separate. Preserve the existing tier-colour
and actor-stroke grammar: tier 4 remains flagged even when a person accepts it.
Use Part F's review applicability for **Needs review again**; a completed review
does not lower its recorded tier. Re-reviewed steps use **Reviewed** rather than
a false unresolved label. Unknown attribution remains unknown.

When factual corrections make the projection stale, retain its truthful last
frame, visibly label that it predates the current answers, and keep Part F's run
disable/recovery behavior. No preview or loading state makes it current again.

## 5. Alternative preview without repeated resolution

`alternatives_of` already resolves each candidate to compute its difference.
Retain that result long enough to produce a typed complete preview snapshot from
the same resolved alternative. Store snapshots by option id in one nullable
`preview_views` JSON column on the existing proposal row, written with the offer.
They are immutable derived views of
that offer, not another editable goal or decision authority.

Validate the map through a closed typed snapshot model at write/read boundaries.
Each snapshot contains its complete graph, step metadata, channels, layout and
offer context; it must agree with the offer's option id, contract and registry.
Refused options have no usable preview. Null means no saved previews for older
offers. The small step envelope records available preview option ids with an
empty default. Snapshots never enter public pending/history envelopes.

Defer the large column in ordinary ORM reads, including session/history reads;
load it explicitly only in the preview endpoint. Omitting it from HTTP JSON alone
is insufficient. This avoids repeatedly loading every alternative from the
database on routine polls, without creating separate preview rows or tables.

Add one read-only preview endpoint under the session/proposal/option path. A
request reads the named proposal and current context in a single transaction,
verifies session ownership and that the offer is still pending and current,
then returns only that saved snapshot. Read the required rows together; do not
query per node. Use existing stale/registry-moved refusal conventions.

Keep the saved offer context immutable. The response wrapper also identifies
the current context checked by the read. Offer creation itself can advance the
session version after recording the offer, so check the caller's expected session
version against the current session, rather than requiring its equality with the
snapshot's historical version. Draft/decision revision, registry and pending
proposal identity must still match the saved offer.

The client caches by session, proposal, option and complete context. Fetch once
on first activation; repeated hover/focus uses the cached answer. Deduplicate
concurrent identical requests; a failed request is retried only deliberately.
No database writes, re-resolution, model calls or gates occur on preview reads.
Acceptance continues through the existing revision-checked command path.

For older pending offers without snapshots, say **Preview unavailable for this
older offer**. Continue remains usable. Do not silently re-resolve, rewrite the
historical offer or require a bulk migration just to backfill previews.

## 6. Preview interaction

Show the complete alternative alone, with actual node identities, contracts,
ports, channels and edges. Do not overlay it on the existing pipeline. Preserve
the card's adds/removes/updates explanation. Every preview node is proposed;
none claims to be reviewed or committed. Keep its real resolution tier visible.

Hover and keyboard focus provide temporary preview; the explicit Preview button
supports touch and a persistent preview. Pointer exit or focus leaving a temporary
preview restores the build. An explicit **Close preview**, Escape, or toggling
the Preview button closes a persistent preview. Keep keyboard focus predictable.

Display **Loading preview…** while fetching, without relabelling the current
pipeline as the alternative. Failure keeps the build visible with an inline error
and deliberate Retry. Refused alternatives explain why and cannot be applied.

A late response for a different option/context cannot replace the current view.
Close preview when its proposal is answered, withdrawn or superseded, when the
session changes, or when its context becomes stale. Reload opens the current build.
Retain the build's viewport, dragged positions and selected node when returning;
preview layout/selection is temporary and cannot modify stored or dragged positions.
Keep, Run and canvas editing cannot act on the preview graph. **Change it** on the
original card remains the explicit acceptance action, with normal version checks.

This supersedes the older artboard's local substitution/individual-consequence
preview. Update its generator, artboard and design explanation together. Preserve
the established canvas geometry and layout direction.

## 7. Progress and historical context

Derive active position from the current blueprint's order and pending node; derive
the total from that same blueprint. Derive reviewed progress from applicable
reviews, not graph-node count or the number of historical proposals. Carry these
small values in the existing session response without exposing future step ids.

The header says **3 of 5 steps reviewed**. The active card says **Step 4 of 5**.
If an earlier review was invalidated, say **Review step 3 of 5 again**. A new
dependency introduced by a swap uses its position in the new plan. Manual graphs
do not claim an authored reviewed/total count that no longer applies.

Record the offer's original position, total and whether it is a re-review with
new offers. History reads those fixed values; it never renumbers old entries
against today's plan. Removed/superseded entries keep Part F's labels. Older
entries without an original position use the step name and status, without an
invented ordinal or denominator. No correction can produce **Step 6 of 5**.

## 8. Run inputs, deferred settings and registry deficiencies

Make wrap-up classification explicit and typed: external input channels, unset
settings deliberately supported at run time, and registry deficiencies. Preserve
the distinction for API consumers as well as receipt text.

Use the existing decision records and `gaps.no_domain` classification. A null
setting whose candidates are only `[None]` is a missing registry domain, not an
ordinary input the researcher forgot. It must not appear under **To run, provide…**.
Do not simply remove all null settings; legitimate deferred run settings remain.

Use **Registry information is incomplete** for deficiencies. Report their actual
consequences using existing build/run diagnostics and materialisation rules.
Do not claim that every registry gap prevents running, and do not add new run
gates in this part. A deficiency that already prevents running stays visible with
Dev mode off, alongside the established disabled action and recovery explanation.

Dev mode adds gap kind/subject, repository fix paths and extra review stops.
Without Dev mode omit repository paths and non-actionable developer detail; keep
user-relevant warnings and choices visible. Explain an unresolved required setting
in plain language even when its technical missing-domain detail is hidden.

Retain the existing pacing precedence: a required fact/choice stops independently
of Dev mode; then developer gap stops; then every step under **together**. Update
the setting help, type comments and protocol diagram/text to describe that actual
behavior. Do not create a second gap-visibility setting or new pause mechanism.

## 9. Boundaries and compatibility

No new decision tables, bulk data migration, undo, differential-expression goal
extraction fixes, model-variance work, registry lifecycle redesign or readiness
work from Part H. Add only the nullable preview column with an additive Alembic
migration; leave existing rows null with no backfill. Proposal JSON additions
have explicit defaults for existing rows; the public client is regenerated,
never edited by hand.

Keep alternative snapshots off history and normal polling responses. The only
new read request is the first activation of an uncached alternative preview.
Ordinary session reads add no database queries for progress/canvas derivation and
replace the living canvas's separate draw request. No N+1 queries by nodes,
alternatives or history entries. Derive from the rows already loaded.

Do not grow database work with hover events. A snapshot map is stored once per
offer in its existing write; there are no writes on GET or per-alternative inserts.
Ensure routine SQL omits the snapshot column and serializers never access it;
implicit lazy loads would break the query constraint.

## 10. Acceptance evidence

Each regression guard must be observed failing against its specific defect before
the fix. Verify all of the following through focused pure/API/frontend tests and
a browser walk with recorded evidence, without live model calls:

- STAR → HISAT2 preview shows HISAT2_BUILD/HISAT2_ALIGN and their actual wiring;
  STAR-only nodes disappear. Closing, failure and stale responses preserve the build.
- Both pacing modes draw offered upstream edges without false INPUT boxes; true
  external inputs, grouped channels and collection scope still render correctly.
- Re-offering an existing node draws it once, with no duplicate-key warning.
- Swap, correction and repeated review keep position/total consistent; historical
  positions remain stable and legacy entries do not invent historical context.
- Newly accepted alternatives never show empty ports or fabricated **0 settled**;
  loading and stale-projection states remain explicit across reload.
- Canvas tiers match recorded provenance; tier 4 remains flagged after acceptance;
  invalidated reviews are distinguished from resolution tier.
- Registry-domain gaps are separate from required files/deferred settings; Dev
  mode changes details and gap stops without concealing an existing run blocker.
- Query/request counts prove no progress/canvas N+1 reads, no extra polling or
  draw request, one preview read per cached context, and no preview writes or
  additional resolver/model calls. Routine/history SQL and HTTP payloads omit
  snapshots; additive migration/model parity and older null rows remain valid.
- Preview works with mouse, keyboard and touch; late responses cannot overwrite
  a newer selection. Preview cannot be edited, kept or run as the current draft.

Update/render the affected artboards before changing the frontend, compare wide
and narrow screenshots, and inspect the browser console. Run frontend tests and
TypeScript, affected Python tests, API generation and documentation gates. Follow
the repository's broader verification requirements for the files actually touched.
Record outcomes and any deviations in the implementation plan when executed.
