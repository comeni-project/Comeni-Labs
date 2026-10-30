# Forge MVP 5: pull requests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a proven draft becomes a pull request on `comeni-registry`, and a person merges it only
when registry CI is green.

**Architecture:** a pure `publishing` module that places a draft in the registry's layout, checks it
and describes it; a `RegistryPublisher` held only by the forge's publish service; a
`forge_pull_request` table, polled by a cron.

**Tech Stack:** Python 3.12, git, httpx, SQLAlchemy + Alembic, ARQ, React + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-10-30-forge-5-pull-requests-design.md`

**Execution:** native, inline. Forge tests per task, the whole suite once before pushing.

## Global Constraints

- Nothing publishes unless `proven`, re-checked in the job.
- One forge pull request open at a time, by a partial unique index.
- Merging needs a person's click and a green check the server re-reads; it merges the exact head.
- `COMENI_FORGE_GITHUB_TOKEN` reaches the worker alone, and never a command line, remote URL, log,
  stored row or model.
- No live GitHub in tests.

## Review Focus

1. Registry checks fail on the checkout: nothing is pushed, the reason is shown, back to `tested`.
   Test in Task 3.
2. GitHub refuses or is unreachable at open or merge: no stuck phase, and no token in the message.
   Tests in Tasks 2 and 3.
3. CI turns red between the page's read and the click: merge refused. Test in Task 3.
4. A pull request closed or merged by hand on GitHub: noticed by the cron. Test in Task 3.
5. A draft's file would overwrite a shared file: refused with its path. Test in Task 1.

---

### Task 1: Placing, checking and describing a draft

**Files:** Create `packages/mendel-forge/src/mendel_forge/publishing.py`; Test
`packages/mendel-forge/tests/test_forge_publishing.py`

**Interfaces:** Produces `RegistryPublisher`, `PublishUnavailable`, `PullRequest(number, url,
branch)`, `PullRequestState(state, head, checks, says)`, `Change(branch, title, body, author)`,
`ToolFacts(id, name, description, homepage)`, `place(draft, checkout, module_id, tool) ->
list[Path]`, `fragment(checkout, module_id, version, summary)`, `check(checkout) -> list[str]`,
`describe(record: Record) -> str`.

- [x] **Step 1: Write the failing tests** `test_placing_puts_the_tool_in_the_registrys_layout`,
  `test_each_role_gets_its_own_file`, `test_a_new_tool_gets_its_tool_yml`,
  `test_an_existing_tool_yml_is_kept`, `test_a_reforge_replaces_the_tool_folder`,
  `test_a_changed_shared_file_is_refused_with_its_path` (focus 5),
  `test_the_placed_draft_passes_the_registrys_checks`,
  `test_a_broken_checkout_says_what_failed` (focus 1, in part),
  `test_the_description_names_who_approved_what`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement.** `check` runs `registry_lint.lint`, `layers.load`, conformance and the
  docs verb in place, then lints again.
- [x] **Step 4: Run; pass.**
- [x] **Step 5: Commit.**

### Task 2: GitHub

**Files:** Create `packages/mendel-api/src/mendel_api/services/github_publisher.py`,
`tests/guards/test_forge_publisher.py`; Modify `settings.py`, `docker-compose.yml`,
`services/reports.py`; Test `packages/mendel-api/tests/forge/test_github_publisher.py`

**Interfaces:** Produces `GitHubPublisher(repo, token, cache, client=None)`, `publisher() ->
RegistryPublisher | None`, `settings.registry_repo`, `settings.github_token`.

- [x] **Step 1: Write the failing tests**, with a local bare repository and `httpx.MockTransport`:
  `test_checkout_is_a_fresh_main`, `test_opening_pushes_a_branch_and_opens_a_pull_request`,
  `test_the_token_is_not_in_the_clone_or_any_command`, `test_state_reads_the_checks`
  (green, pending when none exist yet, red), `test_merging_names_the_head_it_checked`,
  `test_a_refusal_never_says_the_token` (focus 2), guards
  `test_only_the_publish_service_holds_the_publisher`, `test_only_the_worker_is_given_the_token`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement.** Git authenticates through `GIT_ASKPASS`, a script reading the variable.
  The API learns *set or not* from `COMENI_FORGE_GITHUB_TOKEN_SET`, never the token.
- [x] **Step 4: Run; pass.** `uv lock --check`.
- [x] **Step 5: Commit.**

### Task 3: Publishing and approving

**Files:** Create `services/forge_publish.py`, a migration; Modify `forging/protocol.py`,
`services/forging.py`, `services/forge_tests.py`, `routes/forge.py`, `worker.py`, `models.py`,
`diagnostics.yml`, `services/catalogue.py`, `mendel_forge/state.py`; Test
`packages/mendel-api/tests/forge/test_forge_publish.py`

**Interfaces:** Produces `Phase.PUBLISHING`, `IN_REVIEW`, `MERGED`; `ForgePullRequest(id, adaptation,
number, url, branch, state, checks, digest, opened_by, approved_by, opened_at, merged_at)`;
`forge_publish.start`, `publish`, `approve`, `poll`; `POST /forge/adaptations/{id}/publish`,
`/approve`; `AdaptationView.pull_request`, `publish_unavailable`; `MF0516` no token, `MF0517` the
registry's checks refused, `MF0518` CI not green.

- [x] **Step 1: Write the failing tests** with a fake publisher:
  `test_opening_needs_a_proven_draft`, `test_opening_records_the_pull_request_and_enters_review`,
  `test_a_second_adaptation_cannot_open_while_one_is_open`,
  `test_the_registrys_checks_failing_pushes_nothing` (focus 1),
  `test_github_refusing_at_open_returns_to_tested` (focus 2),
  `test_approve_refuses_unless_green` (pending, red), `test_a_check_gone_red_refuses_at_the_click`
  (focus 3), `test_approve_merges_the_head_and_records_who`,
  `test_a_pull_request_merged_by_hand_is_noticed`, `test_one_closed_by_hand_returns_to_tested`
  (focus 4), `test_a_merged_adaptation_refuses_commands`,
  `test_a_change_in_review_demotes_and_the_next_open_closes_the_old_one`,
  `test_the_catalogue_shows_in_review_and_merged_not_released`, `test_no_token_is_MF0516`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement,** on the shape of `forge_tests`.
- [x] **Step 4: Run; pass.** Regenerate the diagram and diagnostics docs.
- [x] **Step 5: Commit.**

### Task 4: The pages

**Files:** Create `frontend/src/registry/forging/PullRequest.tsx`; Modify `Adaptation.tsx`,
`useForgeActions.ts`, `useAdaptation.ts`, `ForgingList.tsx`, `../states.tsx`, generated client.

- [x] **Step 1: Write the failing tests** `open pull request starts it`, `pending CI disables approve
  and says why`, `green CI approves`, `merged shows the link and what comes next`, `without a token
  it says why`, `in review and merged are real catalogue states`.
- [x] **Step 2: Run; they fail.**
- [x] **Step 3: Implement,** polling every 15 seconds while in review.
- [x] **Step 4: Run** `npx vitest run` and `npx tsc -b`; pass.
- [x] **Step 5: Commit.**

### Task 5: Docs, the whole suite, and the push

- [x] **Step 1:** How-to, `CHANGELOG.md`, `docs/notes/now.md`, a journal entry.
- [x] **Step 2:** The whole Python suite, `make guards`, `make doc-sizes`, `make links`.
- [x] **Step 3:** Commit, and push `forge-5-pull-requests` (operator, 2026-10-30).

## Not in this plan

- The change to `comeni-registry` (spec §6): asks the operator again, once this is on GitHub.
- A real pull request: walked against a test repository with #412.

## Deviations

- Merging runs in a worker job, because only the worker holds the token: `approve` checks the stored
  CI state and queues, and `merge` re-reads it. So a merge refused at the last moment is reported in
  the chat, not as the click's response. `approved_by` doubles as *merging* while the row is open.
- The token moved from every Mendel service to `mendel-worker`, replacing
  `test_the_token_reaches_every_service_that_reads_an_upstream`.
- Tests in Tasks 1 to 3 were written with their code. The key rules were then broken by hand
  (`proven`, the merge's re-read, the registry's checks) and a test failed each time.
- `RegistryPublisher` gained `checkout` and `close`, and `merge` names the head.
