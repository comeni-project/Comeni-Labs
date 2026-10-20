import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NODE_H, NODE_W } from "../geometry";
import { revealing } from "../useView";
import { FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LivingCanvas } from "./LivingCanvas";

/** The canvas follows the engine (#377): a newly offered or selected step is brought on screen,
 *  without zooming, and a view that already shows it is left alone. */

const VIEW = { x: 250, y: 20, k: 1 };
const SCREEN = { w: 800, h: 500 };
const box = (x: number, y: number) => ({ x, y, w: NODE_W, h: NODE_H });

describe("revealing a step", () => {
  it("leaves the view alone when the step is already on screen", () => {
    expect(revealing(VIEW, box(40, 40), SCREEN)).toBeNull();
  });

  it("centres a step that lies off screen, and never changes the zoom", () => {
    const next = revealing({ ...VIEW, k: 0.8 }, box(1400, 300), SCREEN)!;
    expect(next.k).toBe(0.8);
    expect(next.x + (1400 + NODE_W / 2) * 0.8).toBeCloseTo(SCREEN.w / 2);
    expect(next.y + (300 + NODE_H / 2) * 0.8).toBeCloseTo(SCREEN.h / 2);
  });

  it("brings in a step that is only partly cut off", () => {
    expect(revealing(VIEW, box(800 - 250 - NODE_W / 2, 40), SCREEN)).not.toBeNull();
  });

  it("does nothing before the canvas has a size", () => {
    expect(revealing(VIEW, box(1400, 300), { w: 0, h: 0 })).toBeNull();
  });
});

describe("the living canvas follows its focus", () => {
  afterEach(() => vi.restoreAllMocks());

  const draw = (focus: string | null, positions: Record<string, { x: number; y: number }>) => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      { x: 0, y: 0, top: 0, left: 0, right: SCREEN.w, bottom: SCREEN.h, width: SCREEN.w, height: SCREEN.h,
        toJSON: () => ({}) } as DOMRect);
    render(
      <LivingCanvas graph={FAKE_SESSION.graph} ghost={null} positions={positions} steps={FAKE_STEPS}
                    channels={FAKE_CHANNELS} authors={{}} selected={null} onSelect={() => undefined}
                    focus={focus} />,
    );
    return screen.getByTestId("canvas").querySelector<HTMLElement>("[style*='translate']")!.style.transform;
  };

  it("pans to a focused step that is off screen", () => {
    const far = { star_genomegenerate: { x: 40, y: 40 }, trimgalore: { x: 40, y: 210 }, star_align: { x: 2000, y: 900 } };
    expect(draw("star_align", far)).not.toBe("translate(250px, 20px) scale(1)");
  });

  it("does not move when the focused step is in view", () => {
    const near = { star_genomegenerate: { x: 40, y: 40 }, trimgalore: { x: 40, y: 210 }, star_align: { x: 264, y: 125 } };
    expect(draw("star_align", near)).toBe("translate(250px, 20px) scale(1)");
  });
});
