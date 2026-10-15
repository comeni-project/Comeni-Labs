# Decisions as rows (14.7.8.3d Part F) — design

**Status: implemented locally and verified (2026-10-12).**
Approved for planning by the operator, 2026-10-11: "you can write the plan".
Behavior decisions and the proposed technical design below are the planning baseline.
Issues: #290, #269, #272, #275, #295 and Part F's items in #268. Parent: #284.

## 1. What the researcher gets

Every fact can be corrected or returned to unknown. A correction changes the
pipeline and the reviews that depend on it. A conflicting sample prompts a real
question in the chat; it never silently replaces an answer. The goal, step cards,
transcript and artifact all read the same active decisions.

A fact's history is available now: previous values, their sources, who selected
them, and what changed. **Undo must be built later.** History in this part is
read-only; it does not offer restore, replay or an Undo button.

## 2. Decisions agreed with the operator (2026-10-11)

| Question | Decision |
|---|---|
| One source of truth | Active decisions are authoritative; the goal is composed from them |
| A measurement disagrees | Ask in the chat; no automatic replacement |
| A correction affects other steps | Cascade through resolution and affected reviews; make this explicit in the diagram |
| A correction makes the build impossible | Accept the factual correction and explain what is missing |
| Return a measurement to unknown | Allowed; retain history, remove its active value from the profile |
| Correct after manual edits | Create a new draft, preserving and linking the edited draft |
| Existing sessions | Operator delegated the migration choice; proposed strategy is in §12 |
| Visible history | Available in this part; explicitly record undo as later work |

Storage mechanics, table names and the migration strategy are implementation
recommendations, not additional claims of operator approval.

## 3. The problems this fixes

Gathering reads `session.facts`; later amendments write `session.goal.profile`.
`project` mirrors the goal onto the draft. The goal also carries partial model
extraction and a question-phrasing cache. A known fact disappears from the step's
offered answers. Sample ingestion keeps any known subject, including an earlier
measurement. `Reviewed` records a node ID and `by`; `kept` checks only node presence.
A changed tool, setting or premise can therefore retain a review of its old form.

Four paths write drafts, with inconsistent revision handling. Ordinary autosave
does not check or advance the revision. A proposal's `by` cannot distinguish a
person's name from a model ID. The transcript labels every tier-3 entry measured.
These are verified in the accompanying research, against `8c86d198`.

## 4. The authoritative records

Decisions belong to the **draft**, with optional links to the session, proposal,
turn and evidence that produced them. Their lifetime must not depend on retaining
the chat. A hand-drawn draft can still derive a goal from its graph, as today;
authored drafts compose their goal from decision rows. Make that distinction
explicit in the draft's ownership mode: authored projection or manual graph.

Use separate typed relations for these families:

| Record | Identity and content |
|---|---|
| Input | Stable input key, type, optional channel name and states; present or withdrawn |
| Wanted output | Output type, required states and stable order |
| Fact | Measurement subject, typed value or explicit unknown, origin and evidence |
| Producer choice | Canonical `Site`, selected contract or explicit released pin |
| Parameter override | Declared parameter name and value, or explicit released override |
| Step review | Step identity, reviewed semantic fingerprint, reviewer and status |

Identity must preserve named channels and multiple inputs of the same type already
supported by `GoalInput`. A fact remains scoped to the whole goal in this part;
do not introduce a per-sample measurement model as an incidental schema change.
Preserve ordering where it affects `Goal` serialization or resolver behavior.

Each decision family retains revisions. The selected current revision is explicit:
use a stable subject row with a pointer to a retained revision. The revision is
immutable and contains the decision value and its attribution. The current pointer
must reference a revision of that same subject and draft, enforced by composite
foreign keys. Subjects have unique keys within a draft. Replacements and removals
create revisions, rather than deleting the old value.

Use typed columns for identity, status and attribution. Bounded structured values
(state lists, typed evidence, a validated scalar value) may use JSON where their
schema requires it. Do not move the current session's entire decision list into a
generic JSON payload on a single new row. Apply Part E's enum CHECK, ownership-key
and migration/model parity conventions to the new relations.

An unselected measurement is retained evidence, not a second active truth. Store
each observation once and reference it from a selection revision; choosing it must
not copy its evidence into independently editable records. Explicit decisions to
keep an existing answer are recorded even though its scalar value did not change.

## 5. Origin, attribution and goal composition

Keep **origin** (person-stated, inspector-measured, model-read, unknown) separate
from **chooser** (person, model, resolver) and their name/model ID. Selecting a
measurement retains its measured origin while recording the person who selected it.
An inspector is evidence-producing software, not a model or a human author.
Store evidence references and piece versions where available. Do not add sample
bytes or new free-text fields to a `Goal` or existing egress payload.

Compose the existing pure `Goal` from selected revisions. Unknown measurements
are absent from its profile. Use the measurement registry's constructors and
validation; preserve evidence filtering at the current door boundary. A model's
suggestions are separate from accepted decisions and become active only through
the existing confirmation rules.

Remove both live goal authorities: `session.goal` and an independently updated
`draft.goal`. Readers of authored drafts use the same composition service.
Keep `Goal` snapshots inside kept artifacts, as fixed records of that build.
Store extraction/read-back presentation separately; question phrasing has a
dedicated cache keyed by subject and the context revision that produced it.
Pacing and whether registry gaps stop the walk are checked nullable columns.

Blueprint and graph remain computed snapshots. Record their source decision
revision and registry digest. Freshness is checked before use; a snapshot never
supplies an answer that disagrees with its source rows. Database IDs, history and
timestamps must not change deterministic artifact bytes for the same `Goal`.

## 6. Disagreement is a question in the protocol

When a newly admitted observation differs from an active known value, retain it
without selecting it and ask, for example:

> You said the reads are 150 bases, but this sample measured 100. Which should we use?

Offer the current answer, the new observation, a different validated answer and
unknown. Label sources accurately, including conflicts between two measurements
or with a model-read value. An equal observation does not replace the current
origin silently. New observations may fill an unknown value under the existing
sample-admission rules; a known value requires an explicit decision to replace.

Only one mutation question is pending at a time. Multiple conflicts from one
sample are retained and asked in deterministic order. Each answer checks the
revision and evidence IDs the question offered. A late result cannot replace an
answer made since its job began, and dismissing one conflict does not erase the
other observations. A resolved or obsolete conflict is not asked again without
new evidence.

The sample section is currently `within_request=True`: it cannot wait for a
person inside that section. Its result must hand off to an ordinary waiting
disagreement node, with an explicit continuation for gathering or building.
No AI call is needed to determine disagreement or offer the engine's question.

## 7. A correction and its cascade

Facts remain available from the current goal and from steps whose declarations,
rules or premises read them, including already supplied facts. Correction is a
structured command, independent of whether the pending card lacks the subject.
Retraction selects an explicit unknown revision. It does not pretend a value
was never supplied and does not invite the model to guess one.

The action validates the correction, selects its revision, composes a fresh goal,
resolves it and compares the old and new semantic pipeline. A changed semantic
step includes a different contract/digest, setting value, relevant input/wiring,
decision reason or premise value/source. Layout and unrelated facts are excluded.
Propagate the affected set through dependent steps. Retain reviews only when
their fingerprint and relevant dependency context remain valid. A review of the
old meaning is superseded even when the node ID remains unchanged.

Affected steps re-enter the walk according to pacing. Tier 4 still stops;
together asks for review; steps eligible for quiet placement receive new resolver
review records rather than inheriting an old person's review. Unaffected reviews
survive. Pinned choices are not silently released; they can be explicitly released
to let the engine choose again. A pin made unreachable by a fact correction is
reported as a conflict the person must address.

Invalidate pending mutation proposals computed from the old decisions and offer
fresh questions. Receipts describe fact/settings changes as well as added,
removed and swapped tools. The transcript keeps original turns, with current
status shown separately: superseded, removed, or still applicable.

## 8. An honest correction can stop the build

A valid factual correction is committed even when the corrected goal cannot be
resolved. Retain the last computed pipeline for comparison, mark it outdated,
and refuse keep/run/preview-as-current until a current build exists. Existing kept
artifacts and submitted runs retain their snapshots.

Return to gathering and explain the missing input or incompatible decision.
If an essential input is unavailable, use the honest stopped path with a drawn
way to correct that answer and resume gathering. Unknown measurements can stay
open and fall to tier 4; missing essential inputs cannot. Expected inability to
build is a domain outcome, not an exception that rolls back a truthful correction.
Unexpected resolver or database errors still roll back the whole action.

A speculative tool swap that cannot be built is refused without changing active
decisions, as today. This distinguishes correcting known facts from asking to
apply an impossible alternative.

## 9. The diagram specifies these paths

Change `mendel_authoring.protocol.PROTOCOL`, its typed commands/events and acting
handlers, then regenerate the authoring diagram. Never hand-edit the generated
picture or add hidden dispatcher transitions. Planned ask-anything stays planned.

The approved behavior must appear as explicit nodes and arrows:

| Entry | Engine work | Person or continuation |
|---|---|---|
| Sample result | Admit evidence; compare to selected answer | Match/new unknown: continue; disagreement: wait for your choice |
| Disagreement answer | Record keeping/replacing/retracting the value | Gathering continues, or a changed build enters the cascade |
| Correct from goal or step | Validate; select revision; compose goal | Resolve the correction |
| Resolved correction | Compare semantic steps; cascade; supersede reviews/proposals | Resume at the first affected step, or finish if nothing needs review |
| Correction cannot build | Mark previous pipeline outdated; explain missing requirement | Gather an answer, or stop honestly with a correction/resume arrow |
| Correct a manually edited draft | Fork a new authored draft and session | Correct and walk in the new draft |

Correction must be reachable from gathering, goal review, the step card, wrap-up
and an honest stopped session. While an async action runs, serialize or reject a
competing mutation with a clear retry outcome; never partially apply it. New
waiting nodes and continuations must satisfy the existing protocol validators.
The implementation plan will name concrete commands, events and node IDs against
the final design, without inventing a second state machine in the API shell.

## 10. One owner for writes and concurrent changes

One draft mutation service owns revision checks and increments for authoring
projection, ordinary autosave and manual edits. Serialize writers on the draft
in a consistent lock order. Every client mutation supplies the version it read;
an old screen receives a conflict and refreshed state, not last-write-wins.

Maintain separate meanings: draft revision identifies the shown graph/provenance;
decision revision identifies the selected goal inputs; session row version guards
workflow movement. One action advances each affected counter once, and receipts
and new proposals refer to the resulting versions. Presentation-only phrasing
updates do not advance the decision or graph revision.

During the authored walk, arbitrary graph saves are refused across every endpoint.
After completion, the first semantic manual graph edit switches ownership to
manual; renaming or layout-only edits do not. Compute provenance through the
appropriate pure projection or manual-restamping function, called by the same
write service. Clients never supply trusted provenance.

Use the existing one-action/one-transaction dispatcher. Commit history, current
pointers, projection freshness, proposal status, transcript and movement together;
enqueue model work only after commit. Async replies carry context versions and
cannot apply obsolete extraction, phrasing, read-back or measurement choices.

## 11. Manual work and visible history

A fact correction on a manually edited authored draft creates a new draft and
session linked by an explicit fork relationship. Carry active goal decisions and
their provenance into the new draft; reference the original history without
reassigning its ownership or inventing new measurement events. Preserve the
original graph, name, transcript, history and kept artifact. The new draft starts
an authored build, states that manual changes have been preserved in the original,
and links back. It does not claim to merge or transfer those graph edits.

Each fact exposes its active value/source and a read-only history: previous
answers, new observations, decisions to retain/replace/retract, chooser and time,
and the associated change receipt where available. Record order with a sequence,
not timestamps alone. An unused observation is labelled as unused, not as a
previous active value. Correcting to an old scalar creates a new decision; it is
not implemented as undo. Do not expose raw model replies or sample contents as a
side effect of browsing history.

Transcript status and tier labels come from actual review and premise records.
Tier 3 means data-profiled; its premise may be asserted, measured or model-read.
Removed steps stay visible as historical steps, not as currently settled work.
Detailed canvas fixes in Part G remain there unless needed for this behavior.

## 12. Existing sessions: migrate what can be recovered

Recommend migrating recoverable state, with a dry-run inventory and database
backup before applying it. No automatic deletion of conversations or drafts.

For confirmed authored sessions, use the confirmed goal as the source of current
inputs, wants, facts and pins: later amendments made it more current than gathering's
fact list. Use compatible fact records to recover evidence. Preserve disagreeing
older records as legacy evidence with unknown activation history. For gathering,
migrate its facts and extracted suggestions separately. Preserve pacing, turns,
proposals, graph and kept state. Do not claim recovered timestamps are original
decision times when only migration time is known.

The session and draft goals should normally agree; compare them and the graph
rather than choosing silently when they differ. Report ambiguous ownership or
conflicting confirmed state in the inventory. Preserve the draft as manual and
retire its session from mutation when faithful recovery is impossible; provide
read-only access and an explicit new-build path. Retirement is a checked status,
not an invented protocol node. Unknown historical actor kinds remain explicitly
unknown in legacy attribution; never infer person/model from a name.

Do not manufacture old reviews from node IDs alone. Carry a legacy review only
when its reviewed meaning can be recovered against the stored blueprint; otherwise
retain the historical record and require fresh review. Record migration provenance
and make recovery deterministic. Exact compatibility/version machinery beyond
this migration belongs to Part H; do not solve it with another delete-all reset.

## 13. Typed boundaries and contained refactors (#275)

Proposal payloads are closed discriminated envelopes per goal, gap, step, pacing
and disagreement kind. Validate the whole envelope on write/read, including
options, amendments, edges and subjects. They remain fixed offers tied to versions;
the server validates answers against offered IDs. Dispatcher arguments are typed
per arrow alongside commands, replacing the shared arbitrary payload dictionary.

Refactor resolver parameter plumbing to take the parameter/declaration and a
resolution context, returning the resolved value and any decision record instead
of mutating an output list. Preserve tiers, reasons, decision order and emitted
bytes. Replace Wiener's repeated task filter/sort/page arguments with a typed
query object, preserving validation, lab scoping, sort and pagination semantics.
No new library, generic event bus or full event-sourcing infrastructure is required.

## 14. Acceptance and validation

- A fact supplied during gathering and corrected during the walk is identical
  across the current goal, relevant cards, profile and kept artifact snapshot.
- A conflicting sample asks and waits. Keeping, choosing the observation, typing
  another value and returning to unknown each preserve correct history and origin.
- Multiple sample conflicts, duplicate answers, delayed jobs and two-tab edits
  cannot produce two selected revisions or silently overwrite a current answer.
- Same node ID with changed settings/premises loses its prior applicable review;
  affected downstream steps cascade, unaffected reviews survive, pacing is honored.
- A valid correction to an impossible goal persists and marks the old projection
  outdated. Keep/run refuse it; the drawn gathering/stopped paths can recover.
- All graph writes check revisions, and arbitrary saves during the walk are refused.
  Renames/layout do not incorrectly trigger a manual-ownership fork.
- A correction after manual edits produces a linked new draft and preserves the
  original work. History is available on both sides without falsifying attribution.
- Migration fixtures cover gathering, confirmed, amended, manually edited,
  ambiguous and obsolete sessions; kept artifact bytes remain unchanged.
- New Postgres ownership/uniqueness/CHECK constraints reject invalid rows, and
  `alembic check` agrees with the models. Record failing guards in the ledger.
- Generated protocol documentation matches `PROTOCOL`; its binding/consistency
  tests exercise disagreement, correction, cascading and honest recovery paths.
- Pure resolver goldens remain byte-identical; Wiener query behavior is unchanged.
  Frontend tests and a real browser walk verify corrections, history and transcript
  status. Use `make verify` for the resolver change, with database checks enabled.

Track the existing CI failures in #296 separately so they cannot be mistaken for
regressions or used to claim this part's checks passed. Before closing this part,
record **undo as a deferred task in the task tree**, compact the journal and update
the current-state notes. Read-only history is complete here; undo remains unbuilt.

## Research basis

[Local findings and alternatives](../../../notes/research/2026-10-11-decisions-as-rows.md).
The relational-history recommendation uses the trade-offs in
[Fowler's temporal patterns](https://martinfowler.com/eaaDev/timeNarrative.html) and
[Microsoft's event sourcing guidance](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing).
Attribution is informed by [W3C PROV](https://www.w3.org/TR/prov-dm/).
Concurrency and typed envelopes follow
[Postgres locking](https://www.postgresql.org/docs/17/explicit-locking.html),
[SQLAlchemy versioning](https://docs.sqlalchemy.org/en/20/orm/versioning.html) and
[Pydantic discriminated unions](https://pydantic.dev/docs/validation/latest/concepts/unions/).
