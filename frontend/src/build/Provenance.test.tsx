import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const step = (id: string, tier: number) => ({
  id, process: id.toUpperCase(), contract_id: `nf-core/${id}@1.0`,
  tier, reason: "because", ports: [], settings: [],
});
const node = (id: string, tier: number, y: number) => ({
  id, rank: 0, order: 0, x: 0, y, width: 232, height: 56, tier,
});

const FIVE = {
  steps: [step("a", 2), step("b", 2), step("c", 2), step("d", 2), step("e", 3)],
  layout: {
    nodes: [node("a", 2, 0), node("b", 2, 90), node("c", 2, 180), node("d", 2, 270), node("e", 3, 360)],
    wires: [], width: 232, height: 416,
  },
  provenance: { "2": 4, "3": 1 },
  settled_share: 0.8,
  needs_review: [],
};

const RISKY = {
  ...FIVE,
  steps: [step("a", 2), step("e", 4)],
  layout: { ...FIVE.layout, nodes: [node("a", 2, 0), node("e", 4, 90)] },
  provenance: { "2": 1, "4": 1 },
  settled_share: 0.5,
  needs_review: ["e"],
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

function at(body: unknown = FIVE) {
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

describe("the provenance bar", () => {
  it("headlines the share settled without judgement", async () => {
    at();
    await waitFor(() => expect(screen.getByTestId("settled").textContent).toContain("80%"));
  });

  it("does not count a rule that read measured data as settled", async () => {
    // **The one number on this screen that could be dishonest.** Tier 3 is yellow because the
    // machinery worked and the premise still needs checking — folding it into "settled without
    // judgement" would make the element `dashboard.md` calls the product thesis into a slogan.
    at();
    await waitFor(() => expect(screen.getByTestId("settled").textContent).toContain("80%"));
    expect(screen.getByTestId("settled").textContent).not.toContain("100%");
  });

  it("draws one segment per tier, proportional to its share", async () => {
    at();
    const segments = await screen.findAllByTestId("band");
    expect(segments).toHaveLength(2);
    const two = segments.find((s) => s.dataset.tier === "2")!;
    const three = segments.find((s) => s.dataset.tier === "3")!;
    expect(parseFloat(two.style.flexGrow)).toBe(4);
    expect(parseFloat(three.style.flexGrow)).toBe(1);
  });

  it("isolates a tier when its band is clicked", async () => {
    at();
    const segments = await screen.findAllByTestId("band");
    fireEvent.click(segments.find((s) => s.dataset.tier === "3")!);
    const nodes = screen.getAllByTestId("node");
    const dimmed = nodes.filter((n) => n.dataset.dim === "true");
    expect(dimmed).toHaveLength(4);
    expect(nodes.find((n) => n.dataset.id === "e")!.dataset.dim).toBeUndefined();
  });

  it("says plainly when something needs a decision", async () => {
    // Invariant 6: tier 4 is flagged always. A bar that showed 50% settled without naming the
    // half that was not would be the honest number doing dishonest work.
    at(RISKY);
    await waitFor(() =>
      expect(screen.getByTestId("undecided").textContent).toMatch(/1\s*needs your decision/i),
    );
  });
});
