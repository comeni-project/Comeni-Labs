# Decisions as rows — research and brainstorm

Research for 14.7.8.3d Part F (#290), against `8c86d198`.
This is a working discussion, not an approved spec or implementation plan.
The operator has agreed to one source of truth; the recommendations below remain proposals.

## Problems verified in the code

- `models.py`: session `facts`, `goal`, `reviewed` and `policy` are JSON.
  The draft has a second `goal`, mirrored in `building/amending.project`.
- `gathering.compose_goal`: copies gathering facts into a `Goal` profile.
  `building/amending.amend` subsequently updates the goal but not those facts.
- `gathering.store_phrasing` and `phrasing_failed`: cache question wording in
  `session.goal`, which also holds partial extraction and the confirmed goal.
- `building/cards.step_payload`: offers only `planned.need.facts`; a known
  fact is no longer an available answer on the step's card.
- `samples._record_found`: retains any existing known subject, not just a
  person's assertion. A subsequent conflicting measurement is reported but
  not recorded as an alternative in the session's fact collection.
- `mendel_authoring.draft.kept`: preserves reviews by node ID alone. It does
  not compare contracts, settings, wiring or supporting premises.
- `mendel_authoring.diff.diff_of`: reports added, removed and changed tools,
  but a settings-only change can currently be described as changing nothing.
- `services/drafts.update`: writes graph and provenance without checking or
  increasing the revision. Other paths increment it themselves (#272).
- `PipelineAuthoringProposal.by`: holds a name or model ID, with no actor kind
  (#295). `Reviewed` similarly has only a node ID and a free-text `by`.
- `frontend/.../DecisionLog.tsx`: labels every tier-3 collapsed entry
  "measured", although a tier-3 premise can also be asserted or model-read.
- `GoalInput` already supports named channels, including multiple inputs of
  one type. A new input table must preserve this existing capability even
  though gathering currently deduplicates facts by subject.

Related work in scope: typed proposal envelopes and dispatcher payloads,
resolver parameter context/result, and Wiener's task query object (#275).
These are structural improvements; they should preserve resolver output and
query behavior rather than introduce new product policy.

## Storage approaches considered

| Approach | Strength | Cost / limitation |
|---|---|---|
| Current rows plus separate audit tables | Direct reads, familiar updates | Two representations to maintain; history must be written on every path |
| Retained typed revisions with an explicit current selection | Current and past values use the same representation; evidence can be retained without activating it | Must constrain current selection and serialize replacements |
| Full event sourcing | Reconstructs state by replaying an ordered log | Event evolution, replay, projections and concurrency add substantial machinery |

**Recommendation:** typed relational records with retained revisions and an
explicit selection of the active revision. No timestamp-based "latest wins".
Database constraints should enforce the identity and current selection; the
write service changes them in one transaction. Exact pointer/index layout is
an implementation design to settle in the spec.

Fowler distinguishes audit history from temporal data queried by the application;
here history is used to explain corrections and conflicting observations, so
it deserves a queryable representation. Microsoft's event-sourcing guidance
describes the extra schema, replay and projection complexity. These support
the simpler recommendation for this application; they do not mandate it.

Sources: [Temporal patterns](https://martinfowler.com/eaaDev/timeNarrative.html),
[Event sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing).

## Proposed boundaries

- Separate typed records for inputs, wanted outputs/required states, facts,
  producer pins, parameter overrides and step reviews. Shared attribution
  types and a shared transaction service need not mean one generic value table.
- Preserve a fact's **origin** separately from **who chose to use it**. A
  person selecting an inspector's measurement does not make it person-measured
  or person-stated. Retain evidence and invocation/inspection references where
  available, without storing sample bytes in these records.
- Separate extracted suggestions from accepted decisions. The model's summary
  and question wording are presentation data, not fields of an authoritative goal.
- Compose `Goal` from active decision rows. The resolver and artifact continue
  to consume the existing pure `Goal` type; database identities and timestamps
  must not leak into deterministic pipeline output.
- Keep blueprint and draft projection as computed state with a recorded source
  revision and registry digest. A cached copy is acceptable when it is derived,
  checked for freshness and never an independent writer of decisions.
- A kept artifact is a fixed snapshot of the goal and pipeline used to produce
  it. Subsequent corrections cannot rewrite that artifact or a submitted run.
- Decide the lifetime of decision rows explicitly: putting their ownership on
  a draft is a candidate that lets a draft retain its goal without retaining
  its entire conversation. Session deletion must not silently change the goal.
- Keep historical transcript content intact. Supply current status separately:
  active, removed or superseded, with a link to the change that caused it.

W3C PROV distinguishes attribution, derivation and the activity that used
evidence. This supports separating origin from chooser; adopting RDF or the
whole ontology is unnecessary for the proposed schema.
Source: [PROV data model](https://www.w3.org/TR/prov-dm/).

## Proposed write and review rules

One application service owns draft writes, revision checks and revision changes.
An action validates its submitted revision, serializes changes to the same draft,
records decisions, resolves and updates the projection, marks affected proposals
stale, and records a receipt in the existing transaction. Queue model calls only
after commit. Delayed AI replies must match the decision context they read;
question wording needs a context key, not just a subject.

Postgres row locks serialize overlapping writers but do not detect that a user
submitted an old screen; explicit expected revisions do. SQLAlchemy's version
counter detects stale ORM flushes but does not protect bulk updates. A shared
service must cover every writer, including ordinary draft autosave.
Sources: [Postgres locking](https://www.postgresql.org/docs/17/explicit-locking.html),
[SQLAlchemy versioning](https://docs.sqlalchemy.org/en/20/orm/versioning.html).

Postgres partial unique indexes can enforce one active row per key when using
active flags. A current-pointer layout instead needs foreign-key ownership
constraints. Pick one, then test its actual Postgres behavior and migration.
Source: [Partial indexes](https://www.postgresql.org/docs/17/indexes-partial.html).

Proposal envelopes should be a discriminated union, validated on both write and
read, with a closed shape per card kind. Dispatcher payloads should likewise name
their per-arrow type. Pydantic recommends discriminated unions for predictable
variant selection and generates their OpenAPI discriminator.
Source: [Pydantic unions](https://pydantic.dev/docs/validation/latest/concepts/unions/).

For reviews, compare what was reviewed: contract identity/digest, resolved settings,
relevant wiring, decision provenance and supporting premises. Exclude timestamps,
layout and unrelated facts. Keep unchanged reviews; supersede affected ones.
Whether affected downstream steps also need review is a product decision.

## Brainstorm questions and their resolution

The questions below record the initial recommendations, not pending approval
requests. On 2026-10-11 the operator chose: no automatic replacement, an explicit
chat/diagram disagreement question, cascading corrections shown in the diagram,
accepting truthful unbuildable corrections, returning to unknown, a new draft
after manual edits, and visible history now with undo explicitly deferred.
Migration strategy was delegated to the implementer. The proposed design migrates
recoverable state and preserves ambiguous drafts while retiring only their
unrecoverable sessions from mutation. The operator approved moving to the plan;
the spec is now the approved planning baseline.

1. Conflicting evidence: retain the active answer until an explicit choice, or
   automatically replace it? Recommended: retain and visibly offer the conflict.
2. Corrections: allow an explicit return to unknown? Recommended: yes for a
   measurement; missing essential inputs still stop the build honestly.
3. Review scope: re-review changed steps and downstream dependencies, only
   changed steps, or the entire pipeline? Recommended: changed steps and affected
   dependencies; preserve demonstrably unaffected reviews and obey pacing.
4. An unbuildable correction: refuse it atomically as today, or retain the corrected
   fact and suspend the build? Recommended: retain an explicit factual correction,
   mark the old projection outdated, and resume gathering; speculative tool swaps
   can still be refused. This changes the current protocol and needs approval.
5. Corrections after manual edits: rebuild in place, disallow them, or create a new
   revision/draft preserving the hand-edited work? Recommended: a new draft when
   reconciling those edits would otherwise be ambiguous.
6. Existing sessions: migrate them, or retire them after preserving drafts and kept
   artifacts? Recommended: migration with explicit unknown historical attribution
   where recoverable; offer deliberate retirement if a faithful migration costs
   more than preserving these pre-launch conversations is worth.
7. History UX: expose prior values and why they changed now, or store them now and
   defer browsing? Recommended: a compact fact history now, full replay/undo later.

The approved specification records these choices and their technical design:
[Decisions as rows](../../superpowers/specs/2026-10-11-decisions-as-rows-design.md).

The authority cutover is an online Alembic upgrade. Stop writers, retain a database
backup, and rehearse restore plus upgrade before applying it to a populated installation.
The versioned converter archives the old decision snapshot and records a disposition
for every draft before dropping duplicate JSON columns. Offline SQL rendering raises
an exception before any removal; it cannot be used to bypass conversion. After new
row decisions are written, rollback means restoring the verified backup, not downgrading
the schema and pretending the old JSON can be reconstructed.

The configured development database was offline during implementation and no development
API or worker process was running. Backup/restore and conversion were rehearsed on isolated
Postgres databases; development data was not modified. The next normal startup must run
this online upgrade before launching the new workers.
