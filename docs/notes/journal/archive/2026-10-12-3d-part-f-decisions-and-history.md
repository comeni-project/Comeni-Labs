# Part F: answers, correction and history

Part F (14.7.8.3d) is implemented on the existing local feature branch. The approved
research/spec/plan led to retained draft-owned decisions as the only live answer authority.
Known answers are never replaced automatically by sample measurements: disagreement asks
keep/use/correct/unknown. Corrections cascade semantic reviews, persist truthful unbuildable
values with recovery, and preserve manual graphs in linked authored forks. History is visible;
undo is explicitly deferred under #302.

Typed offers/commands carry version context, public writes check revisions, and chooser role
is independent of fact origin. Frozen legacy conversion preserves ambiguity and unproved
attribution, archives historical state, and removes duplicate live JSON goal/fact authorities.
Independent constraint order survives row composition and migration. Resolver parameter
context and Wiener task filtering are contained typed refactors.

Verification: Python 3.12.15 make verify passed 3,860 regular tests, all 11 real Nextflow
tests and 95 invariant checks, plus every lint/types/generated-doc/reference/status/link/path/size gate. Frontend: 680 passed, 1 existing skip; TypeScript passed.
Recorded-evidence browser walks exercised disagreement, late delivery, unknown, cascading
reviews, missing-input recovery, manual forks, reload, competing tabs and keyboard recovery.
The final fresh reviewer found two Important defects: stale expanded history and an empty
legacy gathering card stamped with a mismatched revision. Both watched RED→GREEN, fixed in
`6adf90dd`, and the browser confirmed an open history changes its current-answer label after
saving a correction. No deferred Minor findings.

The configured development database was offline and was not changed. Fresh/populated and
verified-backup restore migrations passed on isolated databases. The PGDMP backup remains in
`build/part-f-migration`; reviewed browser captures are in `build/part-f-review`. All five
application images rebuilt after the final fix. The actual development upgrade remains a
controlled startup operation with old writers stopped and a verified backup.

Two unchanged Python 3.14 truncated-gzip failures are tracked separately under #303; those
cases pass on CI Python 3.12/3.13. #296 remains open for its original CI-specific findings.

Part F issues #269/#272/#275/#295/#290 and final review #304 are closed with local evidence.
Only Part F's removed-step/source-label items are checked in #268; the rest stays open.
Next is Part G (#291), canvas and walk defects. The branch is kept locally, without push
or merge.
