import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Step } from "../../api/types";
import { COLLECT_CHANNELS, COLLECT_SESSION, COLLECT_STEPS, FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LivingCanvas } from "./LivingCanvas";

/** The canvas as the *Build* and *Question* boards draw it (the board-match pass). */

const mount = (ui: React.ReactElement) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

function fake(extra: Partial<React.ComponentProps<typeof LivingCanvas>> = {}) {
  return mount(
    <LivingCanvas graph={{ ...FAKE_SESSION.graph,
                           nodes: [...FAKE_SESSION.graph.nodes, { id: "samtools_sort", contract_id: "c/sort", params: [] }] }}
                  ghost="samtools_sort" positions={FAKE_SESSION.placement} steps={FAKE_STEPS}
                  channels={FAKE_CHANNELS} authors={{}} selected={null} onSelect={vi.fn()} {...extra} />,
  );
}

function collect(extra: Partial<React.ComponentProps<typeof LivingCanvas>> = {}) {
  return mount(
    <LivingCanvas graph={COLLECT_SESSION.graph} ghost={null} positions={COLLECT_SESSION.placement}
                  steps={COLLECT_STEPS} channels={COLLECT_CHANNELS} authors={{}} selected={null}
                  onSelect={vi.fn()} {...extra} />,
  );
}

describe("a step on the canvas", () => {
  it("counts its values by how they were decided, measured first", () => {
    fake();
    expect(screen.getByTestId("node-footer-star_align")).toHaveTextContent(/^1 measured · 2 settled$/);
  });

  it("marks what it reads with < and what it makes with >", () => {
    fake();
    const node = screen.getByTestId("living-node-star_align");
    expect(node).toHaveTextContent("< fastq.reads::trimmed");
    expect(node).toHaveTextContent("> alignment.bam");
  });

  it("says the step on offer is proposed and not added yet", () => {
    fake();
    expect(screen.getByTestId("node-footer-samtools_sort")).toHaveTextContent("Proposed · not added yet");
  });

  it("marks a step with a value that needs the person", () => {
    const open = { ...FAKE_STEPS.star_align, settings: [
      ...FAKE_STEPS.star_align.settings,
      { name: "strandedness", value: null, via: "ext", tier: 4, reason: "", because: "", axis_reason: "", optional: false, premise: [] },
    ] } as Step;
    fake({ steps: { ...FAKE_STEPS, star_align: open } });
    expect(screen.getByTestId("node-open-star_align")).toBeInTheDocument();
    expect(screen.getByTestId("node-footer-star_align")).toHaveTextContent("1 needs you");
    expect(screen.queryByTestId("node-open-trimgalore")).toBeNull();
  });
});

describe("an input on the canvas", () => {
  it("says Input, its name, its type and how it is read", () => {
    collect();
    const reads = screen.getByTestId("living-source-reads");
    expect(reads).toHaveTextContent("Input");
    expect(reads).toHaveTextContent("reads");
    expect(reads).toHaveTextContent("× 12 samples");
    expect(screen.getByTestId("living-source-reference")).toHaveTextContent("read once per task");
  });

  it("writes nothing on the wires until a step is selected", () => {
    collect();
    const wires = document.querySelector("svg")!;
    expect(wires.textContent).not.toMatch(/once per (task|item)|collect all|samples/);
  });
});

describe("the canvas frame", () => {
  it("captions the pipeline's size and how many samples it runs over", () => {
    collect();
    expect(screen.getByTestId("canvas-caption")).toHaveTextContent(/steps · \d+ inputs/);
    expect(screen.getByTestId("canvas-samples")).toHaveTextContent("12 samples, one task each");
  });

  it("has Fit and a legend of what the colours mean", () => {
    collect();
    expect(screen.getByRole("button", { name: "Fit" })).toBeInTheDocument();
    const legend = screen.getByRole("list", { name: "legend" });
    expect(within(legend).getAllByRole("listitem").map((i) => i.textContent)).toEqual(["settled", "measured", "needs you"]);
    fireEvent.click(screen.getByRole("button", { name: "Fit" }));
  });
});

describe("the minimap (issue 389)", () => {
  it("draws one mark per step, the step on offer included, as the manual builder does", () => {
    fake();
    const map = screen.getByTestId("minimap");
    expect(within(map).getAllByTestId("minimap-mark")).toHaveLength(
      FAKE_SESSION.graph.nodes.length + 1);
  });

  it("marks a step with a value that needs the person in its colour", () => {
    const open = { ...FAKE_STEPS.star_align, settings: [
      ...FAKE_STEPS.star_align.settings,
      { name: "strandedness", value: null, via: "meta", tier: 4, reason: "", because: "", axis_reason: "",
        premise: [], optional: false },
    ] } as Step;
    fake({ steps: { ...FAKE_STEPS, star_align: open } });
    const colours = within(screen.getByTestId("minimap")).getAllByTestId("minimap-mark")
      .map((mark) => mark.style.borderColor);
    expect(colours).toContain("var(--needs-you)");
  });
});

