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
    <LivingCanvas graph={FAKE_SESSION.graph} positions={FAKE_SESSION.placement} steps={FAKE_STEPS}
                  channels={FAKE_CHANNELS} authors={{}} selected={null} onSelect={vi.fn()} {...extra} />,
  );
}

function collect(extra: Partial<React.ComponentProps<typeof LivingCanvas>> = {}) {
  return mount(
    <LivingCanvas graph={COLLECT_SESSION.graph} positions={COLLECT_SESSION.placement}
                  steps={COLLECT_STEPS} channels={COLLECT_CHANNELS} authors={{}} selected={null}
                  onSelect={vi.fn()} {...extra} />,
  );
}

describe("a canvas that starts empty", () => {
  it("draws the first step built while it is open", () => {
    // The agent builds while the canvas is on screen (#463); an early return above a hook made
    // the first step a different number of hooks, and React refuses that.
    const empty = { nodes: [], edges: [] };
    const draw = (graph: typeof empty | typeof FAKE_SESSION.graph) => (
      <QueryClientProvider client={client}>
        <LivingCanvas graph={graph} positions={FAKE_SESSION.placement} steps={FAKE_STEPS}
                      authors={{}} selected={null} onSelect={vi.fn()} />
      </QueryClientProvider>);
    const client = new QueryClient();
    const { rerender } = render(draw(empty));
    expect(screen.getByTestId("canvas-empty")).toBeInTheDocument();
    rerender(draw(FAKE_SESSION.graph));
    expect(screen.getByTestId("living-node-star_align")).toBeInTheDocument();
  });
});

describe("a step with many ports (issue 494)", () => {
  it("draws every port of a many-port step inside it, each on its own row", () => {
    const port = (name: string, side: "in" | "out") =>
      ({ name, type_id: `t.${name}`, side, met: true, states: [], gathers: false });
    const quast = { id: "quast", process: "QUAST", contract_id: "nf-core/quast@5.2.0", tier: 2, runs: "once",
      reason: "", settings: [],
      ports: [...["consensus", "fasta", "gff", "bam", "bai", "reads"].map((n) => port(n, "in")),
              ...["results", "tsv", "report"].map((n) => port(n, "out"))] } as unknown as Step;
    mount(<LivingCanvas graph={{ nodes: [{ id: "quast", contract_id: quast.contract_id, params: [] }], edges: [] }}
                        positions={{ quast: { x: 0, y: 0 } }} steps={{ quast }} authors={{}}
                        selected={null} onSelect={vi.fn()} />);
    const node = screen.getByTestId("living-node-quast");
    expect(node.style.height).toBe("199px");
    const marks = Array.from(node.querySelectorAll<HTMLElement>("[data-port-mark]"));
    expect(marks).toHaveLength(9);
    for (const mark of marks) {
      const top = parseFloat(mark.style.top);
      expect(top).toBeGreaterThan(28);
      expect(top + parseFloat(mark.style.height)).toBeLessThan(199);
    }
    const rows = Array.from(node.querySelectorAll<HTMLElement>("[data-port-row]"));
    expect(rows).toHaveLength(6);
    expect(rows[0]).toHaveTextContent(/consensus.*results/);
    expect(rows[2]).toHaveTextContent(/gff.*report/);
    expect(rows[5]).toHaveTextContent(/^\s*<\s*reads\s*$/);
    // Each row is centred on its own ports' anchor: 56 + 22 × index.
    expect(rows.map((r) => parseFloat(r.style.top) + parseFloat(r.style.height) / 2))
      .toEqual([56, 78, 100, 122, 144, 166]);
  });
});

describe("a step on the canvas", () => {
  it("counts its values by how they were decided, measured first", () => {
    fake();
    expect(screen.getByTestId("node-footer-star_align")).toHaveTextContent(/^1 measured · 2 settled$/);
  });

  it("marks what it reads with < and what it makes with >", () => {
    fake();
    const node = screen.getByTestId("living-node-star_align");
    const [first, second] = Array.from(node.querySelectorAll<HTMLElement>("[data-port-row]"));
    // A row is a port's name; its type and states are its title (issue 494).
    expect(first).toHaveTextContent(/<\s*reads\s*bam\s*>/);
    expect(second).toHaveTextContent(/<\s*index/);
    expect(within(first).getByText("reads").closest("[title]")).toHaveAttribute("title", "fastq.reads::trimmed");
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
  it("draws one mark per step, as the manual builder does", () => {
    fake();
    const map = screen.getByTestId("minimap");
    expect(within(map).getAllByTestId("minimap-mark")).toHaveLength(FAKE_SESSION.graph.nodes.length);
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


describe("a step only some samples take (issue 466)", () => {
  it("is marked on its node, with the samples it takes", () => {
    const steps = { ...FAKE_STEPS, star_align: { ...FAKE_STEPS.star_align, takes_samples: {
      tools: ["nf-core/star/align@2.7.11b"], samples: "samples where read_length >= 70",
      lookup: { facts: [], rule: "implementation:alignment", rows: [], fallback: null,
                fallback_is: "stop" as const, fallback_reason: "" } } } };
    fake({ steps });
    const mark = screen.getByTestId("node-branch-star_align");
    expect(mark.textContent).toBe("some samples");
    expect(mark.getAttribute("title")).toBe("takes only samples where read_length >= 70");
    expect(screen.queryByTestId("node-branch-star_genomegenerate")).toBeNull();
  });
});

describe("Tidy", () => {
  it("gives the server's layout back and fits the drawing", () => {
    const fit = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      { x: 0, y: 0, top: 0, left: 0, right: 400, bottom: 300, width: 400, height: 300, toJSON: () => ({}) } as DOMRect);
    mount(<LivingCanvas graph={COLLECT_SESSION.graph} positions={COLLECT_SESSION.placement}
                        steps={COLLECT_STEPS} channels={COLLECT_CHANNELS} authors={{}} selected={null}
                        onSelect={vi.fn()} />);
    const node = screen.getByTestId("living-node-fastqc");
    fireEvent.pointerDown(node, { clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(node, { clientX: 70, clientY: 40, pointerId: 1 });
    fireEvent.pointerUp(node, { pointerId: 1 });
    const before = screen.getByTestId("canvas").querySelector<HTMLElement>("[style*='translate']")!.style.transform;
    fireEvent.click(screen.getByTestId("tidy"));
    const after = screen.getByTestId("canvas").querySelector<HTMLElement>("[style*='translate']")!.style.transform;
    expect(after).not.toBe(before);
    expect(after).not.toMatch(/scale\(1\)$/);
    fit.mockRestore();
  });
});
