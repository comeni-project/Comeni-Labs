# Specs

Design authority for a change, written before its plan and argued rather than asserted. Where a
spec and the code it cites disagree, read the spec's own precedence note — some take precedence
and some are descriptions that drifted.

Three kinds live here:

- **Nine per audit root** (`2026-08-07-root-*.md`) — one per root cause behind round two's
  findings, because a fix per finding would have been nine copies of the same repair.
- **Design specs for a change with no audit behind it** — `2026-08-07-the-pipeline-file.md`
  (shipped as Plan 1.10), `2026-08-15-root-5-the-rule-format.md` (Plan 1.15),
  `2026-08-16-code-and-documentation-organisation.md` (issue #41),
  `2026-08-16-registry-ci-and-tool-docs.md` (comeni-registry#2),
  `2026-08-16-the-forge.md` (**replaces Plan 2, which was deleted rather than corrected**),
  `2026-08-17-forge-phase-2.md` (**the phase that puts a model behind `HoleFiller` and creates
  `mendel-ai`** — and §1 resolves the fifth-door question Phase 1 left open: there is no door 5,
  because invariant 14 tracks prompt-derived data on the build path and the forge is offline
  authoring outside it),
  `2026-08-17-vocabulary-proposals.md` (**what a hole needs that the vocabulary cannot express
  yet** — a proposal leaves the hole *open*, because a contract citing an undeclared type is the
  load-time refusal invariant 7 already makes),
  `2026-08-18-the-shared-question.md` (**Plan 2.5 — one `Question` and one `Answer` shared by the
  forge and the build path, and deliberately NOT one blocking rule**; §3.1 is why the difference
  must stay in the containers and the ports rather than becoming a field), and
  `2026-08-18-the-interface.md` (**from a viewer to a tool** — written after slice 1 shipped a
  working backend and a frontend with zero event handlers. Its §1 is an honest inventory of that,
  §2.1 is the argument for building the foundation before the routes, and every phase states what
  you can and cannot do at the end of it, because the failure it corrects was a checkpoint that
  said "the queue on screen" without saying nothing on it worked),
  `2026-08-18-answering.md` (**Plan 3A phase 2** — the answer screen, and the two decisions the
  interface spec left open: `answer-all` is best-effort and reports every refusal, because the
  design's own worked example is a batch with one wrong member; and phase 2 *creates* proposals
  while phase 3 decides them, because a closed choice with no way to decline forces a wrong
  answer),
  `2026-08-18-deciding-proposals.md` (**Plan 3A phase 3** — approving, renaming and rejecting.
  The vocabulary file is written at *land* time in one commit with the contract, honouring
  "one review, not two"; approving deliberately bypasses candidate validation, because an
  approved proposal is by definition not among the candidates; and `verify` checks against the
  registry *as this draft would leave it*),
  `2026-08-18-browsing-contracts.md` (**Plan 3A phase 4** — the contracts list and the module
  page. Drift status comes from `ops.check` per request cached on the registry digest, with the
  cold cost at scale stated rather than discovered; `unverifiable` is a facet and never folded
  into `matching`; and two things are recorded as *absent* rather than faked — pipeline pins,
  and per-field origin, which is discarded when a draft lands),
  `2026-08-18-plan-3.md` (**the API and the interface** — written after Plan 2.5 landed and after
  the interface was designed, which is why it could be specific. Its §4 is the substance: what
  must exist underneath for the screens to be true rather than decorative, each entry naming the
  screen that needs it. It replaced a deliberately thin predecessor that existed only to hold the
  decisions until the code and the design caught up), and
  `2026-08-19-resolving-drift.md` (**Plan 3A phase 5** — what moved, what it means, and taking
  the source's value. Two checkers already ask this question and overlap on two fields, so the
  spec declares the coverage rather than merging them; *"every field checked"* is made honest by
  naming the six fields nothing checks, three of which the router reads; the verdict is a fold
  over a total classification rather than a case analysis; and accepting patches **one line**,
  because a registry contract's comments are its reasoning and a YAML dumper deletes them), and
  `2026-08-19-sources-and-drafting.md` (**Plan 3A phase 6** — the screen `forge-review.md` §9
  lists as *undesigned*, so §3's rule is its authority. Its sharpest finding is that the forge's
  mounted transport **cannot be called from a browser at all** — its request models carry
  `source_root` and `workspace_root`, and a caller choosing those is the second answer to a
  question `settings.py` answers once — which is why every phase since 2 has re-exposed forge
  operations and why `main.py`'s docstring saying otherwise has been false for four phases. The
  mount is removed. Two more: `Workspace.save` overwrites a draft **silently**, and the contract
  version is **not derivable** — two vendored tools have containers with no version tag at all), and
  `2026-08-19-compose-and-prod.md` (**Plan 3A phase 8, which ends 3A** — one image for the api and the worker, carrying the registry and the vendored modules because they are read on nearly every request. Its sharpest moment is that **phase 6's guard decided a phase 7 design question**: serving the SPA from FastAPI needs `app.mount`, which `test_the_served_surface_is_the_openapi_document` refuses, so nginx is forced rather than chosen. And accepting a drift **crashes** when the registry is not a checkout — the rung phase 5 missed and a container makes normal), and
  `2026-08-19-responsiveness.md` (**Plan 3A phase 7, which the audit created** — every registry-touching screen cost 250ms, and one function was responsible. Its decisions split by safety: the pure packages get *speed* and no cache, because a cache in a pure package is how invariant 10 stops being true and because the 1346-test suite is the biggest beneficiary and the one a cache serves worst; only `mendel-api` caches, on the digest, beside the cache phase 4 already built. And the performance property is guarded by **counting, never timing** — a millisecond budget in CI teaches people to re-run.), and
  `2026-08-19-the-landing-page.md` (**Plan 3B** — and its §1 is the whole spec: an Overview
  page was designed and CUT once, because it answered the Queue's question, and
  `forge-review.md` §4 calls the Queue *the only home*. The resolution is that a front door
  answers *what is this and what does it hold*, which no destination answers — and the
  discipline that keeps it there is that **it counts and links, and never lists an item**.
  If that slips, this page should be cut the way the Overview was.)
- **One scheduled on 2026-08-17, after having been unscheduled on purpose** — `2026-08-13-the-rule-drafter.md`, which now runs after forge Phase 2 and before Plan 3 (`notes/README.md` rows 16 and 17). Tier 3 is the
  differentiator and nothing currently produces tier-3 rules; the spec records the design so the
  deferral does not also lose it, and names four hard prerequisites and the central risk.

**Read the relevant spec before starting the part that implements it.** The plan argues from the
spec, and a plan read alone loses the reasons.
