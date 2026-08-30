import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

/** **Four things the plan cut and the operator put back.**
 *
 * Each was scoped out during 3C and written up as a "deliberate deviation" in the plan and the
 * journal — which is not the same as asking. The design had all four and they were not mine to
 * drop. These tests exist so that whatever else changes, they cannot go missing quietly again.
 */
const MODULES = [
  { contract_id: "nf-core/star/align@1.11.0", tool: "star/align", process: "STAR_ALIGN",
    roles: ["alignment"], needs: ["fastq.reads"], makes: ["alignment.bam"], container: "x" },
  { contract_id: "nf-core/hisat2/align@1.0.0", tool: "hisat2/align", process: "HISAT2_ALIGN",
    roles: ["alignment"], needs: ["fastq.reads"], makes: ["alignment.bam"], container: "y" },
  { contract_id: "nf-core/multiqc@1.25.1", tool: "multiqc", process: "MULTIQC",
    roles: ["qc_aggregation"], needs: ["qc.report"], makes: ["qc.report"], container: "z" },
];

const PIPELINE = {
  steps: [
    {
      id: "star_align", process: "STAR_ALIGN", contract_id: "nf-core/star/align@1.11.0",
      tier: 3, reason: "a rule matched",
      ports: [
        { name: "reads", type_id: "fastq.reads", side: "in", met: true },
        { name: "gtf", type_id: "annotation.gtf", side: "in", met: false },
        { name: "bam", type_id: "alignment.bam", side: "out", met: true },
      ],
      settings: [{ name: "seq_platform", value: null, via: "ext", tier: 4,
                   reason: "nobody judged it", axis_reason: "", premise: [] }],
    },
  ],
  layout: {
    nodes: [{ id: "star_align", rank: 0, order: 0, x: 0, y: 0, width: 232, height: 78, tier: 3 }],
    wires: [], width: 232, height: 78,
  },
  provenance: { "3": 1, "4": 1 },
  settled_share: 0,
  needs_review: ["star_align"],
};

const TIERS = [
  { tier: 1, name: "Forced", group: "Forced by inputs", what: "", colour: "pea" },
  { tier: 2, name: "Convention", group: "Standard practice", what: "", colour: "pea-soft" },
  { tier: 3, name: "Measured", group: "Check the premise", what: "", colour: "measured" },
  { tier: 4, name: "Undecided", group: "Needs your decision", what: "", colour: "undecided" },
];

function at() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => (String(url).includes("/tiers")
            ? TIERS
            : String(url).includes("/modules")
              ? MODULES
              : PIPELINE),
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

describe("what the design asked for", () => {
  it("answers what could I add, and now does it better than the palette did", async () => {
    // ═══ THE THIRD RESTATEMENT OF THIS TEST, AND THE LOUDEST ═══════════════════════════
    //
    // This file exists so four things the plan cut and the operator put back could not go
    // missing quietly again. **Three of the four were about the left palette**, and the palette
    // is now deleted. That is not the plan cutting them again — it is the browse overlay
    // answering each better, and the honest way to record it is here, in the test that held
    // them, rather than by deleting the file.
    //
    // What each restored thing was protecting, and where it lives now:
    //
    // - *`All modules` answers what could I add* — the picker half of the original pair. The
    //   overlay answers it with search, every role, and the type signature.
    // - *A module can be dragged in; the affordance must be REAL* — the rule was never about
    //   dragging, it was **never offer a control that does nothing**. Adding is now a click, a
    //   keypress, or a port picker, and the drag handlers were deleted WITH their source rather
    //   than left as a drop target nothing can drag onto.
    // - *A card beside the panel, because the content is a sentence* — there is no sentence.
    //   #78: `ModuleContract` has no prose field, `impl-reuse` forbids inventing one, and the
    //   overlay shows the type signature, which is what a contract actually knows.
    //
    // `Browse.test.tsx` holds the overlay's own behaviour. This holds that the QUESTION is
    // still answered somewhere, which is what the operator was protecting.
    at();
    await screen.findAllByTestId("node");
    expect(screen.queryByTestId("module-row")).toBeNull();
    expect(screen.queryByTestId("step-row")).toBeNull();

    fireEvent.contextMenu(screen.getByTestId("canvas"));
    const cards = await screen.findAllByTestId("browse-card");
    expect(cards.length).toBeGreaterThan(0);
    expect(cards.some((c) => c.textContent?.includes("HISAT2_ALIGN"))).toBe(true);
  });

  it("draws a port for each side, in different shapes", async () => {
    // **Inputs and outputs are different shapes**, at the operator's request. The design gives
    // both the same circle and leaves direction to be inferred from which edge it sits on, which
    // works on a mock you already know and not on a graph you are reading for the first time.
    at();
    const ports = await screen.findAllByTestId("port");
    expect(ports).toHaveLength(3);
    const shape = (p: HTMLElement) => (p.querySelector("path") ? "chevron" : "circle");
    expect(ports.filter((p) => p.dataset.side === "in").every((p) => shape(p) === "chevron"))
      .toBe(true);
    expect(ports.filter((p) => p.dataset.side === "out").every((p) => shape(p) === "circle"))
      .toBe(true);
  });

  it("keeps hollow for an input nothing feeds", async () => {
    // The one channel from `dashboard.md` §3 that must survive the shape change: hollow is a
    // required input with nothing behind it, and it is the only thing on a node a reader must act
    // on. Met counts an entry channel, not only a wire — `gtf` arrives from `params.gtf`.
    at();
    const ports = await screen.findAllByTestId("port");
    expect(ports.filter((p) => p.dataset.met === "false")).toHaveLength(1);
  });

  it("names a port on hover, on the canvas rather than in a native tooltip", async () => {
    at();
    const ports = await screen.findAllByTestId("port");
    fireEvent.mouseEnter(ports[0]);
    const label = await screen.findByTestId("port-label");
    expect(label.textContent).toContain("reads");
    expect(label.textContent).toContain("fastq.reads");
  });

  it("keeps a tab for the AI, unwired and saying so", async () => {
    // The rail is three tabs because the design has three. A rail that gains one later moves
    // every position a person had learned — and the slot is the honest place to say that door 1
    // is not open yet.
    at();
    fireEvent.click(await screen.findByTestId("tab-ask"));
    const ask = await screen.findByTestId("ask");
    expect(ask.textContent).toMatch(/not wired yet/i);
    expect(ask.textContent).toMatch(/editable goal card/i);
  });

  it("opens the settings card from the node itself", async () => {
    // `dashboard.md` §5 — from the node's "N settings" button, which is where a person is when
    // they wonder what a step is set to.
    at();
    fireEvent.click(await screen.findByTestId("open-settings"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());
    expect(screen.getByTestId("settings-card").textContent).toContain("seq_platform");
  });
});
