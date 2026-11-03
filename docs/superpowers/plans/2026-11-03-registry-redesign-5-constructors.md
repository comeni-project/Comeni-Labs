# Forge MVP 3, slice 5: constructors and pickers

**Spec:** [slice 5](../specs/2026-10-31-registry-redesign-design.md). **Issue:** #427.
**Authorized:** operator asked to proceed to the next slice. Slice 4's uncommitted work is
preserved on this dependent branch, `registry-redesign-5-constructors`.

Replace both raw item editors with one constructor selected by piece and item kind. The
server supplies the existing value models' schemas; these describe fields, not a second
validation protocol. Existing command validation remains authoritative. Nested lists, maps
and alternatives need controls too, so existing values survive an edit without losing fields.
Registry references use the shared picker. Source channel names guide question and port
construction. Settings expose a typed default and a preview of the declared route/template.
Save waits for the server; refusals retain the form, and success names the saved item.

Estimate: four implementation parts below, comparable to slice 3. Reassess if the work
grows to twice that scope. Live model and real tool execution remain deferred on this laptop.

- [x] Supply constructor schemas from the existing value models and module channel hints.
- [x] Build fields, nested controls, registry pickers and setting preview.
- [x] Replace Write and Change; retain revision checks, inline errors and save feedback.
- [x] Verify commands, refusal recovery and preservation of nested values; frontend suite,
      types, relevant backend tests and browser at 1440/390 in both themes.

The approved external canvas was inaccessible during slice 4; exact board comparison remains
pending if it is still inaccessible. Inspect the implemented forms in the browser regardless.


## Verification and remaining checks

Implemented locally, without a model call or real tool run. Slice 4 changes remain intact;
no commit or push was made.

- Backend: 328 tests passed across the forge, pure forge package and OpenAPI declarations.
  The browser fixture is checked against the live command models' constructor schemas.
- Frontend: 983 tests passed in 114 files; TypeScript build passed. Coverage includes nested
  edits, vocabulary declaration/extension switching, setting route changes, inline refusal
  recovery, successful save feedback, pending saves and stale revision handling.
- Invariant guards: 95 passed. Ruff, generated type/document checks, documentation status,
  links, source paths, size budgets and `git diff --check` passed.
- Browser: question construction with a registry pick, setting edits and test construction
  at 1440 and 390 px, light and dark. All 12 combinations had no page errors or horizontal
  overflow. Inspected desktop setting and phone question/test screenshots by eye. Screenshots
  are in `/tmp/forge-slice5-preview/` for this session.
- Browser testing found [#442](https://github.com/comeni-project/Comeni-Labs/issues/442):
  the chat intercepted the phone picker's Use button because the anchored selector overrode
  its phone stacking order. Fixed the phone selector; the actual click now succeeds.
- Mutation evidence: replacing the editor's captured revision with the refreshed item's
  revision failed the background-refresh test (sent 8 instead of 7). Restored the captured
  revision; the frontend suite passed. See `/tmp/forge-slice5-revision-mutation.log`.

The external approved canvas remains inaccessible, so exact board comparison is pending.
Live model/real tool execution remains deferred as authorized. The full Python/check/verify
commands were not repeated: slice 4 recorded the unrelated Python 3.14 blueprint-navigation
failure and absent Nextflow. Their results are not claimed green by this slice.
