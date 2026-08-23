import { describe, expect, it } from "vitest";

import { COL_PITCH, elbow, freeSpot, heightFor, NODE_W, path, portX } from "./geometry";

describe("geometry the client owns", () => {
  it("spreads ports by the same formula layout.py uses", () => {
    // All three — layout.py, dashboard.html and Port.tsx — must agree, or a wire misses its
    // chevron. That disagreement is exactly the 39px bug the operator found.
    expect(portX(232, 2, 0)).toBeCloseTo(232 / 3);
    expect(portX(232, 2, 1)).toBeCloseTo((232 * 2) / 3);
    expect(portX(232, 1, 0)).toBeCloseTo(116);
  });

  it("sizes a node by its declared ports", () => {
    expect(heightFor(3, 1)).toBeGreaterThan(heightFor(1, 1));
    expect(heightFor(0, 0)).toBe(heightFor(1, 1));
  });

  it("a straight drop is two points, not four", () => {
    // Four points would hand the renderer a zero-length segment to round, which turns a 7px
    // corner into a visible nick on a wire that should be plumb.
    expect(elbow({ x: 90, y: 0 }, { x: 90, y: 128 })).toHaveLength(2);
    expect(elbow({ x: 10, y: 0 }, { x: 200, y: 128 })).toHaveLength(4);
  });

  it("draws a path for both shapes without throwing", () => {
    expect(path(elbow({ x: 90, y: 0 }, { x: 90, y: 128 }))).toMatch(/^M90,0 L90,128$/);
    expect(path(elbow({ x: 10, y: 0 }, { x: 200, y: 128 }))).toContain("Q");
  });

  it("never drops a node on top of another", () => {
    const taken = { a: { x: 0, y: 0 } };
    const spot = freeSpot(taken, { x: 10, y: 10 });
    expect(spot).not.toEqual({ x: 10, y: 10 });
    expect(Math.abs(spot.x) >= NODE_W || Math.abs(spot.y) >= 128).toBe(true);
  });

  it("takes the drop point when it is clear", () => {
    expect(freeSpot({}, { x: 400, y: 300 })).toEqual({ x: 400, y: 300 });
  });

  it("keeps its columns on layout.py's pitch", () => {
    const second = freeSpot({ a: { x: 0, y: 0 } });
    expect(second.x % COL_PITCH === 0 || second.y % 128 === 0).toBe(true);
  });
});
