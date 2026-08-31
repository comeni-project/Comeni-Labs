import { describe, expect, it } from "vitest";

import { elbow, path, PORT_GAP, portOffset, SPINE } from "./geometry";

describe("geometry the client owns", () => {
  it("anchors the first port on the spine, whatever its siblings do", () => {
    // **The property the old spread did not have.** `portX` divided the edge by the port count,
    // so declaring one more input moved every wire already drawn — and the browser and the
    // layout had to agree about that count or a wire missed its chevron by 39px. An index-only
    // offset cannot disagree about a count, because it never reads one.
    expect(portOffset(0)).toBe(SPINE);
    expect(portOffset(1)).toBe(SPINE + PORT_GAP);
    expect(portOffset(2)).toBe(SPINE + 2 * PORT_GAP);
  });

  it("does not size a node at all", async () => {
    // A node used to be sized from its declared port count. Every symbol is 172x112 now —
    // `impl-geom` calls that load-bearing, because variable heights put a jog between every
    // pair and the main chain stops reading as a chain.
    const geometry = await import("./geometry");
    expect("heightFor" in geometry).toBe(false);
    expect(geometry.NODE_H).toBe(112);
  });

  it("a straight run is two points, not four", () => {
    // Four points would hand the renderer a zero-length segment to round, which turns a 7px
    // corner into a visible nick on a wire that should be straight. **Along the flow now**, so
    // "straight" means the two ports share a `y`.
    expect(elbow({ x: 0, y: 90 }, { x: 224, y: 90 })).toHaveLength(2);
    expect(elbow({ x: 0, y: 10 }, { x: 224, y: 200 })).toHaveLength(4);
  });

  it("draws a path for both shapes without throwing", () => {
    expect(path(elbow({ x: 0, y: 90 }, { x: 224, y: 90 }))).toMatch(/^M0,90 L224,90$/);
    expect(path(elbow({ x: 0, y: 10 }, { x: 224, y: 200 }))).toContain("Q");
  });

  // **`freeSpot` is deleted, and so are its three tests.** It was correct about what it was
  // given and given the wrong thing: `offsets` are DELTAS added to the layout's position, and
  // it walked a grid of ABSOLUTE cells. `dag-core` already places a new node without overlap,
  // so `useBuilder.addAt` stopped fighting it rather than being handed better arguments.

  it("computes a port's position nowhere but here", () => {
    // **`impl-geom`'s rule, and it is a correctness rule rather than a style one:**
    //
    // > Port positions are DERIVED from node geometry in one place. Never write a coordinate
    // > twice.
    //
    // It was written after the 2026-08-29 walk found every wire sitting 6px above its port and
    // every source stub starting 27px short of the box it left — because the endpoints had been
    // typed separately from the node positions, and the two drifted.
    //
    // The scan looks for arithmetic on a node's own size, which is what a second derivation
    // looks like. Anything needing a port's offset imports `portOffset`.
    const files = import.meta.glob("./*.tsx", { query: "?raw", import: "default", eager: true });

    const offenders: string[] = [];
    for (const [path, raw] of Object.entries(files as Record<string, string>)) {
      // Comments quote the formulas they replaced — a value named in prose is documentation,
      // and a scan that cannot tell it from a declaration turns writing things down into a
      // failure. This repository has been caught by exactly that three times in two days.
      const code = raw
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/(^|[^:])\/\/.*$/gm, "$1");
      if (/NODE_H\s*\/\s*2|placed\.height\s*\/\s*2|node\.height\s*\/\s*2/.test(code)) {
        offenders.push(`${path} derives a port offset of its own`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
