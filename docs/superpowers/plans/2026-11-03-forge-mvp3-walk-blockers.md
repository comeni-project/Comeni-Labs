# Forge MVP 3: live-walk blockers #428 and #431

The operator authorised resolving these before the GPU walk and approved both recommended
behavior choices on 2026-11-03, after reviewing the alternatives. The decisions are recorded on both GitHub issues. Independent review and the
mechanical error-reporting fix preceded this approval.

## #428: approved decision

Retain Reject as an unresolved request for correction. Add explicit Remove question
with a reason and retained history; removal settles the question and lets the piece advance.
Explain rejection beside the item so a person can choose another answer or remove a false premise.

Alternatives: making Reject remove silently gives one button two meanings; automatically
redrafting adds a model call and cannot establish whether the premise is false. Both were rejected by the operator. Existing human approval, stale-revision checks and
downstream reopening stay.
The related attribution finding is already addressed by `identity.default_author`: Settings
`system.author` / `COMENI_AUTHOR`, then Git's name, then the explicit unknown fallback. The GPU
walk should configure the curator's name rather than fabricate one in saved history.

## #431: approved decision

Allow contract references introduced by approved question answers marked `new`;
require separate vocabulary declarations before Assembly. Include new types, states and jobs.
Contract completion needs the process and at least one approved input or output port. Unapproved
or arbitrary names stay refused; the final layer loader and conformance remain authoritative.

Alternatives: moving Vocabulary earlier changes the workflow; accepting mixed Contract and
Vocabulary replies widens the draft's mutation scope and complicates validation. Both were rejected by the operator. No vocabulary is silently declared by approving a question.

## Independent mechanical fix

- [x] Reproduce truncated form refusals and model retries that report only a wrong-piece item.
- [x] Share field-level value-error formatting between the person's boundary and model retries.
- [x] Report wrong-piece and value errors together, so a retry can correct the entire reply.
- [x] Verify both regressions fail first, then run the affected API/model suites: 48 passed.

`test_contract_retry_names_bad_fields_as_well_as_wrong_piece_items` failed because the retry
contained only the wrong-piece problem. `test_a_person_refusal_names_each_bad_field` failed
because it received only “3 validation errors for ProcessDraft”. Both now name `nf_process`,
`nf_include` and `container` and their type errors. Nothing is saved from either invalid reply.
Logs: `/tmp/forge-431-fields-red.log`, `/tmp/forge-431-fields-green.log`.

## Implementation

- [x] Expose explicit question removal with required UI reason, captured revision, inline
  refusal recovery and retained question/answer history. Explain that rejection stays unresolved.
- [x] Use only approved answers marked new as draft reference permissions, including types,
  states and jobs. Proposed, rejected, reopened or removed answers grant no permission.
- [x] Read input alternatives and explicit state fields through the existing port models so
  their vocabulary checks agree with `type::state` notation.
- [x] Require the process and at least one approved port before Contract can advance; the
  browser tracker follows the server's first unfinished piece.
- [x] Keep the final vocabulary requirement in Assembly. Missing type declarations now produce
  a Vocabulary refusal instead of an uncaught KeyError.
- [x] Send item status in the typed model payload, retain removed questions as history, and
  separate approved answers as prompt instructions. Draft v3 adds typed examples, zero-based
  positions and process-slot/tuple instructions. Questions v4 honours removed questions.
- [x] Complete backend/frontend/guard checks and browser verification.

Implementation and merge are tracked by PR #447.

Live model calls, tool execution and registry publication remain deferred until the GPU walk.


## Verification

- Focused backend: **363 passed**, covering the pure forge, Forge API and OpenAPI operations.
- Core package: **483 passed**, covering the shared payload/schema changes.
- Frontend: **994 passed**; TypeScript passed. Tests cover explicit removal, retained reasons,
  stale revisions and process-only Contract progress. Removal forms hide competing Answer and
  Reject decisions; its regression failed before that restriction.
- Invariant guards: **95 passed**. Removing the approved-answer filter made three permission
  cases fail; the filter was restored before the final suites. The new-type and completion
  regressions also failed against the original behavior before implementation.
- Browser: three cases at 1440/390 in light/dark (**12 combinations**), including a refused
  removal followed by success, retained removed-question history, and Contract with/without a
  port. No page errors or horizontal page overflow. Screenshots were inspected by eye.
- Lint, generated clients, generated types, documentation, links and size checks passed.
- Logs: `/tmp/forge-blockers-backend-final.log`, `/tmp/forge-blockers-frontend-final.log`,
  `/tmp/forge-blockers-guards.log`, `/tmp/forge-blockers-browser.log` and
  `/tmp/forge-blockers-approval-mutation.log`. Browser artifacts: `/tmp/forge-blockers-preview/`.

The missing-family finding **#441** remains separate: the saved quast draft's `assembly.fasta`
requires a family declaration that Forge cannot yet author. These fixes deliberately preserve
that loader refusal. The operator must choose how families are declared before resuming that
case's live Assembly step. No real model or tool was run in this work.
