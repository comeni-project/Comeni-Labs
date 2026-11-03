# Registry redesign, slice 4: question context and reviewer

**Spec:** [slice 4, D1 and D2](../specs/2026-10-31-registry-redesign-design.md). **Issue:** #426.
**Branch:** `registry-redesign-4-context`. **Size:** L. Stop and present options at twice the
estimate; the estimate is the four parts below at the pace of slices 2 and 3.

## Grounding

Checked against the code on 2026-11-02:

- Role files hold bare names, and their meaning sits in YAML comments no code can read.
- `TypeDeclaration` already has `name`, `explain` and `scope`, but only 3 of the 8 types fill
  `explain`, so the type side of a question has the same gap as the role side.
- `services/explain.py` and the builder's `Explain` block give *What is this?* from declared data.
  The forge reuses their marks and vocabulary instead of adding a concept.
- `access_for` falls back to the default model, so a reviewer built the usual way could not be off
  when unset, as D2 requires. It needs its own rule.
- `docs/design/voice.md` is gone with no replacement. Copy follows the builder's and the
  documentation style guide.

## 1. Roles and types say what they mean (engine and registry)

Decided: a role entry takes the same field name a type has, and one role per file stays.

```yaml
declares: role
roles:
  - id: alignment
    explain: Place reads against a reference.
```

- [x] `RoleVocabulary` loads `{id, explain}` and keeps `names`; `explain` is required, so a role with
      no words fails to load (`MD0302`). The old bare form is refused, with no alias.
- [x] `registry_lint`, `publishing._roles`, `assemble` and the fixtures follow.
- [x] `RoleDraft` gains a required `explain`, so a forged role has its words before review; the draft
      prompt asks for them.
- [x] Registry PR, from a writable checkout: nine roles, with `explain` taken from their comments and
      rewritten for a person, plus the five missing type `explain`s. `ENGINE_REF` points at this
      branch. Type `explain` stays optional in the engine: a lab's layer has no duty to fill it, and
      the page simply leaves that line out.
- [x] Operator reviews the wording and runs the release (`gh release create` is refused here).
- [ ] Submodule pinned to the release; `ENGINE_REF` moved to `main` after the merge.

## 2. Each question brings its context (no model)

- [x] Pure, in `mendel-forge`: `uses(script, name)` finds the lines of `main.nf` that use a port.
      Tested on real modules, including a name that also appears as a substring of another.
- [x] `GET /forge/adaptations/{id}/context?item=` returns, for a question:
      - the module's lines, and upstream's description from `meta.yml`, marked as upstream's;
      - the registry's name, `explain` and scope for the suggested and offered types or roles;
      - the contracts already using each one;
      - what the answer decides, from the engine.
      It is read when a question opens and is not part of the polled view. Absent source says so.
- [x] A question card shows these beside the options, using the *curated* and *engine* marks.
      Compare with the Review and Phone boards.
- [x] An output whose declaration is optional says so, from the contract rules (#426's `fastqc` case).

## 3. The reviewer (D2)

- [x] `InvocationPurpose.REVIEW`, prompt `forge.review.v1`, typed reply: one comment per item, each
      with an optional quote and file. Item ids are validated at the boundary.
- [x] `MODEL_FORGE_REVIEW` under Settings → Models. Unset means off: no fallback to the default model.
- [x] `forge_review`, append-only: adaptation, item, revision reviewed, comment, quote, file, model,
      invocation. A comment shows only while its revision is current. Registered in `shapes.py` if it
      holds JSON.
- [x] A separate job on the AI queue after `saved`, so a slow reviewer never holds the piece. It
      records `started`, `asking`, `called` and `saved` as `forge_step`s, and the ladder gains *The
      reviewer reads it*. Failure leaves one line in the chat and the piece untouched.
- [x] A quote is shown only if the engine finds it verbatim in the named file; otherwise the quote is
      dropped and the comment stays. The guard test uses a quote absent from the file and must fail
      with the check removed; recorded in `tests/fixtures/guard-ledger.md`.
- [x] Guard: the reviewer's reply cannot change an item, whatever it says.
- [x] The card shows *Reviewer AI · a model's comment, so check it*, as the boards do.

## 4. Questions ask what an output holds (D1)

- [x] `forge.questions.v3`: for a general output, options offer `type::state`, naming what the file
      holds and never the tool. Replies are recorded for the tests.
- [x] Offered states are validated at the boundary. An undeclared one leads to a reviewed vocabulary
      item, never a silent new state.
- [x] The answer reaches the contract as `qc.report::assembly`, with `format` beside it; the tool
      diagram shows both. Checked by assembling `quast`.

## Done when

- [ ] `make check WIENER_API_TOKEN= COMENI_FORGE_GITHUB_TOKEN=`, frontend tests and `make guards`.
- [ ] `make verify`: the saved contract's content changes through part 4.
- [ ] Opened at 1440 and 390 in both themes, compared with the boards.
- [ ] One real reviewer run on a model, judged by the operator. Recorded replies prove the plumbing,
      not that the comments are any use.
- [x] CHANGELOG and any deviations recorded here.


## Implementation and verification — 2026-11-03

Forge MVP 3, slice 4 is implemented on this branch. Registry PR #26 was already released as
v0.7.0; the submodule now points at that release. Its CI still pins the engine commit containing
part 1. Moving `ENGINE_REF` to `main` follows the Labs merge, rather than changing a release here.

Question context reuses the upstream parser, including nested input tuples and output maps.
Reviewer advice uses scalar columns, so it needs no JSON shape registration. It uses the existing
forge egress payload with declared state signatures. An unset reviewer is explicitly Off in the
model picker; it never inherits the default. Reviewer work is queued before drafting becomes idle,
and comments refresh when that work finishes. Cancellation clears the waiting message.

Tests use canned replies without a model. QUAST's pinned source fixture assembles a report with
`qc.report::assembly` and a separate `tsv` format. The quote guard failed when its source-membership
check was removed, then passed after restoration (guard ledger).

Rendered fixture states were inspected in Chrome at 1440 and 390 pixels, in light and dark themes;
no page errors or horizontal overflow. Screenshots are in `/tmp/forge-slice4-preview/` for this
session. The approved external canvas was inaccessible, so exact Review/Phone board comparison
remains pending. The user explicitly deferred the real reviewer run because this laptop lacks GPU
capacity; no live model was called.

Full Python verification initially reported 3,810 passes and six failures. Five declaration
expectations were updated for this feature and rerun; the unrelated blueprint-navigation test
expects a missing list member's name in Python's `list.index` error, while Python 3.14 reports
`list.index(x): x not in list`. No blueprint behavior was changed here. Consequently `make verify`
cannot be reported green on this interpreter. Remaining stages and targeted results are recorded
below as they complete.


Final targeted results: 370 backend tests passed, including the five updated declaration checks;
95 invariant guards passed; 969 frontend tests passed. TypeScript compilation, Ruff, generated
measurement types, reference documentation, status generation, links, paths and document sizes
passed. The full Python run's blueprint-navigation failure remains outside this slice.


`make slow`: 8 passed, 6 skipped, 5 failed. All five failures trace to Nextflow being absent
from PATH (the three counts assertions share the failed gate run; both join tests cannot start
Nextflow). Real workflow execution therefore remains unverified here, in addition to the explicit
GPU/model deferral. No tool images or model weights were downloaded for this slice.
