import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sources } from "./Sources";

/** What the pipeline needs from you, drawn as typed sockets. `impl-inv` — invariant 15 decides
 *  this design: a source node carries a TYPE and never a path. */

const DATA = {
  steps: [{
    id: "trimgalore", process: "TRIMGALORE", contract_id: "nf-core/trimgalore@0.6.10",
    tier: 2, reason: "", settings: [],
    ports: [
      // Met, and nothing wires it — so it is fed from outside.
      { name: "reads", type_id: "fastq.reads", side: "in", met: true, states: [] },
      { name: "reads", type_id: "fastq.reads", side: "out", met: true, states: ["trimmed"] },
    ],
  }, {
    id: "align", process: "STAR_ALIGN", contract_id: "nf-core/star/align@1.11.0",
    tier: 3, reason: "", settings: [],
    ports: [
      // Met by a wire from trimgalore — it has a source on the canvas already.
      { name: "reads", type_id: "fastq.reads", side: "in", met: true, states: ["trimmed"] },
      // Unmet — that is the hollow port's job to say, not a socket's.
      { name: "index", type_id: "genome.index.star", side: "in", met: false, states: [] },
    ],
  }],
  layout: {
    nodes: [
      { id: "trimgalore", rank: 0, order: 0, x: 40, y: 60, width: 232, height: 78, tier: 2 },
      { id: "align", rank: 1, order: 0, x: 360, y: 60, width: 232, height: 78, tier: 3 },
    ],
    wires: [{
      from_node: "trimgalore", from_port: "reads", to_node: "align", to_port: "reads",
      type_id: "fastq.reads", points: [], label_at: { x: 0, y: 0 },
    }],
    width: 600, height: 200,
  },
  provenance: {}, settled_share: 1, needs_review: [],
};

describe("what the pipeline needs from you", () => {
  it("draws a socket for an input fed from outside, and only for that", () => {
    // Three inputs, one socket: one is wired from another step, one is unmet (the hollow port
    // says so), and one is genuinely an entry channel.
    render(<Sources data={DATA as never} offsets={{}} />);
    const sockets = screen.getAllByTestId("source");
    expect(sockets.length).toBe(1);
    expect(sockets[0].textContent).toContain("reads");
    expect(sockets[0].textContent).toContain("fastq.reads");
  });

  it("carries a TYPE and offers nothing to type into", () => {
    // **The invariant, drawn.** `impl-inv`: *no input accepts a sample identifier, filename or
    // path; the `Goal` holds a SHAPE.* The socket is deliberately not editable — there is
    // nothing to put in it, which is the design saying that out loud. The binding happens at
    // the RUN, which is Wiener's and is `Submit.tsx`'s.
    const { container } = render(<Sources data={DATA as never} offsets={{}} />);
    expect(container.querySelectorAll("input, textarea, select").length).toBe(0);
    expect(container.textContent).not.toMatch(/\//);
  });

  it("renders nothing at all when the pipeline needs nothing", () => {
    // Absence is absence. A pipeline with no entry channels gets no empty column.
    const closed = {
      ...DATA,
      steps: [{ ...DATA.steps[0], ports: [DATA.steps[0].ports[1]] }],
      layout: { ...DATA.layout, nodes: [DATA.layout.nodes[0]], wires: [] },
    };
    const { container } = render(<Sources data={closed as never} offsets={{}} />);
    expect(container.innerHTML).toBe("");
  });

  it("follows a node that has been dragged", () => {
    // The socket is placed relative to its consumer, so moving the consumer moves it. Reading
    // the layout instead would leave it behind the moment anybody rearranged the canvas.
    const { container } = render(
      <Sources data={DATA as never} offsets={{ trimgalore: { x: 500, y: 300 } }} />,
    );
    const box = container.querySelector('[data-testid="source"] > div:last-child') as HTMLElement;
    expect(parseInt(box.style.left, 10)).toBe(500 - 150 - 90);
  });
});
