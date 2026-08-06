# Round two — the brief

**Not an audit. The instructions for one.** Written at the end of Plan 1.8 so that whoever
runs round two — human or agent — starts from the method rather than from a blank page.

The loop this belongs to: *fix, re-audit, repeat until no critical finding survives.* Plan 1.8
closed A1–A13 and A15. **A14 is critical and open**, so the loop has not exited. Round two
either closes it or finds the next thing.

## Scope

`main` after [#17](https://github.com/comeni-project/Comeni-Labs/pull/17) merges. **Audit the
fixes hardest.** Three audits running, and the sharpest defect has been in the freshest code
every time — A9 was itself a fix that opened the hole it closed, and A15 was a defect the
previous audit walked past while quoting the invariant that names it.

## The method, and the one change from round one

Round one found A1–A13 **by reading**. In a single day, **reverting** found four inert guards
that reading had not. So:

> **Revert and watch, not read.**

For each guard in `tests/`, break the code it protects — deliberately, minimally, in the way a
careless change would — and confirm the guard fails *and names the right thing*. A guard that
stays green is a finding. A guard that fails with a message that would not lead a reader to the
defect is a smaller finding, and still one.

That is also **A14's closure condition**: it closes when every guard in `tests/` has a recorded
revert that was watched failing. Not when someone reads them and judges them sound — that is
how they were written.

Known inert-guard shapes, from A14's four instances:

| shape | example |
|---|---|
| asserts something both the broken and fixed code satisfy | a drift line that mentions the layer either way |
| a fixture whose two paths default opposite ways, so it agrees with whichever it is not testing | Task 6's single resolver |
| asserts over an empty loop | two contracts that route only one |
| never runs at all | `make check` deselecting the counts-matrix tests |

## Passes

The same five as round one, plus one:

1. **Invariants 1, 14, 15** — the three test-enforced ones. All were defeated in round one by
   shapes the guards were not written against. Ask not "does this catch the bug I have" but
   **"what shape of violation does my break-test not have?"**
2. **Determinism and digests** — byte-identical emission, content addressing, the lockfile.
   A hash over concatenated fields means nothing unless each field can be read only one way.
3. **The doors** — the four in `comeni_core.egress`. Publication has no undo.
4. **The registry as a stack** — invariant 11. Round one covered contracts and missed rules
   entirely (A15). All four kinds of declared data stack: `contracts/`, `rules/`,
   `vocabularies/`, `measurements/`. **Check all four this time.**
5. **What Plan 2 is about to build on** — the `AmbiguityResolver` port, `ReplayResolver`,
   `DecisionRecord`. A16 already lives here.
6. **New: the guards themselves**, by the revert protocol above. This is pass one in
   importance and last in the list only because it needs the others' context.

## Reviewers

**At least two, independent, with no session context.** The point is not extra hands; it is
that someone who did not write the fix does not know which invariant it was *meant* to satisfy,
and therefore reads what is there. Round one's A4 and A5 came from session-context passes and
needed knowledge of what Plans 1.5 and 1.6 had decided — so the split is deliberate, not a
fallback.

**Re-verify every reviewer claim first-hand before recording it.** Round one had one claim with
a right conclusion and a wrong mechanism (recorded in A1), and A8's own account was overstated
in the same way — found only by reverting after the fix had landed.

## Rules for the write-up

- **Findings keep their numbers permanently.** Round two starts at **A17**.
- **Reproduce by execution, not by argument.** A finding with no reproduction is a hypothesis.
- **Say what is not wrong.** Round one's *Clean — attacked and held* section is what makes the
  rest legible; without it a reader cannot tell what was examined from what was skipped.
- **Amend, never rewrite.** A corrected finding gets a dated note beneath it, as A8 has.
- **State the severity honestly even when it is inconvenient.** A14 is critical and open, and
  filing it lower to let the loop exit would have been the easy call.

## Do not re-audit

The toolchain (verified 2026-08-02) and the 2026-08-03 audit's C1–C4, which are closed.
