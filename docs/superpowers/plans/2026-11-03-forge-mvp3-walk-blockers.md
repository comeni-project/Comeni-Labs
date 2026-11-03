# Forge MVP 3: live-walk blockers #428 and #431

The operator authorised resolving these before the GPU walk. The repository's rule-change
procedure requires the operator to choose the behavior; two choices were requested while
independent review and mechanical fixes continued.

## #428: proposed decision, awaiting the operator

Recommended: retain Reject as an unresolved request for correction. Add explicit Remove question
with a reason and retained history; removal settles the question and lets the piece advance.
Explain rejection beside the item so a person can choose another answer or remove a false premise.

Alternatives: making Reject remove silently gives one button two meanings; automatically
redrafting adds a model call and cannot establish whether the premise is false. Neither is
assumed approved. Existing human approval, stale-revision checks and downstream reopening stay.
The related attribution finding is already addressed by `identity.default_author`: Settings
`system.author` / `COMENI_AUTHOR`, then Git's name, then the explicit unknown fallback. The GPU
walk should configure the curator's name rather than fabricate one in saved history.

## #431: proposed decision, awaiting the operator

Recommended: allow contract references introduced by approved question answers marked `new`;
require separate vocabulary declarations before Assembly. Include new types, states and jobs.
Contract completion needs the process and at least one approved input or output port. Unapproved
or arbitrary names stay refused; the final layer loader and conformance remain authoritative.

Alternatives: moving Vocabulary earlier changes the workflow; accepting mixed Contract and
Vocabulary replies widens the draft's mutation scope and complicates validation. Neither is
assumed approved. No vocabulary should be silently declared by approving a question.

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

The remaining prompt examples, vocabulary permission and completion rules, question removal UI
and end-to-end guards follow the operator's choice. Neither issue is closed by this partial fix.
Live model calls, tool execution and registry publication remain deferred until the GPU walk.
