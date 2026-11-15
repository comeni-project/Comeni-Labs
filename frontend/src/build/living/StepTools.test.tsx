import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthoringSession, DraftGraph, Step } from "../../api/types";
import { makeClient } from "../../app/queryClient";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LivingSurface } from "./LivingSurface";
import { framed } from "./frame";

/** Changing a step that is already on the canvas — Task 14's *preserve swapping and settings*.
 *
 * A step's tools open in its card or from its menu, beside it on the canvas (#499), and every
 * change leaves through the session's one edit verb — so the
 * server writes the receipt and restamps only the decision that moved. A tool that saved the
 * draft any other way would change the pipeline and leave the log saying nothing about it.
 */

afterEach(() => vi.unstubAllGlobals());

const ALIGN = "nf-core/star/align@2.7.11b";
const HISAT = "nf-core/hisat2/align@1.0.0";

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

const TIERS = [
  { tier: 1, name: "Forced", group: "Forced by inputs", what: "", colour: "pea" },
  { tier: 2, name: "Convention", group: "Standard practice", what: "", colour: "pea-soft" },
  { tier: 3, name: "Measured", group: "Check the premise", what: "", colour: "measured" },
  { tier: 4, name: "Undecided", group: "Needs your decision", what: "", colour: "undecided" },
];

const CANDIDATES = {
  candidates: [
    { contract_id: ALIGN, port: "bam", process: "STAR_ALIGN", tool: "star/align", surplus: 0,
      priority: 10, why: "produces alignment.bam" },
    { contract_id: HISAT, port: "bam", process: "HISAT2_ALIGN", tool: "hisat2/align", surplus: 0,
      priority: 0, why: "produces alignment.bam" },
  ],
  total: 2,
};

const STEPS = {
  ...FAKE_STEPS,
  star_align: {
    ...FAKE_STEPS.star_align,
    settings: [{ name: "seq_platform", value: null, via: "ext", tier: 4, reason: "no rule matched",
      axis_reason: "", optional: false, premise: [], because: "" }],
  },
  fastqc_1: { id: "fastqc_1", process: "FASTQC_1", contract_id: "nf-core/fastqc@0.12.1", tier: 2,
    runs: "per_item", reason: "", settings: [], ports: [] },
} as unknown as Record<string, Step>;

/** Nothing pending, so the log is history and the composer is open. */
const RESTED = {
  ...FAKE_SESSION,
  turns: FAKE_SESSION.turns.filter((t) => t.state !== "pending"),
  working: false,
} as AuthoringSession;

function living(selected: string | null, graph: DraftGraph = RESTED.graph) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes("/tiers")) return ok(TIERS);
    if (u.includes("/candidates")) return ok(CANDIDATES);
    if (u.includes("/validate")) return ok({ findings: [] });
    return ok({});
  }));
  const onEdit = vi.fn();
  render(
    <QueryClientProvider client={makeClient()}>
      <LivingSurface
        session={framed({ ...RESTED, graph, placement: { ...RESTED.placement, fastqc_1: { x: 488, y: 300 } } } as AuthoringSession, STEPS)}
        graph={graph}
        selected={selected}
        preview={null}
        onSelect={vi.fn()}
        composer=""
        onCompose={vi.fn()}
        sending={[]}
        onSay={vi.fn()}
        onAnswer={vi.fn()}
        onRetry={vi.fn()}
        onReviewed={vi.fn()}
        onAddStep={vi.fn()}
        onDismiss={vi.fn()}
        onSetParam={vi.fn()}
        onEdit={onEdit}
      />
    </QueryClientProvider>,
  );
  return onEdit;
}

/** The step's card, beside it on the canvas (#499). */
const stepTab = () => screen.getByRole("region", { name: /^step card / });

describe("a selected step's tools", () => {
  it("opens beside the step, with its other tools a click away", () => {
    living("star_align");
    expect(within(stepTab()).getByRole("button", { name: "Swap tool…" })).toBeInTheDocument();
    expect(within(stepTab()).getByRole("button", { name: "Edit values" })).toBeInTheDocument();
  });

  it("is offered for nothing when nothing is selected", () => {
    living(null);
    expect(screen.queryByRole("region", { name: /^step card / })).toBeNull();
  });

  it("is offered for a step added by hand, which no decision in the log created", () => {
    const graph = {
      ...RESTED.graph,
      nodes: [...RESTED.graph.nodes, { id: "fastqc_1", contract_id: "nf-core/fastqc@0.12.1", params: [] }],
    };
    living("fastqc_1", graph);
    expect(stepTab()).toHaveAccessibleName("step card FASTQC_1");
  });
});

describe("changing a step goes through the session's edit", () => {
  it("removes a step only after asking, and its wires go with it", () => {
    const onEdit = living(null);
    fireEvent.contextMenu(screen.getByTestId("living-node-star_align"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Remove step…" }));
    expect(onEdit).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Remove STAR_ALIGN" }));
    expect(onEdit).toHaveBeenCalledOnce();
    const sent: DraftGraph = onEdit.mock.calls[0][0];
    expect(sent.nodes.map((n) => n.id)).toEqual(["star_genomegenerate", "trimgalore", "samtools_sort"]);
    expect(sent.edges).toEqual([]);
  });

  it("keeps the step when removing is taken back", () => {
    const onEdit = living(null);
    fireEvent.contextMenu(screen.getByTestId("living-node-star_align"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Remove step…" }));
    fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
    expect(screen.queryByRole("button", { name: "Remove STAR_ALIGN" })).toBeNull();
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("stages typed values and sends them as one edit — never one per keystroke", async () => {
    // A receipt per character is `set STAR_ALIGN.seq_platform to I`, then `to IL`, … in the log
    // and a revision per key, each staling whatever step is on offer.
    const onEdit = living("star_align");
    fireEvent.click(screen.getByRole("button", { name: "Edit values" }));
    const field = await screen.findByTestId("setting-field");
    fireEvent.change(field, { target: { value: "ILL" } });
    fireEvent.change(field, { target: { value: "ILLUMINA" } });
    expect(onEdit).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Use these values" }));
    expect(onEdit).toHaveBeenCalledOnce();
    const sent: DraftGraph = onEdit.mock.calls[0][0];
    expect(sent.nodes.find((n) => n.id === "star_align")?.params).toEqual([
      { name: "seq_platform", value: "ILLUMINA", why: "" },
    ]);
  });

  it("swaps a step's contract, keeping its id and so its wires", async () => {
    const onEdit = living("star_align");
    fireEvent.click(screen.getByRole("button", { name: "Swap tool…" }));
    const [hisat] = await screen.findAllByTestId("swap-option");
    fireEvent.click(hisat);
    const apply = await screen.findByTestId("apply-swap");
    await waitFor(() => expect(apply).toBeEnabled());
    fireEvent.click(apply);

    expect(onEdit).toHaveBeenCalledOnce();
    const sent: DraftGraph = onEdit.mock.calls[0][0];
    expect(sent.nodes.find((n) => n.id === "star_align")?.contract_id).toBe(HISAT);
    expect(sent.edges).toEqual(RESTED.graph.edges);
  });
});
