# Part F: completed implementation and execution decisions

Part F is implemented locally on `stage-four-the-consultant-build`, in `44d399ad` through `6adf90dd`, following the approved research/spec/plan.

Current answers come from retained selections. Measurement disagreement asks keep/use/correct/unknown; corrections cascade semantic reviews and keep truthful unbuildable answers recoverable; manual work opens a linked authored fork. History is visible; undo remains explicitly deferred under #302.

Final verification after the fresh review fixes: Python 3.12.15 `make verify` passed 3,860 regular tests, all 11 real Nextflow tests and 95 invariant checks, including lint/types/generated-doc/reference/status/link/path/size gates. Frontend: 680 passed, 1 existing skip; TypeScript passed. Populated and restored-backup migration/parity checks passed; all five application images rebuilt. Recorded-evidence browser walks cover disagreement, late delivery, unknown, cascades, missing-input recovery, manual forks, reload, keyboard recovery and stale two-tab saves. The final browser check confirms an expanded history refreshes without toggling and agrees with the authoritative API.

Fresh whole-branch review found two Important defects, both watched RED→GREEN and fixed in `6adf90dd` (#304); no Critical findings or deferred Minors.

The development database was offline and was not modified. Its actual online upgrade remains a controlled startup step with old writers stopped and a verified backup. Two unchanged Python 3.14 gzip inspection failures stay tracked separately in #303; the cases pass on CI Python 3.12/3.13. #296 remains open for its original CI-specific findings.

These are local validation results; the implementation commits have not been pushed or merged. Next: Part G (#291).

The approved [spec](../../superpowers/specs/archive/2026-10-11-decisions-as-rows-design.md)
and completed [plan](../../superpowers/plans/archive/2026-10-11-14.7.8.3d-f-decisions-as-rows.md)
retain the acceptance requirements, per-task checkpoints and final verification. The original
local commit was preserved on `backup/stage-four-before-sync-2026-10-11` before syncing
the requested feature branch to `8c86d198`; Part F commits remain on that local branch.

## Rulings made during execution

1. Existing feature branch is the isolated implementation workspace — user requested work on this local branch and its changes are limited to this task — cost if wrong: move commits to another feature branch.
2. add tests to pytest pythonpath for mandated support.paths on package-only runs — scoped command otherwise fails collection — cost if wrong: remove setting.
3. extend test truncation to actual draft-owned tables without CASCADE — additive ownership constraints correctly prevent parent-only cleanup — cost if wrong: narrow helper to explicit tables.
4. the decision service reports evidence agreement/disagreement/unknown; correction buildability belongs to Task 10 after resolution — rows must accept truthful values independently of buildability — cost if wrong: add a result wrapper there.
5. separate save_in for an existing locked unit of work — opening another unjoined session while holding its draft lock deadlocks — cost if wrong: unify scopes via transaction context.
6. read proposal identity as a scalar before draft lock — caching the ORM proposal before waiting can reuse its old pending state — cost if wrong: refresh the proposal after lock. Existing simultaneous-upload guard failed with both accepted, then passed after fix.
7. model-extracted wants stay in extraction until goal confirmation — the gathering card derives a proposed goal from accepted facts and the tentative want, without making candidate facts active — cost if wrong: refine explicit candidate API representation.
8. prefetch wording expires when earlier answers change its context — preserves truthful wording and fixed options; queue identity includes the new revision/context — cost if wrong: narrow context to declared semantic dependencies.
9. wording stamps travel as immutable pairs of plain values — the pure command boundary correctly rejected a Pydantic object — cost if wrong: expand the closed value vocabulary explicitly.
10. add a synchronous correcting phase shared by typed continuations — one common acting node cannot have several originating phases under the existing validator — cost if wrong: expand phase-specific acting nodes.
11. existing internal amendment/sample command constructors allow omitted version fields during cutover; new public corrections require all three versions and production sample jobs capture them — existing offers already validate their selection context — cost if wrong: make internal fields mandatory and update all fixtures.
12. missing requirement is offered directly by correction_blocked and drawn to reply — the broad original gap walk can ask unrelated questions instead of the precise resolver requirement — cost if wrong: unify requirement discovery in the pure gap planner.
13. already-kept bundles and gates consume the immutable pipeline artifact, and Wiener upload/submit consume independent artifacts — only current-draft materialisation/keep/preview is freshness guarded — cost if wrong: add artifact-version labels to more views; never cancel old runs.
14. recording and dispatch share one workflow-version stamp per action — a completed-session correction otherwise increments twice and offers an immediately old context — cost if wrong: centralize all workflow content writes under this owner.
15. retain delivery identity and a typed one-time observation acknowledgement on evidence access — otherwise equal/kept evidence can be re-asked after a later correction, and late job delivery can duplicate it — cost if wrong: promote acknowledgements to their own revision relation when undo is built.
16. a fork inherits decisions and evidence, but starts a fresh review without manual-graph approvals — those approvals cannot safely certify a newly authored graph — cost if wrong: add explicit inherited review applicability later.
17. correcting has no legacy phase-only derived node — its atomic transaction needs an action payload, and inventing one on resume would be unsafe — cost if wrong: add persisted typed recovery payloads.
18. store nullable typed proposal actor roles and expose legacy null as unknown — names cannot prove whether the chooser was a person, resolver or model — cost if wrong: migrate independently proven legacy roles later.
19. keep inherited history read-only and scoped to the parent snapshot, without locking parent drafts during history reads — corrections lock parent then child, so reverse read locks can deadlock — cost if wrong: use a repeatable read history snapshot.
20. legacy reviews without proved semantic fingerprints remain in the archive; recoverable authored sessions receive a fresh goal confirmation card — avoids certifying current meaning from an unproved historical cursor — cost if wrong: recover individually proved reviews in a future converter version.
21. a completed manual graph with a recoverable goal stays manual and correctable by fork; an ambiguous active walk retires read-only — graph changes cannot be silently overwritten by old workflow approvals — cost if wrong: add an explicitly reconciled resume path.
22. refuse unrepresentable goal constraints and evidence origins rather than silently discard them; retain duplicate unnamed inputs as separate selections — preserves truth even when the resulting pipeline is invalid — cost if wrong: extend the decision vocabulary with a versioned migration.
23. historical chat answers read the original proposal-linked selection, not current facts; unproved legacy typed answers stay unknown — correction must not rewrite what the transcript claims was said — cost if wrong: recover proved original answers from the frozen archive later.
24. configured dev database is offline, with no dev API/workers running; rehearse backup/restore and upgrade on isolated databases and leave the real startup migration to the normal deployment — creating an empty replacement would not upgrade the user's data — cost if wrong: repeat the rehearsal against the real dev backup when it becomes available.
25. offline SQL rendering emits an exception before column removal — offline scripts cannot execute a snapshot-dependent conversion safely — cost if wrong: add a separately verified offline data export/import workflow.
26. explicit authored ownership identifies new zero-revision conversations as already using rows — revision zero alone cannot distinguish new extraction-only sessions from legacy ones — cost if wrong: introduce an explicit authority-version marker.
27. automated browser samples use recorded inspector results delivered through the real dispatcher on a separate throwaway database; upload admission/transport is verified by HTTP tests — no dev workers or live model are running — cost if wrong: repeat the end-to-end upload/operator walk on the deployed stack.
28. allow json/hashlib for the pure authoring package's canonical in-memory review fingerprints — neither hashing nor value serialization performs I/O — cost if wrong: replace the fingerprint adapter without relaxing the transport bans.
29. verify the complete repository on its CI Python 3.12 while retaining the two pre-existing Python 3.14 inspection failures as a separate issue — unchanged inspection code fails alone on 3.14; the same cases and purity checks pass 79/79 on 3.12 — cost if wrong: Python 3.14 operators need the separate inspection fix before relying on truncated gzip evidence.
30. extend the unreleased final cutover with a checked required-state order column and rebuild only the named throwaway database — confirmed goal serialization must be preserved and no real dev migration has run — cost if wrong: an already-upgraded external database would require a follow-up migration rather than editing this unreleased migration.
31. undo stays deferred — approved scope is read-only history now with restoration as a later attributed decision (#302) — cost if wrong: prioritize undo separately without rewriting history.
32. leave Python 3.14 gzip inspection outside this fix pass — unchanged failures have separate issue #303 and pass on CI Python 3.12/3.13 — cost if wrong: 3.14 users need that compatibility fix before inspecting truncated gzip.
33. actual offline dev database upgrade remains a controlled deployment step — isolated populated and restored-backup rehearsals passed; real data must be available before it can be upgraded — cost if wrong: rehearse against the real backup and handle its distinct legacy rows before startup.
34. broader registry compatibility/version lifecycle remains Part H — this review assessed the changed cascade and proposal behavior while the user approved the contained Part F scope — cost if wrong: advance specific compatibility requirements from H before release.
35. keep the requested local feature branch and checkout without a new integration menu — the user authorized local implementation, and no merge or push is needed to finish that scope — cost if wrong: integrate the existing commits later using the user's chosen route.

## Deferred minors

None. The fresh reviewer completed one whole-branch review, resumed after a usage interruption,
and the implementer completed one test-first fix pass. No repeat review was dispatched.
