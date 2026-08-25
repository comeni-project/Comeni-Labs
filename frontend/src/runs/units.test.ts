import { describe, expect, it } from "vitest";

import { ABSENT, pair } from "./units";

const MB = 1024 * 1024;
const GB = 1024 * MB;

describe("a peak against what was asked for", () => {
  /** **The defect this exists for.** `STAR_GENOMEGENERATE` reported `memory_peak_bytes:
   * 3809280` — 3.8 MB — against a 31 GB request, and the overview drew `0.0 / 31 GB` under a
   * footer reading *"— means nothing was reported, never zero"*. The number was real; the
   * shared unit erased it. A reader cannot tell that `0.0` from a true zero, and the Tasks tab
   * spelled the same field `3.6 MB` one click away.
   */
  it("never rounds a measured peak away to zero", () => {
    const drawn = pair(3809280, 33285996544);
    expect(drawn).not.toMatch(/^0(\.0)? \//);
    expect(drawn).toBe("3.6 MB / 31 GB");
  });

  /** One unit stays the rule wherever it costs nothing — two suffixes in one cell is not a
   *  comparison a reader makes at a glance, which is why `pair` exists at all.
   *
   *  **A decimal only below 10**, which is `pair`'s existing rule and not this fix's. Note it
   *  disagrees with `Main.dc.html`, which draws `61.2 / 64 GB`; that divergence is recorded in
   *  the 2026-08-25 conformance audit rather than changed here, because rounding moves every
   *  number on the screen and is a decision rather than a defect. */
  it("keeps one unit when both halves are legible in it", () => {
    expect(pair(31 * GB, 64 * GB)).toBe("31 / 64 GB");
    expect(pair(8.9 * GB, 64 * GB)).toBe("8.9 / 64 GB");
  });

  /** A true zero is still a zero — the fallback triggers on *rounding*, not on smallness. */
  it("still says zero when the measurement is zero", () => {
    expect(pair(0, 64 * GB)).toBe("0.0 / 64 GB");
  });

  /** Half a comparison invites the reader to supply a ceiling they do not have. */
  it("is a dash when either half is missing", () => {
    expect(pair(null, 64 * GB)).toBe(ABSENT);
    expect(pair(31 * GB, null)).toBe(ABSENT);
  });
});
