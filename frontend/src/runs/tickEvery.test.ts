import { expect, it } from "vitest";

import { tickEvery } from "./Timeline";

/** The axis has one promise — *the largest interval that yields at most six ticks wins* — and
 *  until 2026-09-02 it kept that promise only while the span stayed inside the ladder. Past the
 *  last rung `?? LADDER[LADDER.length - 1]` pinned the step at 24h and the loop ran on: eight
 *  ticks at seven days, sixty at sixty days, and 20,699 for a live run whose `from_ms` is 0.
 *
 *  That is why `Timeline.test.tsx`'s open-bar case timed out in CI at 5s and passed locally —
 *  20,699 SVG nodes is slow, not flaky. `make check` never saw it, because it does not run the
 *  frontend suite at all. This asserts the promise directly rather than through a render, so
 *  the next span nobody imagined fails here in a millisecond instead of there in five seconds. */

const MOST = 6;
const DAY = 24 * 3_600_000;

it.each([
  ["a 40-second stub run", 40_000],
  ["a two-day run", 2 * DAY],
  ["exactly the last rung", DAY],
  ["one tick past the ladder", 7 * DAY],
  ["sixty days", 60 * DAY],
  ["an open run reporting from_ms 0", Date.now()],
  ["absurd, but arithmetic should not care", 1e15],
])("keeps the axis to six intervals for %s", (_what, span) => {
  const marks = tickEvery(span);
  expect(marks.length).toBeLessThanOrEqual(MOST + 1);
  expect(marks[0]).toBe(0);
  expect(marks.every((m) => Number.isFinite(m))).toBe(true);
});

it("still lands on round intervals a person can read", () => {
  // The ladder is the point: past it the step stays a whole number of days rather than
  // becoming span/6, which is what put `2343m 39s` on the axis in the first place.
  const step = tickEvery(60 * DAY)[1];
  expect(step % DAY).toBe(0);
});
