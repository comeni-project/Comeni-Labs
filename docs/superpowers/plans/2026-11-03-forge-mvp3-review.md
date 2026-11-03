# Forge MVP 3: review and merge

The operator authorised reviewing and merging redesign slices 4–6, resolving #428/#431 and
leaving the live GPU walk until afterwards. Review scope: question context and reviewer
isolation, constructor data preservation, rule previews, progress and publication views.

## Behavior and requirements

- **#443, fixed:** an explicit union editor survived array index reuse after an earlier row
  was removed. The surviving numeric value could appear as null, hiding its editor. The
  remembered branch is now used only while it matches the current value. The regression failed
  with editor kind 4 instead of 1, then passed after the fix.
- **#444, fixed:** constructor metadata offered `tests:none`, while the protocol requires an
  actual test and always refuses that item. Removed the impossible option; optional pieces
  retain their none constructors. The regression failed against the advertised option before
  the fix and passed afterwards. The schema fixture was regenerated from the service.
- **#446, fixed:** the constructor source-hint test relied on the development cache. Both clean
  CI runners failed on empty hints, and the failure was reproduced locally with an empty cache.
  The source-backed test now copies its own module fixture into an isolated cache; a separate
  test verifies that absent source returns empty hints while retaining constructor schemas.
- Reviewer advice applies no commands and is tied to immutable revisions; source quotes are
  checked against the exact request text. Display filters out superseded revisions. Rule
  previews use the resolver and reject stale revisions. These boundaries must remain intact.
- #428 and #431 remain operator decisions, requested separately during this review. Neither
  rejection-as-removal nor implicit vocabulary declarations is assumed by the reviewed code.

## Design and refactoring

The reviewed services keep source evidence, advice, constructor schemas and rule execution in
separate owners. Constructor field schemas come from command models; backend validation remains
mandatory. The impossible Tests option was a concrete metadata/protocol drift, corrected under
#444. No further structural change is justified for this merge. Review was limited to this
branch and nearby callers; it does not establish live-model or live-tool correctness.

## Verification

- Both new regressions were watched failing before their fixes.
- API constructor suite: 14 passed with an empty external module cache; constructor/editor suite: 15 passed; TypeScript passed. Full frontend: 991 passed. The mixed-list removal also passed in the
  browser at 1440/390 in both themes, without errors or page overflow.
- Earlier slice verification: 342 focused backend, 990 frontend and 95 invariant guards passed;
  44 browser combinations passed at 1440/390 in both themes. Full Python had one pre-existing
  Python 3.14 exception-message mismatch in blueprint navigation. PR CI uses Python 3.12/3.13.
- Live GPU execution and exact external canvas comparison remain outside this merge's evidence.
