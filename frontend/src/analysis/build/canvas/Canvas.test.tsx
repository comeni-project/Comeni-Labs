import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../../../app/queryClient";
import { FAKE_SESSION, FAKE_STEPS } from "../../../build/living/fake";
import { LivingCanvas } from "../../../build/living/LivingCanvas";

const port = (name: string, type_id: string, side: "in" | "out", extra = {}) =>
  ({ name, type_id, side, met: true, states: [], gathers: false, optional: false, accepts: [], adds: [], ...extra });

const STEPS = {
  ...FAKE_STEPS,
  star_align: { ...FAKE_STEPS.star_align, does: "Align reads", ports: [
    port("reads", "fastq.reads", "in"), port("index", "genome.index.star", "in"),
    port("gtf", "annotation.gtf", "in", { optional: true, met: false }),
    port("bam", "alignment.bam", "out")] },
  samtools_sort: { ...FAKE_STEPS.samtools_sort, runs: "once", ports: [
    port("bam", "alignment.bam", "in", { gathers: true }), port("bam", "alignment.bam", "out")] },
};

function canvas(over: Partial<Parameters<typeof LivingCanvas>[0]> = {}) {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => [] })));
  const props = {
    graph: FAKE_SESSION.graph, positions: FAKE_SESSION.placement, steps: STEPS as never, authors: {},
    selected: null, onSelect: vi.fn(), samples: 24, onAddHere: vi.fn(), ...over,
  };
  render(<QueryClientProvider client={makeClient()}><LivingCanvas {...props} /></QueryClientProvider>);
  return props;
}

afterEach(() => vi.unstubAllGlobals());

describe("the Build canvas", () => {
  it("an optional input not in use folds into +N optional", () => {
    canvas();
    const node = screen.getByTestId("living-node-star_align");
    expect(within(node).getByTestId("node-folded-star_align")).toHaveTextContent("+1 optional");
    expect(node.querySelector('[data-port-mark][data-optional="true"]')).toBeNull();
  });

  it("a per-sample step shows ×N from the analysis's sample count", () => {
    canvas();
    expect(within(screen.getByTestId("living-node-star_align")).getByText("×24")).toBeTruthy();
    expect(within(screen.getByTestId("living-node-star_genomegenerate")).queryByText(/^×/)).toBeNull();
  });

  it("a fan-in port reads all N", () => {
    canvas();
    expect(screen.getByTestId("living-node-samtools_sort").querySelector('[data-port-mark="gather"]')).not.toBeNull();
  });

  it("a step says what it does, then its tool and version", () => {
    canvas();
    const node = screen.getByTestId("living-node-star_align");
    const does = within(node).getByTestId("node-name-star_align");
    const tool = within(node).getByTestId("node-tool-star_align");
    expect(does).toHaveTextContent("Align reads");
    expect(does.compareDocumentPosition(tool) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(tool).toHaveTextContent("star align 2.7.11b");
  });

  it("an input several steps read draws as one shared trunk", () => {
    canvas({ channels: [{ name: "gtf", param: "gtf", type_id: "annotation.gtf", grain: "study", count: null,
                          states: [], ports: ["star_genomegenerate.fasta", "star_align.gtf"] }] as never });
    expect(screen.getByTestId("trunk-gtf")).toBeTruthy();
    expect(screen.getByText("gtf · shared")).toBeTruthy();
  });

  it("right-click on the empty canvas offers add step here", () => {
    const props = canvas();
    fireEvent.contextMenu(screen.getByTestId("canvas"), { clientX: 300, clientY: 200 });
    fireEvent.click(screen.getByRole("menuitem", { name: "Add step here" }));
    // Where on the drawing the step goes: the click, in canvas coordinates.
    expect(props.onAddHere).toHaveBeenCalledWith({ x: expect.any(Number), y: expect.any(Number) });
    expect(screen.queryByRole("menu")).toBeNull();
  });
});
