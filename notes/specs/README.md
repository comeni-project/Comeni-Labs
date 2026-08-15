# Specs

Design authority for a change, written before its plan and argued rather than asserted. Where a
spec and the code it cites disagree, read the spec's own precedence note — some take precedence
and some are descriptions that drifted.

Three kinds live here:

- **Nine per audit root** (`2026-08-07-root-*.md`) — one per root cause behind round two's
  findings, because a fix per finding would have been nine copies of the same repair.
- **Design specs for a change with no audit behind it** — `2026-08-07-the-pipeline-file.md`
  (shipped as Plan 1.10), `2026-08-15-root-5-the-rule-format.md` (Plan 1.15),
  `2026-08-16-code-and-documentation-organisation.md` (issue #41).
- **One that is unscheduled on purpose** — `2026-08-13-the-rule-drafter.md`. Tier 3 is the
  differentiator and nothing currently produces tier-3 rules; the spec records the design so the
  deferral does not also lose it, and names four hard prerequisites and the central risk.

**Read the relevant spec before starting the part that implements it.** The plan argues from the
spec, and a plan read alone loses the reasons.
