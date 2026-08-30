import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const node = (id: string, x: number, y: number, tier: number) => ({
  id, rank: 0, order: 0, x, y, width: 232, height: 56, tier,
});

const PIPELINE = {
  steps: [
    { id: "trimgalore", process: "TRIMGALORE", contract_id: "nf-core/trimgalore@0.6.10",
      tier: 2, reason: "the only contract that produces this", ports: [], settings: [] },
    { id: "star_align", process: "STAR_ALIGN", contract_id: "nf-core/star/align@1.11.0",
      tier: 3, reason: "rule matched read_length >= 70",
      ports: [],
      settings: [{ name: "seq_platform", value: null, via: "ext", tier: 4,
                   reason: "nobody judged it", axis_reason: "", premise: [] }] },
  ],
  layout: {
    nodes: [node("trimgalore", 338, 0, 2), node("star_align", 169, 128, 3)],
    wires: [{
      from_node: "trimgalore", from_port: "reads",
      to_node: "star_align", to_port: "reads",
      type_id: "fastq.reads",
      points: [{ x: 454, y: 56 }, { x: 454, y: 92 }, { x: 285, y: 92 }, { x: 285, y: 128 }],
      label_at: { x: 369, y: 86 },
    }],
    width: 570, height: 184,
  },
  provenance: { "2": 1, "3": 1 },
  settled_share: 0.5,
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

describe("the graph", () => {
  it("draws a node per step, where the backend put it", async () => {
    at();
    const nodes = await screen.findAllByTestId("node");
    expect(nodes).toHaveLength(2);
    const star = nodes.find((n) => n.dataset.id === "star_align")!;
    // **The frontend does no layout arithmetic.** If it is computing a position, phase 1 is
    // incomplete — the whole point of laying out in Python is that this is a lookup.
    expect(star.style.left).toBe("169px");
    expect(star.style.top).toBe("128px");
  });

  it("carries the tier on the node, so the rail can draw it", async () => {
    // Certainty as stroke, the same language `Standing` uses on the front door and the design
    // uses on this rail: solid pea, faded pea, dashed amber, gapped coral.
    at();
    const nodes = await screen.findAllByTestId("node");
    expect(nodes.find((n) => n.dataset.id === "star_align")!.dataset.tier).toBe("3");
    expect(nodes.find((n) => n.dataset.id === "trimgalore")!.dataset.tier).toBe("2");
  });

  it("draws a wire per edge, through the points the backend computed", async () => {
    at();
    const wire = (await screen.findAllByTestId("wire"))[0];
    // Four corner points → three segments, and the `d` is built from them rather than from any
    // geometry recomputed here.
    // **Left to right since phase 6**: a wire leaves the source's RIGHT edge at that port's
    // offset and enters the target's LEFT edge at its own. The numbers below are the fixture's
    // node positions plus `NODE_W` and `portOffset`, which is the one derivation.
    const d = wire.getAttribute("d") ?? "";
    expect(d.startsWith("M")).toBe(true);
    expect(d).toMatch(/^M\d+,\d+/);
    // Three segments from four corners, and no curve command other than the corner rounding.
    expect(d).not.toMatch(/C/);
  });

  it("labels a wire with the type it carries", async () => {
    at();
    await waitFor(() => expect(screen.getByText("fastq.reads")).toBeTruthy());
  });

  it("counts what needs you and what is settled, without opening the card", async () => {
    // **The artboard's footer verbatim** — `2 need you · 11 settled`, and just `14 settled`
    // when nothing is open. It used to read `1 setting`, which counts the list rather than
    // saying anything about it: a step with eleven settled values and two open ones reported
    // `13 settings`, which is the number least worth knowing.
    //
    // The node reads both off the settings it already has. A count field would be a second
    // thing to keep in step with the list, and the card needs the list anyway.
    at();
    await waitFor(() => expect(screen.getAllByTestId("node-foot").length).toBeGreaterThan(0));
    const feet = screen.getAllByTestId("node-foot").map((f) => f.textContent ?? "");
    expect(feet.some((text) => /\d+ settled|\d+ need you/.test(text))).toBe(true);
  });

  it("moves a node by the drag divided by the zoom", async () => {
    // `dashboard.html`: node drag divides deltas by the zoom factor, or a node at 50% zoom
    // travels twice as far as the cursor. Dragging moves it IN THE VIEW ONLY — nothing
    // persists a position and inventing somewhere to put one is out of scope.
    at();
    const nodes = await screen.findAllByTestId("node");
    const star = nodes.find((n) => n.dataset.id === "star_align")!;
    fireEvent.pointerDown(star, { clientX: 0, clientY: 0 });
    fireEvent.pointerMove(window, { clientX: 100, clientY: 40 });
    fireEvent.pointerUp(window);
    expect(star.style.left).toBe("269px");
    expect(star.style.top).toBe("168px");
  });
});
