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
  `2026-08-18-plan-3.md` (**the API and the interface** — written after Plan 2.5 landed and after
  the interface was designed, which is why it could be specific. Its §4 is the substance: what
  must exist underneath for the screens to be true rather than decorative, each entry naming the
  screen that needs it. It replaced a deliberately thin predecessor that existed only to hold the
  decisions until the code and the design caught up).
- **One scheduled on 2026-08-17, after having been unscheduled on purpose** — `2026-08-13-the-rule-drafter.md`, which now runs after forge Phase 2 and before Plan 3 (`notes/README.md` rows 16 and 17). Tier 3 is the
  differentiator and nothing currently produces tier-3 rules; the spec records the design so the
  deferral does not also lose it, and names four hard prerequisites and the central risk.

**Read the relevant spec before starting the part that implements it.** The plan argues from the
spec, and a plan read alone loses the reasons.
