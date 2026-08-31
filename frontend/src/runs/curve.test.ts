import { describe, expect, it } from "vitest";

import { ceilingOf, stepPath } from "./curve";

const BOX = { x0: 0, y0: 0, w: 100, h: 50 };

describe("a curve is drawn as the step function it is", () => {
  it("never draws a derived curve smooth", () => {
    // **The guard this file exists for.** `wiener_core.series` labels a curve `derived` because
    // its shape is invented — a per-task total spread uniformly over its window. A spline
    // converts that honest label into a picture of measurements nobody took, and the change is
    // one word in somebody else's library with no effect on the data.
    const path = stepPath(
      [{ at_ms: 0, value: 4 }, { at_ms: 100, value: 12 }, { at_ms: 200, value: 4 }],
      BOX, { xmax: 200, ymax: 12 },
    );

    for (const bezier of ["C", "c", "S", "s", "Q", "q", "T", "t", "A", "a"]) {
      expect(path).not.toContain(bezier);
    }
    expect(path).toMatch(/^M[\d. ]+(?:[HV][\d.]+)+$/);
  });

  it("holds a value across its interval and jumps at the boundary", () => {
    // A reservation genuinely IS a step: four cpus are held, then twelve. There is no instant
    // at which six were reserved, and a sloping line draws one.
    const path = stepPath(
      [{ at_ms: 0, value: 5 }, { at_ms: 50, value: 10 }],
      BOX, { xmax: 100, ymax: 10 },
    );

    expect(path).toBe("M0.0 25.0H50.0V0.0H50.0");
  });

  it("closes a derived area at the last completion and not at the right edge", () => {
    // The gap after the last completion is hatched by the panel rather than drawn. A curve
    // that ran to the edge would be claiming something about a window nothing reported on.
    const closed = stepPath(
      [{ at_ms: 0, value: 8 }], BOX, { xmax: 200, ymax: 8 },
      { close: true, xend: 100 },
    );

    expect(closed.endsWith("Z")).toBe(true);
    expect(closed).toContain("H50.0");   // xend 100 of xmax 200, in a 100-wide box
    expect(closed).not.toContain("H100.0");
  });

  it("is an empty path rather than a crash when nothing was recorded", () => {
    expect(stepPath([], BOX, { xmax: 100, ymax: 1 })).toBe("");
  });

  it("gives a flat-zero curve an axis rather than dividing by it", () => {
    expect(ceilingOf([{ at_ms: 0, value: 0 }])).toBe(1);
    expect(ceilingOf([{ at_ms: 0, value: 3 }, { at_ms: 1, value: 9 }])).toBe(9);
  });
});
