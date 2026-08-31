import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Canvas } from "./Canvas";
import type { View } from "./useView";

/** `START` is private to `useView` and stays that way — a test does not need the app's
 *  opening camera, only *a* camera. */
const VIEW: View = { x: 250, y: 20, k: 1 };

/** The canvas's three layers, and the one rule that governs each.
 *
 * `impl-geom` keeps them apart deliberately, and the reason is that they answer to three
 * different things:
 *
 * - **the arc field** is anchored to the frame and does not pan — it is ambience
 * - **the grid** pans with the nodes — it is a measuring surface
 * - **the registration marks** are fixed to the frame's bounds
 *
 * Merging any two of them is how a canvas stops reading as an instrument.
 */
function at(props: Partial<React.ComponentProps<typeof Canvas>> = {}) {
  return render(
    <Canvas view={VIEW} onWheel={() => {}} onPointerDown={() => {}} {...props} />,
  );
}

describe("the canvas", () => {
  it("shows no grid at rest", () => {
    // **`n-bcanvas`: *a permanent grid is the loudest hobby-editor signal there is.*** It is a
    // measuring surface, and there is nothing to measure until something is being placed — so
    // it belongs to the gesture, not to the resting screen.
    at();
    expect(screen.getByTestId("grid").style.opacity).toBe("0");
  });

  it("shows it while a step is being moved", () => {
    at({ grid: true });
    expect(screen.getByTestId("grid").style.opacity).toBe("1");
  });

  it("rules it three times, at 1:5:10", () => {
    // One spacing carries no sense of scale, and a single ruling of DOTS — which is what this
    // was — cannot show an alignment, which is the only thing a grid is for during a drag.
    const sizes = at({ grid: true }).container.querySelector<HTMLElement>(
      '[data-testid="grid"]',
    )!.style.backgroundSize;

    for (const ruling of ["80px", "40px", "8px"]) {
      expect(sizes).toContain(ruling);
    }
  });

  it("pans the grid with the nodes and not the field", () => {
    // The two layers move differently ON PURPOSE. A field that panned would be a very large
    // picture behind the graph; a grid that did not would be a backdrop rather than the surface
    // the graph sits on.
    const view = { ...VIEW, x: 120, y: 40 };
    at({ grid: true, view });

    expect(screen.getByTestId("grid").style.backgroundPosition).toBe("120px 40px");
    expect(screen.getByTestId("stage").style.transform).toContain("translate(120px, 40px)");
  });

  it("marks the frame's four corners", () => {
    at();
    expect(screen.getAllByTestId("registration")).toHaveLength(4);
  });
});
