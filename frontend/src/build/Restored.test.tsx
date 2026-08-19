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
                   reason: "nobody judged it", axis_reason: "" }],
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
  it("keeps both lists — the pipeline's steps and every module", async () => {
    // **Two questions, two tabs.** `In pipeline` answers *where is that step*; `All modules`
    // answers *what could I add*. 3C shipped only the first, which is a table of contents rather
    // than a picker — and the fix is not to replace it, because both are asked.
    at();
    await screen.findAllByTestId("step-row");
    fireEvent.click(screen.getByTestId("left-tab-all"));
    const rows = await screen.findAllByTestId("module-row");
    expect(rows.length).toBe(3);
    fireEvent.click(screen.getByTestId("left-tab-pipeline"));
    expect(screen.getAllByTestId("step-row").length).toBeGreaterThan(0);
  });

  it("offers every module, not only the ones already in the pipeline", async () => {
    at();
    fireEvent.click(await screen.findByTestId("left-tab-all"));
    const rows = await screen.findAllByTestId("module-row");
    expect(rows.length).toBe(3);
    expect(rows.some((r) => r.textContent?.includes("hisat2/align"))).toBe(true);
  });

  it("does not pretend a module can be dragged in", async () => {
    // **It was `draggable` with an `onDragStart` that set data nothing read** — a control that
    // moves under your hand and does nothing. A `Goal` cannot pin a module, so *add this to the
    // pipeline* is not expressible in the engine today; the honest state is a reference list
    // that says so. The builder-versus-visualiser gap is a spec, not a `draggable` attribute.
    at();
    fireEvent.click(await screen.findByTestId("left-tab-all"));
    const rows = await screen.findAllByTestId("module-row");
    expect(rows[0].getAttribute("draggable")).toBeNull();
    expect(screen.getByText(/reference only — placeholder/i)).toBeTruthy();
  });

  it("opens a card beside the panel when a module is hovered", async () => {
    // `dashboard.md` §4 — beside the panel, not under the cursor, because the content is a
    // sentence and it must not cover the rows you are scanning.
    at();
    fireEvent.click(await screen.findByTestId("left-tab-all"));
    const rows = await screen.findAllByTestId("module-row");
    fireEvent.mouseEnter(rows[0]);
    const card = await screen.findByTestId("module-card");
    expect(card.textContent).toContain("Needs");
    expect(card.textContent).toContain("Makes");
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
