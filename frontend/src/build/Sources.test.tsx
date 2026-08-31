import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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
      // Nothing consumes it, so it is what the pipeline is FOR — spec §4.1.
      { name: "bam", type_id: "alignment.bam", side: "out", met: true, states: ["sorted"] },
    ],
  }],
  // **The server's answer, one entry per CHANNEL** — spec §12.3. It used to be derived here
  // from unwired ports, which is what put five sockets above one `params.gtf` (§0).
  channels: [
    { name: "reads", param: "input", type_id: "fastq.reads", states: [],
      ports: ["trimgalore.reads"] },
  ],
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

  it("renders nothing at all when the pipeline neither needs nor produces anything", () => {
    // Absence is absence. A closed graph gets no empty column on either side.
    //
    // **This fixture had to get stricter when outputs arrived**, and that is the test doing its
    // job. It used to be a lone step with one unwired OUTPUT port, which was "needs nothing" and
    // is now "produces exactly one thing" — so a version of it that still passed would have been
    // a version where `terminals` drew nothing.
    const closed = {
      ...DATA,
      steps: [
        // Only the out port, which `align` consumes.
        { ...DATA.steps[0], ports: [DATA.steps[0].ports[1]] },
        // Both ins covered — one wired, one unmet — and no outs at all.
        { ...DATA.steps[1], ports: DATA.steps[1].ports.slice(0, 2) },
      ],
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

/** Spec §4.1. `goal_of` has computed `want` since Plan 3E and **the canvas drew none of it** —
 *  a terminal `counts.matrix` was an unwired port with nothing saying it was the point. */
describe("what the pipeline is for", () => {
  it("draws an output for a port nothing consumes, and only for that", () => {
    // Two out ports on the canvas: `trimgalore.reads` feeds `align`, so it is a step in the
    // middle of a pipeline; `align.bam` feeds nothing, so it is the pipeline's product.
    render(<Sources data={DATA as never} offsets={{}} />);
    const outs = screen.getAllByTestId("terminal");
    expect(outs.length).toBe(1);
    expect(outs[0].textContent).toContain("bam");
    expect(outs[0].textContent).toContain("alignment.bam");
    expect(outs[0].textContent).toContain("Output");
  });

  it("draws one per terminal port where there are several", () => {
    // **The operator asked for this in these words** — *"there can be multiple outputs"* — and
    // `want` has always been a list. A single-output canvas over a multi-output goal is the
    // interface asserting something the artifact does not say.
    const forked = {
      ...DATA,
      steps: [DATA.steps[0], {
        ...DATA.steps[1],
        ports: [...DATA.steps[1].ports, {
          name: "log", type_id: "qc.report", side: "out", met: true, states: [],
        }],
      }],
    };
    render(<Sources data={forked as never} offsets={{}} />);
    expect(screen.getAllByTestId("terminal").length).toBe(2);
  });

  it("sits in the gutter to the RIGHT, which the last rank has by construction", () => {
    // The mirror of the input gutter, and the same arithmetic — `place`. A socket needs
    // `SOCKET_W + GAP` = 240px of clear space and a rank is `RANK_PITCH` = 224px wide, so the
    // space beside a node that is not at the end is already occupied by the node it feeds.
    const { container } = render(<Sources data={DATA as never} offsets={{}} />);
    const box = container
      .querySelector('[data-testid="terminal"] > div:last-child') as HTMLElement;
    // `align` is at rank 1, which is the last: x + NODE_W + GAP.
    expect(parseInt(box.style.left, 10)).toBe(360 + 172 + 90);
  });

  it("carries a TYPE and offers nothing to type into", () => {
    // Invariant 15 reaches both sides. An output socket is as un-bindable as an input one:
    // where the results are written is `params.outdir`, a SITE fact Wiener supplies, and it is
    // no more a pipeline's business than where the reads came from.
    const { container } = render(<Sources data={DATA as never} offsets={{}} />);
    const out = container.querySelector('[data-testid="terminal"]') as HTMLElement;
    expect(out.querySelectorAll("input, textarea, select").length).toBe(0);
    expect(out.textContent).not.toMatch(/\//);
  });
});

/** Spec §5, the visible half. What a person types is a **label**: the channel name, the param,
 *  the samplesheet column and the Nextflow variable are all derived and this reaches none of
 *  them. `tests/test_draft_labels.py` is what holds that; these hold that it is reachable. */
describe("naming a socket on the canvas", () => {
  it("renames an input in place, and reports the socket it renamed", () => {
    const renamed = vi.fn();
    render(<Sources data={DATA as never} offsets={{}} onRename={renamed} />);
    const field = screen.getByLabelText("name for reads");
    fireEvent.change(field, { target: { value: "liver reads" } });
    // **The CHANNEL's name, not `<node>.<port>`** — and that changed in phase 2.5.
    //
    // An input socket is a channel now, and a channel may feed three ports. Keying its label on
    // a port would give one socket three competing labels and no rule for which wins; keying it
    // on the channel is one label for the thing a person is actually naming. An OUTPUT keeps
    // `<node>.<port>`, because `Goal.want` gives an output no identity of its own yet.
    expect(renamed).toHaveBeenCalledWith("reads", "liver reads");
  });

  it("renames an output too", () => {
    // **Both, and the plan says both in those words.** An output you cannot name is half a
    // feature on the screen where the operator asked for multiple outputs.
    const renamed = vi.fn();
    render(<Sources data={DATA as never} offsets={{}} onRename={renamed} />);
    fireEvent.change(screen.getByLabelText("name for bam"), { target: { value: "liver bam" } });
    expect(renamed).toHaveBeenCalledWith("align.bam", "liver bam");
  });

  it("shows the port's own name as a placeholder rather than as a value", () => {
    // An unnamed socket reads as its port, and the field is empty — so a person who types
    // replaces nothing, and one who clears it gets the derived name back rather than a blank
    // box. Storing the port name as a value would make "never touched" indistinguishable from
    // "named it after itself".
    render(<Sources data={DATA as never} offsets={{}} onRename={vi.fn()} />);
    const field = screen.getByLabelText("name for reads") as HTMLInputElement;
    expect(field.value).toBe("");
    expect(field.placeholder).toBe("reads");
  });

  it("shows the label where there is one, and still shows the type", () => {
    // The type is what the socket is; the label is what this pipeline calls it. Replacing the
    // type with a person's words is how a screen comes to assert something the artifact cannot
    // back up — spec §0.1, and the reason the label sits above the type rather than over it.
    render(
      <Sources
        data={DATA as never}
        offsets={{}}
        labels={{ reads: "liver reads" }}
        onRename={vi.fn()}
      />,
    );
    expect((screen.getByLabelText("name for reads") as HTMLInputElement).value)
      .toBe("liver reads");
    expect(screen.getAllByTestId("source")[0].textContent).toContain("fastq.reads");
  });

  it("offers no field at all where the canvas is read-only", () => {
    // The run graph draws the same sockets and renames none — `onRename` omitted is the whole
    // of that, so a read-only canvas cannot grow an editable field by accident.
    const { container } = render(<Sources data={DATA as never} offsets={{}} />);
    expect(container.querySelectorAll("input").length).toBe(0);
  });
});


/** Spec §4 on the canvas: the operator's *"multiple of the same type"*, as a control. */
describe("splitting a channel on the canvas", () => {
  const SHARED = {
    ...DATA,
    channels: [
      { name: "gtf", param: "gtf", type_id: "annotation.gtf", states: [],
        ports: ["trimgalore.reads", "align.index"] },
      // A channel feeding exactly one port, so the negative half of the test has a subject.
      { name: "fasta", param: "fasta", type_id: "genome.fasta", states: [],
        ports: ["align.reads"] },
    ],
  };

  it("offers split per port, and only where a channel feeds more than one", () => {
    // A channel feeding one port has nothing to split off. Offering the control there would be
    // a button that either does nothing or silently means something else.
    const split = vi.fn();
    render(<Sources data={SHARED as never} offsets={{}} onSplit={split} />);
    fireEvent.click(screen.getByLabelText("give align.index its own channel"));
    expect(split).toHaveBeenCalledWith("align.index");
    // `fasta` feeds one port. Offering the control there would be a button that either does
    // nothing or silently means something else.
    expect(screen.queryByLabelText("give align.reads its own channel")).toBeNull();
  });

  it("offers merge on a channel a person split, and not on a type's default", () => {
    // The same control in reverse, and the distinction it rests on is not derivable from the
    // server's answer: `channels` says what the grouping IS, `declared` says whose decision it
    // was. A default single-port channel must not offer to merge into nothing.
    const merge = vi.fn();
    const one = {
      ...DATA,
      channels: [
        { name: "gtf_2", param: "gtf_2", type_id: "annotation.gtf", states: [],
          ports: ["align.index"] },
      ],
    };
    const { rerender } = render(
      <Sources data={one as never} offsets={{}} declared={["align.index"]}
               onMerge={merge} />,
    );
    fireEvent.click(screen.getByLabelText("put align.index back on the shared channel"));
    expect(merge).toHaveBeenCalledWith("align.index");

    rerender(<Sources data={one as never} offsets={{}} declared={[]} onMerge={merge} />);
    expect(
      screen.queryByLabelText("put align.index back on the shared channel"),
    ).toBeNull();
  });

  it("offers neither where the canvas is read-only", () => {
    render(<Sources data={SHARED as never} offsets={{}} />);
    expect(screen.queryByLabelText("give align.index its own channel")).toBeNull();
  });
});
