import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const PIPELINE = {
  steps: [],
  layout: { nodes: [], wires: [], width: 401, height: 462 },
  provenance: { "2": 4, "3": 1 },
  settled_share: 0.8,
  needs_review: [],
};

function at(body: unknown = PIPELINE) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body }),
  );
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/build"] })} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the builder shell", () => {
  it("is three columns", async () => {
    at();
    await waitFor(() => expect(screen.getByTestId("builder")).toBeTruthy());
    expect(screen.getByTestId("modules")).toBeTruthy();
    expect(screen.getByTestId("canvas")).toBeTruthy();
    expect(screen.getByTestId("rail")).toBeTruthy();
  });

  it("resizes each panel only within the range the design gives it", async () => {
    // `dashboard.md` §4 — 190–430 left, 280–560 right. The numbers are the design's, and a
    // panel draggable to 40px is a panel draggable into uselessness.
    at();
    const left = await screen.findByTestId("modules");
    fireEvent.pointerDown(screen.getByTestId("resize-left"), { clientX: 260 });
    fireEvent.pointerMove(window, { clientX: 0 });
    expect(parseInt(left.style.width, 10)).toBeGreaterThanOrEqual(190);
    fireEvent.pointerMove(window, { clientX: 2000 });
    expect(parseInt(left.style.width, 10)).toBeLessThanOrEqual(430);
    fireEvent.pointerUp(window);
  });

  it("collapses to a rail that still says what is blocking the run", async () => {
    // **The rule this test exists for** — `dashboard.md` §4: the collapsed right rail keeps its
    // undecided count on the stub, because hiding the panel must never hide what is blocking
    // your run.
    at({ ...PIPELINE, needs_review: ["star_align", "samtools_sort"] });
    const collapse = await screen.findByTestId("collapse-right");
    fireEvent.click(collapse);
    const rail = screen.getByTestId("rail");
    expect(rail.dataset.collapsed).toBe("true");
    expect(rail.textContent).toContain("2");
  });

  it("zooms toward the cursor, clamped to the design's range", async () => {
    at();
    const canvas = await screen.findByTestId("canvas");
    for (let i = 0; i < 60; i++) {
      fireEvent.wheel(canvas, { deltaY: -100, clientX: 10, clientY: 10 });
    }
    expect(Number(screen.getByTestId("zoom").dataset.k)).toBeLessThanOrEqual(2.2);
    for (let i = 0; i < 200; i++) {
      fireEvent.wheel(canvas, { deltaY: 100, clientX: 10, clientY: 10 });
    }
    expect(Number(screen.getByTestId("zoom").dataset.k)).toBeGreaterThanOrEqual(0.3);
  });

  it("resets to where it started", async () => {
    at();
    const canvas = await screen.findByTestId("canvas");
    fireEvent.wheel(canvas, { deltaY: -400, clientX: 10, clientY: 10 });
    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(Number(screen.getByTestId("zoom").dataset.k)).toBe(1);
  });

  it("draws no nodes, because phase 3 has none to draw", async () => {
    // Named rather than left implicit: an empty canvas at this checkpoint is the deliverable,
    // not a bug, and the next phase is what fills it.
    at();
    await screen.findByTestId("canvas");
    expect(screen.queryAllByTestId("node")).toHaveLength(0);
  });
});
