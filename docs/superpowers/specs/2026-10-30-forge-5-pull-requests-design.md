# Forge MVP 5 — open and approve pull requests; the changelog (#366)

Status: design, awaiting the operator's approval. Parent: #360. Builds on tests (#365). Board 5 could
not be read, so the page follows the issue and is compared with the board later.

## 1. What this adds

Once a draft is **proven** (tested, and the draft on disk is the one that passed), two buttons, as
the operator asked: **Open pull request** pushes a branch to `comeni-registry` and opens a pull
request; **Approve pull request** merges it, only when registry CI is green. The catalogue then
shows *in review* and *merged, not released*.

## 2. The publisher

```python
class RegistryPublisher(Protocol):
    def open_pull_request(self, change: Change) -> PullRequest: ...  # number, url, branch
    def state(self, number: int) -> PullRequestState: ...            # open, merged, closed; checks
    def merge(self, number: int) -> None: ...
```

- The interface is in `mendel-forge`. `GitHubPublisher` is in `mendel-api`: a working clone under the
  forge cache, and the GitHub API over `httpx`. Tests use a fake that records calls.
- **The token is the existing `COMENI_FORGE_GITHUB_TOKEN`**, on the worker alone, never typed into a
  page, logged or sent to a model. Git receives it through an askpass helper, so it is never in a
  command line, a remote URL or `.git/config`. A guard searches errors and stored rows for it.
- Without a token, publishing shows as unavailable and says why; forging works up to green tests.
- `MENDEL_REGISTRY_REPO` names the repository (default `comeni-project/comeni-registry`), so the
  first live run can use a test repository.

## 3. Opening

Opening runs in a worker job from a fresh checkout of `main`:

1. **Refuse unless `proven`**, re-checked in the job, not only at the button.
2. **One forge pull request open at a time** (design answer 1): a partial unique index, not a check
   a race can pass. The next starts after this one merges, so there is no rebase handling.
3. Copy the draft into the checkout in the registry's own layout: the tool folder with its tests,
   each role in its own file, `tool.yml` from the catalogue's metadata, the generated README.
4. Write one **changelog fragment**, `changelog.d/<tool>.md`.
5. **Run the registry's own checks locally** (`mendel lint`, `docs --check`, `conformance`, layer
   load), and refuse with what they said. A forge pull request should not be how we learn it fails.
6. Push the branch, `forge/<tool>-<version>`, and open the pull request.

**The description is written by the engine, not a model:** what the tool is, each piece's items, who
approved each, who answered each question, which were the AI's, the test runs and the draft's digest.
It is a record, so it stays exact and needs no model. The design's AI summary can join it later.

A person's name comes from Settings (`identity.default_author`); the GitHub actor is the token's
account (design answer 8).

## 4. Approving

- The job's record lives in `forge_pull_request`: adaptation, number, url, state, checks, digest.
- A cron every 60 seconds reads open pull requests, as tests do: restarts lose nothing, an idle
  stack does no work, and one merged or closed on GitHub by hand is noticed.
- **Approve merges only when CI is green and the pull request is open.** Pending or red disables the
  button and says why; the server re-reads the checks before merging, and refuses otherwise.
- Merging records who approved it. The adaptation ends as `merged`.
- A pull request closed unmerged returns the adaptation to `tested`, so it can be opened again.
- A review or CI failure is fixed by changing the adaptation: that demotes it to `reviewing`, and the
  open pull request is closed by the engine when a new one opens. Forcing a push is not offered.

## 5. The flow and pages

`tested → publishing → in_review → merged`, with `publishing → tested` on a failure. The assembled
panel gains the two buttons, the pull request's link and checks, and the reason when either is
unavailable. The catalogue's two placeholder states become real, from `forge_pull_request`.

## 6. Prerequisites in `comeni-registry`

These land before the first forge pull request can pass registry CI:

- `layout.test: [tools/]` in `registry.yml`, and `changelog.d/` with the registry's CONTRIBUTING.
- `ENGINE_REF` moved to a Comeni-Labs commit that understands `declares: test`. **That commit must
  be on GitHub**, so MVP 3–5 must be pushed first. CI then keeps its current checks, with no
  containers (design answer 5).

Then `AHEAD_OF_THE_REGISTRY` goes from this repository's test.

## 7. Not in this MVP

- Forging from `comeni-registry` `main` rather than the app's registry (design answer 1): the check
  in §3 runs against `main`, so a stale base fails there. Releases (#367) settle the base.
- A real pull request: built against the fake publisher, and walked against a test repository.
- Editing an existing rule table or role alternatives across tools: a draft adds files, and a
  shared file it must change is refused with its path until the first real tool needs it.

## 8. Costs and risks

- Mendel's worker can now write to a public repository. The token should be fine-grained, limited to
  that repository's contents and pull requests.
- Merging is outward and hard to undo. It takes a person's click, a server-side green check and a
  matching digest; nothing merges on its own.
- An engine-written description is plainer than an AI summary, in exchange for being exact.
