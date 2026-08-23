import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

/** **The screen now edits a GRAPH**, so the fixture needs steps rather than only a layout.
 *
 * Plan 3C's canvas took a resolved pipeline and drew it; a builder takes a graph you drew and
 * asks the server to lay it out. An empty fixture used to be enough because nothing depended on
 * there being a graph — now an empty one legitimately renders a blank canvas, which is where a
 * builder starts and is not what these tests are about.
 */
const PIPELINE = {
  steps: [
    { id: "star_align", contract_id: "nf-core/star/align@1.11.0", process: "STAR_ALIGN",
      tier: 4, reason: "", ports: [], settings: [] },
    { id: "samtools_sort", contract_id: "nf-core/samtools/sort@1.21.0", process: "SAMTOOLS_SORT",
      tier: 4, reason: "", ports: [], settings: [] },
  ],
  layout: {
    nodes: [
      { id: "star_align", rank: 0, order: 0, x: 0, y: 0, width: 180, height: 64, tier: 4 },
      { id: "samtools_sort", rank: 1, order: 0, x: 0, y: 128, width: 180, height: 64, tier: 4 },
    ],
    wires: [
      // `points` must be a real elbow: `Wires.d()` reads points[0] and the last one, so an
      // empty list throws inside the render rather than drawing nothing.
      { from_node: "star_align", from_port: "bam", to_node: "samtools_sort", to_port: "bam",
        type_id: "alignment.bam",
        points: [{ x: 90, y: 64 }, { x: 90, y: 96 }, { x: 90, y: 128 }],
        label_at: { x: 90, y: 96 } },
    ],
    width: 401,
    height: 462,
  },
  provenance: { "2": 4, "3": 1 },
  settled_share: 0.8,
  needs_review: [],
};

const MODULES = [
  { contract_id: "nf-core/star/align@1.11.0", tool: "star/align", process: "STAR_ALIGN",
    roles: ["alignment"], needs: ["fastq.reads"], makes: ["alignment.bam"], container: "x" },
];

const TIERS = [
  { tier: 1, name: "Forced", group: "Forced by inputs", what: "", colour: "pea" },
  { tier: 2, name: "Convention", group: "Standard practice", what: "", colour: "pea-soft" },
  { tier: 3, name: "Measured", group: "Check the premise", what: "", colour: "measured" },
  { tier: 4, name: "Undecided", group: "Needs your decision", what: "", colour: "undecided" },
];

function at(body: unknown = PIPELINE) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        // **One stub, two shapes.** `/pipeline/modules` answers a list and `/pipeline/example`
        // an object; a stub returning the same body for every URL made the picker iterate a
        // pipeline and crash the whole tree, which surfaced as *no rail* rather than as
        // anything about modules.
        json: async () => (String(url).includes("/tiers")
            ? TIERS
            : String(url).includes("/modules")
              ? MODULES
              : body),
      }),
    ),
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

  it("gives the canvas a track to grow into", async () => {
    // **A weak guard for a defect no test here can see.** The canvas sits in a flex column under
    // the provenance bar and everything inside it is absolutely positioned, so without `flex-1`
    // it sizes to its content — nothing — and the graph renders into a zero-height box. The bar
    // showed, the nodes did not, and every test in this file still passed: **jsdom has no layout
    // engine**, so height is not a thing it can be wrong about.
    //
    // Asserting a class name is testing a CSS string and it is worth exactly what that is worth.
    // It is here because it names the failure, so a refactor that drops the class has something
    // to trip over. The mechanism that actually caught this was a person opening the page, which
    // is what checkpoint 2 is for.
    at();
    const canvas = await screen.findByTestId("canvas");
    expect(canvas.className).toContain("flex-1");
    expect(canvas.className).toContain("min-h-0");
  });

  it("draws no nodes, because phase 3 has none to draw", async () => {
    // Named rather than left implicit: an empty canvas at this checkpoint is the deliverable,
    // not a bug, and the next phase is what fills it.
    at();
    await screen.findByTestId("canvas");
    expect(screen.queryAllByTestId("node")).toHaveLength(0);
  });
});

describe("the builder is a builder", () => {
  it("offers problems and compare beside the review rail", async () => {
    // Plan 3C shipped a visualiser: a goal in, the resolver searches, nothing on the canvas can
    // be changed. These three tabs are the difference — what is wrong with what YOU drew, and
    // what Mendel would have done instead.
    at();
    expect(await screen.findByTestId("tab-problems")).toBeInTheDocument();
    expect(screen.getByTestId("tab-compare")).toBeInTheDocument();
    expect(screen.getByTestId("tab-review")).toBeInTheDocument();
  });

  it("problems comes before compare, because an illegal graph is not worth diffing", async () => {
    at();
    const tabs = await screen.findByTestId("tab-problems");
    const rail = tabs.parentElement!;
    const order = [...rail.children].map((c) => c.getAttribute("data-testid"));
    expect(order.indexOf("tab-problems")).toBeLessThan(order.indexOf("tab-compare"));
  });

  it("does not render a diff until one is asked for", async () => {
    // `compare` runs a full resolve. It is a button, not a reaction — and an empty table would
    // read as "you and Mendel agree", which is a claim nothing has checked.
    at();
    fireEvent.click(await screen.findByTestId("tab-compare"));
    expect(screen.getByTestId("compare-idle")).toBeInTheDocument();
    expect(screen.getByTestId("run-compare")).toBeInTheDocument();
  });
});
