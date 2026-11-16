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
  star_align: { ...FAKE_STEPS.star_align, ports: [
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
  it("optional ports are dashed with connect", () => {
    canvas();
    const node = screen.getByTestId("living-node-star_align");
    expect(within(node).getByText("connect")).toBeTruthy();
    const mark = node.querySelector('[data-port-mark][data-optional="true"]') as HTMLElement;
    expect(mark.style.border).toContain("dashed");
    expect(mark.style.background).toBe("transparent");
  });

  it("a per-sample step shows ×N from the analysis's sample count", () => {
    canvas();
    expect(within(screen.getByTestId("living-node-star_align")).getByText("×24")).toBeTruthy();
    expect(within(screen.getByTestId("living-node-star_genomegenerate")).queryByText(/^×/)).toBeNull();
  });

  it("a fan-in port reads all N", () => {
    canvas();
    expect(within(screen.getByTestId("living-node-samtools_sort")).getByText("all 24")).toBeTruthy();
  });

  it("shows the tool's version under its name", () => {
    canvas();
    expect(within(screen.getByTestId("living-node-star_align")).getByText("2.7.11b")).toBeTruthy();
  });

  it("right-click on the empty canvas offers add step here", () => {
    const props = canvas();
    fireEvent.contextMenu(screen.getByTestId("canvas"), { clientX: 300, clientY: 200 });
    fireEvent.click(screen.getByRole("menuitem", { name: "Add step here" }));
    expect(props.onAddHere).toHaveBeenCalled();
    expect(screen.queryByRole("menu")).toBeNull();
  });
});
