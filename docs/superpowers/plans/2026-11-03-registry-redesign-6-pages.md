# Forge MVP 3, slice 6: piece pages and the rest

**Scope:** approved registry redesign, slice 6 (#429). Continue from slice 5 without discarding
its uncommitted work. Size L: four implementation steps, followed by focused verification.
The user authorised continuation; live model and GPU execution remain deferred.

- [x] Give each piece readable details, context and next actions; retain answered questions,
  distinguish input/output labels and order decisions by dependency.
- [x] Add a revision-bound, read-only rule preview using the resolver on the server, including
  a read-length slider when the rule reads read length. Never infer a rule result in the browser.
- [x] Finish progress and hand-over across Assembly, Tests, Pull request, Forging, Releases and
  Tool; preserve existing approval gates and show only recorded data.
- [x] Verify backend/API and frontend behavior, types, repository checks, and browser layouts
  at 1440/390 in both themes. Record unavailable comparisons and execution prerequisites.

The approved external canvas is inaccessible through the browsing tool. Use the written spec
and local boards for implementation; exact canvas comparison remains outstanding. No release,
merge, model call or actual tool run is part of local verification.


## Implementation and verification

- Added structured declared-value details and piece-specific guidance; questions retain their
  wording after answering, selected answers supersede suggestions, and decisions are ordered
  job → inputs → outputs. Actions sit below each item's details.
- Added `POST /forge/adaptations/{id}/rule-preview`: checks the stored item and revision,
  creates hypothetical asserted premises and calls `RuleTable.effects_for`. It stores nothing.
  The browser renders returned effects, including misses, without calculating decisions.
- Refused empty drafts remain visible through their durable events. Forging progress omits
  removed items; filters and active-work polling help follow adaptations. Re-forges draw their
  starting contract before port questions exist. Assembly shows the publication stages; existing
  test, CI and human approval gates remain in force. Tool details work at phone widths.
- Focused backend: **342 passed** (forge API, OpenAPI declaration and mendel-forge).
  Frontend: **990 passed** after the final preview, layout and filter changes.
  TypeScript passed. Lint, generated types, documentation, links and size checks passed.
- Browser: all eleven views at **1440 and 390**, light and dark (**44 combinations**), with
  no page errors or horizontal page overflow. Checked all screenshot comparisons visually;
  exercised piece navigation, Assembly, the rule slider and Forging filtering with fixture APIs.
  Screenshots and browser script are in `/tmp/forge-slice6-preview/` and
  `/tmp/forge_slice6_browser.py`; these are local verification artifacts.
- Invariant guards: **95 passed**.
- Mutation evidence: removing the preview revision check accepts a stale request (200 vs 422);
  removing the summary's removed-item filter overcounts progress (2 vs 1). Both guards failed
  under mutation and passed after restoration; evidence is in the guard ledger.

`make check WIENER_API_TOKEN= COMENI_FORGE_GITHUB_TOKEN=` reached **3,832 passed, 4 skipped,
19 deselected, 1 failed**. Its sole failure is the previously observed
`mendel-authoring/tests/test_blueprint_navigation.py::test_blueprint_lookup_refuses_unknown_steps`:
on Python 3.14, `list.index` says `list.index(x): x not in list`, while the test expects
`missing` in that exception. No authoring code or test was changed for this slice. The remaining
lint/type/documentation checks were run separately and passed.

The external canvas comparison, operator page ratings and live walk remain outstanding. Live model
and tool execution were not attempted. Slices 4–6 are committed together on `registry-redesign-6-pages` for review and push, as
authorised after implementation. No merge, tool publication or registry release was made.
