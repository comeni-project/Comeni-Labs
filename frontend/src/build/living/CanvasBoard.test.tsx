import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
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
    // Six inputs: the compact card grows by one port gap a row (#511): 64 + 18 × 5.
    expect(node.style.height).toBe("154px");
    const marks = Array.from(node.querySelectorAll<HTMLElement>("[data-port-mark]"));
    expect(marks).toHaveLength(9);
    for (const mark of marks) {
      const top = parseFloat(mark.style.top);
      expect(top).toBeGreaterThan(40);
      expect(top).toBeLessThan(154);
    }
    // Names show where a side has several: one label a port, centred on its anchor, 50 + 18 × index.
    const labels = Array.from(node.querySelectorAll<HTMLElement>("[data-port-row]"));
    expect(labels).toHaveLength(9);
    expect(labels.slice(0, 6).map((l) => l.textContent)).toEqual(["consensus", "fasta", "gff", "bam", "bai", "reads"]);
    expect(labels.slice(0, 6).map((l) => parseFloat(l.style.top) + 7)).toEqual([50, 68, 86, 104, 122, 140]);
  });
});

describe("a step on the canvas", () => {
  it("draws inputs as circles and outputs as triangles, named where a side has several", () => {
    fake();
    const node = screen.getByTestId("living-node-star_align");
    expect(node.querySelectorAll('[data-shape="circle"]').length).toBeGreaterThan(1);
    expect(node.querySelectorAll('[data-shape="triangle"]').length).toBeGreaterThan(0);
    const [first, second] = Array.from(node.querySelectorAll<HTMLElement>("[data-port-row]"));
    // A label is a port's name; its type and states are its title (issue 494).
    expect(first).toHaveTextContent("reads");
    expect(second).toHaveTextContent("index");
    expect(first).toHaveAttribute("title", "fastq.reads::trimmed");
  });

  it("marks a step with a value that needs the person", () => {
    const open = { ...FAKE_STEPS.star_align, settings: [
      ...FAKE_STEPS.star_align.settings,
      { name: "strandedness", value: null, via: "ext", tier: 4, reason: "", because: "", axis_reason: "", optional: false, premise: [] },
    ] } as Step;
    fake({ steps: { ...FAKE_STEPS, star_align: open } });
    expect(screen.getByTestId("node-open-star_align")).toHaveTextContent("1 open");
    expect(screen.queryByTestId("node-open-trimgalore")).toBeNull();
  });
});

describe("an input on the canvas", () => {
  it("says what it is and what answers it: how many samples, or the file Data gave", () => {
    collect();
    const reads = screen.getByTestId("living-source-reads");
    expect(reads).toHaveTextContent("12 samples");
    expect(reads.getAttribute("title")).toContain("params.reads");
    expect(screen.getByTestId("living-source-reference")).toHaveTextContent("not given yet");
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

describe("an input beside a tall step (plan 2 review)", () => {
  it("is placed below the step's full height, not over its rows", async () => {
    const { place } = await import("../Sources");
    const below = place("Input", { x: 0, y: 0 }, 0, false, { w: 120, h: 80 }, 199);
    expect(below.box.y).toBeGreaterThanOrEqual(199 + 20);
  });
});

describe("a step that measures a fact for another (walk 2026-11-15)", () => {
  it("draws a dotted line from the measuring step to the step it decides, with the whole label", () => {
    const measure = { id: "measure_len", process: "MEASURE", contract_id: "comeni/measure/genome_length_fai@1.0.0",
      tier: 1, runs: "once", reason: "", settings: [], ports: [] };
    const index = { id: "star_index", process: "STAR_INDEX", contract_id: "nf-core/star/genomegenerate@2.7.11b",
      tier: 2, runs: "once", reason: "", ports: [], settings: [{ name: "sa_index_nbases", value: null, via: "ext",
        tier: 3, reason: "", because: "", axis_reason: "", optional: false, premise: [],
        at_run: { facts: [{ fact: "genome_length", source: "measured", said: "", measured_by: measure.contract_id }],
                  rule: "r", rows: [], fallback: null, fallback_is: "stop", fallback_reason: "" } }] };
    mount(<LivingCanvas graph={{ nodes: [{ id: "measure_len", contract_id: measure.contract_id, params: [] },
                                         { id: "star_index", contract_id: index.contract_id, params: [] }], edges: [] }}
                        positions={{ measure_len: { x: 224, y: 0 }, star_index: { x: 0, y: 200 } }}
                        steps={{ measure_len: measure, star_index: index } as unknown as Record<string, Step>}
                        authors={{}} selected={null} onSelect={vi.fn()} />);
    const link = screen.getByTestId("fact-link-measure_len-star_index");
    expect(link.querySelector("path")!.getAttribute("stroke-dasharray")).toBeTruthy();
    expect(within(link).getByText("genome_length → sa_index_nbases")).toBeInTheDocument();
    // Out of the measuring step's side, into the decided step's top: never through a step.
    const d = link.querySelector("path")!.getAttribute("d")!;
    expect(d).toMatch(/^M 369 /);
    expect(d).toMatch(/V 200$/);
  });
});

describe("fitting what the agent built (issue 532)", () => {
  it("fits the drawing once steps arrive on a canvas nobody has moved", async () => {
    const rect = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      { x: 0, y: 0, left: 0, top: 0, right: 600, bottom: 500, width: 600, height: 500, toJSON: () => ({}) } as DOMRect);
    const empty = { nodes: [], edges: [] };
    const client = new QueryClient();
    const draw = (graph: typeof empty | typeof FAKE_SESSION.graph) => (
      <QueryClientProvider client={client}>
        <div data-testid="canvas">
          <LivingCanvas graph={graph} positions={FAKE_SESSION.placement} steps={FAKE_STEPS}
                        authors={{}} selected={null} onSelect={vi.fn()} />
        </div>
      </QueryClientProvider>);
    const { rerender, container } = render(draw(empty));
    rerender(draw(FAKE_SESSION.graph));
    await act(async () => { await new Promise((done) => setTimeout(done, 50)); });
    const world = container.querySelector<HTMLElement>("[style*='scale(']")!;
    // The view starts at (250, 20) at 1:1; fitted, it has moved.
    expect(world.style.transform).not.toBe("translate(250px, 20px) scale(1)");
    rect.mockRestore();
  });
});

describe("a lit path (Run → Outputs)", () => {
  it("keeps the lit steps and the wires between them, and fades the rest", () => {
    fake({ lit: ["trimgalore", "star_align"] });
    expect(screen.getByTestId("living-node-trimgalore").className).not.toContain("opacity-40");
    expect(screen.getByTestId("living-node-samtools_sort").className).toContain("opacity-40");
    expect(screen.getByTestId("wire-trimgalore-star_align").closest("g[data-lit]")?.getAttribute("data-lit")).toBe("true");
    expect(screen.getByTestId("wire-star_align-samtools_sort").closest("g[data-lit]")?.getAttribute("data-lit")).toBe("false");
  });

  it("lights everything when nothing is lit", () => {
    fake();
    expect(screen.getByTestId("living-node-samtools_sort").className).not.toContain("opacity-40");
  });
});

describe("inputs and results are cards of their own", () => {
  it("drags an input on its own, and its wire follows (walk 2026-11-17)", () => {
    fake();
    const reads = screen.getByTestId("living-source-reads");
    const left = parseFloat(reads.style.left), top = parseFloat(reads.style.top);
    fireEvent.pointerDown(reads, { clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(reads, { clientX: 70, clientY: 40, pointerId: 1 });
    fireEvent.pointerUp(reads, { pointerId: 1 });
    expect(parseFloat(screen.getByTestId("living-source-reads").style.left)).toBe(left + 60);
    expect(parseFloat(screen.getByTestId("living-source-reads").style.top)).toBe(top + 30);
  });

  it("drags a result on its own", () => {
    fake();
    const [result] = screen.getAllByTestId(/^living-result-/);
    const left = parseFloat(result.style.left);
    fireEvent.pointerDown(result, { clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(result, { clientX: 50, clientY: 10, pointerId: 1 });
    fireEvent.pointerUp(result, { pointerId: 1 });
    expect(parseFloat(screen.getByTestId(result.dataset.testid!).style.left)).toBe(left + 40);
  });
});

describe("the canvas keeps its gestures to itself (walk 2026-11-17)", () => {
  it("a wheel over the canvas zooms it and never scrolls the page", () => {
    fake();
    expect(fireEvent.wheel(screen.getByTestId("canvas"), { deltaY: 40 })).toBe(false);
  });

  it("dragging an input or a result does not pan the canvas", () => {
    fake();
    const frame = screen.getByTestId("canvas").querySelector<HTMLElement>("[style*='translate']")!;
    const before = frame.style.transform;
    const [result] = screen.getAllByTestId(/^living-result-/);
    fireEvent.pointerDown(result, { clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(window, { clientX: 80, clientY: 10, pointerId: 1 });
    fireEvent.pointerUp(window, { pointerId: 1 });
    expect(frame.style.transform).toBe(before);
  });

  it("a lit path carries pulses along its wires, and only there", () => {
    fake({ lit: ["trimgalore", "star_align"] });
    const lit = screen.getByTestId("wire-trimgalore-star_align");
    expect(lit.querySelectorAll("[data-pulse]").length).toBeGreaterThan(0);
    expect(screen.getByTestId("wire-star_align-samtools_sort").querySelectorAll("[data-pulse]").length).toBe(0);
  });
});

it("pulses move at one speed on every wire, and are as far apart (walk 2026-11-17)", async () => {
  // A fixed duration made long wires faster than short ones, which read as meaning something.
  const { Pulses } = await import("./CollectionChannel");
  const speed = (d: string) => {
    const { container, unmount } = render(<svg><Pulses d={d} length={Number(d.split(" ").pop())} /></svg>);
    const dots = within(container).getAllByTestId("pulse-dot");
    const seconds = parseFloat(dots[0].querySelector("animateMotion")!.getAttribute("dur")!);
    const out = { perSecond: Number(d.split(" ").pop()) / seconds, gap: Number(d.split(" ").pop()) / dots.length };
    unmount();
    return out;
  };
  const short = speed("M0 0 H 120"), long = speed("M0 0 H 600");
  expect(short.perSecond).toBeCloseTo(long.perSecond, 5);
  expect(Math.abs(long.gap - short.gap) / short.gap).toBeLessThan(0.2);
});
