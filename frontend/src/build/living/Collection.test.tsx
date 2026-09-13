import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { authoringReducer, EVENT_CAP, initialAuthoring } from "./authoringReducer";
import { flowLabel, flowTag, multiplicity } from "./CollectionChannel";
import { COLLECT_CHANNELS, COLLECT_SESSION, COLLECT_STEPS, FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LivingCanvas } from "./LivingCanvas";
import { MOTION, motionFor, wireSubject } from "./motion";

/** Task 11: the collection grammar and the motion policy. **What jsdom cannot see is pixels** —
 *  the side-by-side renders are the record of how these look. These hold which shape is chosen,
 *  from which server fact, and which event class goes on which object. */

const mount = (ui: React.ReactElement) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

function collect(extra: Partial<React.ComponentProps<typeof LivingCanvas>> = {}) {
  return mount(
    <LivingCanvas graph={COLLECT_SESSION.graph} ghost={null} positions={COLLECT_SESSION.placement}
                  steps={COLLECT_STEPS} channels={COLLECT_CHANNELS} authors={{}} selected={null}
                  onSelect={vi.fn()} {...extra} />,
  );
}

describe("the three collection shapes", () => {
  it("draws a run-scoped input as one stroke, a per-item input as a ribbon, a gather as a convergence", () => {
    collect();
    expect(screen.getByTestId("flow-reference-star_align")).toHaveAttribute("data-flow", "one");
    expect(screen.getByTestId("flow-reads-trimgalore")).toHaveAttribute("data-flow", "many");
    expect(screen.getByTestId("wire-fastqc-multiqc")).toHaveAttribute("data-flow", "gather");
  });

  it("draws three strands for a ribbon whatever the count is, and one for a value", () => {
    collect();
    expect(screen.getByTestId("flow-reads-trimgalore").querySelectorAll("path")).toHaveLength(3);
    expect(screen.getByTestId("flow-reference-star_align").querySelectorAll("path")).toHaveLength(1);
  });

  it("chooses the shape from server facts — a gathering port and how a step runs — not from type names", () => {
    const renamed = {
      ...COLLECT_STEPS,
      multiqc: { ...COLLECT_STEPS.multiqc, ports: COLLECT_STEPS.multiqc.ports.map((p) => ({ ...p, gathers: false })) },
    };
    collect({ steps: renamed });
    expect(screen.getByTestId("wire-fastqc-multiqc")).toHaveAttribute("data-flow", "many");
  });

  it("marks a gathering port wide and a per-item step's ports tall", () => {
    collect();
    const multiqc = screen.getByTestId("living-node-multiqc");
    expect(multiqc.querySelector('[data-port-mark="gather"]')).not.toBeNull();
    expect(screen.getByTestId("living-node-trimgalore").querySelector('[data-port-mark="many"]')).not.toBeNull();
  });

  it("says how many only where a measurement said so, and never on the wire", () => {
    expect(multiplicity(12)).toBe("×12 samples");
    expect(multiplicity(null)).toBe("×N items");
    expect(flowTag("many")).toBe("once per item");
    expect(flowTag("gather")).toBe("collect all");
    expect(flowLabel("many", null)).toBe("×N items · once per item");
    collect();
    expect(screen.getByTestId("living-source-reads")).toHaveTextContent("×12 samples");
    expect(screen.getByTestId("living-source-reference")).not.toHaveTextContent("×");
  });

  it("says each step runs once or per item, from the server's answer", () => {
    collect();
    expect(screen.getByTestId("living-node-fastqc")).toHaveTextContent("runs 12×");
    expect(screen.getByTestId("living-node-multiqc")).toHaveTextContent("runs once");
  });

  it("draws an input beside the step it feeds when the gutter is empty, not below it", () => {
    collect();
    const source = screen.getByTestId("living-source-reference");
    const step = COLLECT_SESSION.placement.star_align;
    expect(parseFloat(source.style.left)).toBeLessThan(step.x);
    expect(parseFloat(source.style.top)).toBeLessThan(step.y + 112);
  });

  it("carries no filename anywhere it draws", () => {
    const { container } = collect();
    expect(container.textContent).not.toMatch(/\.(?:fastq|fq|bam|fa|fasta|gtf)(?:\.gz)?\b(?!\.)/i);
  });
});

describe("motion follows domain events", () => {
  it("maps each event to one class, and draws nothing for a rejection", () => {
    expect(MOTION.proposal_shown).toBe("living-pop");
    expect(MOTION.proposal_accepted).toBe("living-settle");
    expect(MOTION.edge_committed).toBe("living-draw");
    expect(MOTION.proposal_rejected).toBeNull();
  });

  it("puts the settle class on the accepted step and the draw class on its wire, in event order", () => {
    const proposal = FAKE_SESSION.pending_proposal!;
    let state = authoringReducer({ ...initialAuthoring }, { type: "snapshot", session: FAKE_SESSION });
    state = authoringReducer(state, { type: "accept", proposal, option: "keep", expectedRevision: 4 });
    expect(state.events.map((e) => e.kind)).toEqual(["proposal_shown", "proposal_accepted", "edge_committed"]);

    const edge = proposal.edges[0];
    expect(motionFor(state.events, ["edge_committed"], wireSubject(edge))?.className).toBe("living-draw");
    expect(motionFor(state.events, ["proposal_accepted"], "samtools_sort")?.className).toBe("living-settle");
    expect(motionFor(state.events, ["proposal_accepted"], "star_align")).toBeNull();
  });

  it("pops the ghost for its proposal and reports the event played when the animation ends", () => {
    const state = authoringReducer({ ...initialAuthoring }, { type: "snapshot", session: FAKE_SESSION });
    const onPlayed = vi.fn();
    mount(
      <LivingCanvas graph={FAKE_SESSION.graph} ghost="samtools_sort" ghostProposal="p-sort"
                    positions={FAKE_SESSION.placement} steps={FAKE_STEPS} channels={FAKE_CHANNELS}
                    authors={{}} selected={null} onSelect={vi.fn()} events={state.events} onPlayed={onPlayed} />,
    );
    const ghost = screen.getByTestId("living-node-samtools_sort");
    expect(ghost).toHaveClass("living-pop");
    fireEvent.animationEnd(ghost);
    expect(onPlayed).toHaveBeenCalledWith(state.events[0]);
  });

  it("keeps a bounded queue, because under reduced motion no animation ever ends", () => {
    let state = { ...initialAuthoring };
    for (let i = 0; i < EVENT_CAP + 25; i += 1) {
      state = authoringReducer(state, { type: "reject", proposalId: `p${i}` });
    }
    expect(state.events).toHaveLength(EVENT_CAP);
    expect(state.events.at(-1)?.subject).toBe(`p${EVENT_CAP + 24}`);
  });
});

describe("a position the person chose", () => {
  it("moves with a drag, and Tidy gives the server's layout back", () => {
    collect();
    const node = screen.getByTestId("living-node-fastqc");
    const before = node.style.left;
    fireEvent.pointerDown(node, { clientX: 10, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(node, { clientX: 70, clientY: 40, pointerId: 1 });
    fireEvent.pointerUp(node, { pointerId: 1 });
    expect(node.style.left).not.toBe(before);

    fireEvent.click(screen.getByTestId("tidy"));
    expect(screen.getByTestId("living-node-fastqc").style.left).toBe(before);
    expect(screen.queryByTestId("tidy")).toBeNull();
  });
});
