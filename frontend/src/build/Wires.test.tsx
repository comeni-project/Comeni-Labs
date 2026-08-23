import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Wires } from "./Wires";

const wire = {
  from_node: "align",
  from_port: "bam",
  to_node: "sort",
  to_port: "bam",
  type_id: "alignment.bam",
  points: [
    { x: 90, y: 64 },
    { x: 90, y: 96 },
    { x: 90, y: 128 },
  ],
  label_at: { x: 90, y: 90 },
};

const props = {
  wires: [wire],
  tierOf: () => 2,
  at: { align: { x: 0, y: 0 }, sort: { x: 0, y: 128 } },
  ports: {
    align: { ins: [], outs: ["bam"], width: 232 },
    sort: { ins: ["bam"], outs: ["bam"], width: 232 },
  },
  width: 400,
  height: 400,
};

describe("detaching a wire", () => {
  it("calls back with the four names the graph keys on", () => {
    const detach = vi.fn();
    render(<Wires {...props} onDetach={detach} />);
    fireEvent.click(screen.getByTestId("wire-hit"));
    expect(detach).toHaveBeenCalledWith({
      from_node: "align",
      from_port: "bam",
      to_node: "sort",
      to_port: "bam",
    });
  });

  it("gives the wire a hit target a hand can actually hit", () => {
    // A 1.5px stroke is a 1.5px hit target. The operator could not detach anything, and this
    // is half of why. jsdom cannot tell us it is clickable, so the width is asserted directly.
    render(<Wires {...props} onDetach={() => {}} />);
    expect(screen.getByTestId("wire-hit")).toHaveAttribute("stroke-width", "14");
  });

  it("says what clicking will do", () => {
    render(<Wires {...props} onDetach={() => {}} />);
    expect(screen.getByTestId("wire-hit").querySelector("title")?.textContent).toContain(
      "click to detach",
    );
  });

  it("offers no hit target at all where the canvas is read-only", () => {
    // A control that does nothing is worse than one plainly not offered — Plan 3C's own rule,
    // recorded when it removed the fake crosshair.
    render(<Wires {...props} />);
    expect(screen.queryByTestId("wire-hit")).toBeNull();
    expect(screen.getByTestId("wire")).toBeInTheDocument();
  });
});

describe("the wire you are dragging", () => {
  it("is drawn to the cursor, because there is no port yet", () => {
    // Without it a wire drag is an invisible gesture: you press on a port, move, and nothing
    // on the screen says anything is happening until you land.
    render(
      <Wires {...props} pending={{ from: { x: 90, y: 64 }, to: { x: 300, y: 240 } }} />,
    );
    const ghost = screen.getByTestId("pending-wire");
    expect(ghost.getAttribute("d")).toContain("M90,64");
    expect(ghost.getAttribute("d")).toContain("300");
  });

  it("reads as undecided, because it is not a wire until it is dropped and checked", () => {
    render(
      <Wires {...props} pending={{ from: { x: 0, y: 0 }, to: { x: 10, y: 10 } }} />,
    );
    expect(screen.getByTestId("pending-wire")).toHaveAttribute("stroke-dasharray", "4 4");
  });

  it("is absent when nothing is being dragged", () => {
    render(<Wires {...props} />);
    expect(screen.queryByTestId("pending-wire")).toBeNull();
  });

  it("never eats a pointer event", () => {
    // It follows the cursor, so anything it swallowed would be swallowed exactly where you are
    // about to drop.
    render(<Wires {...props} pending={{ from: { x: 0, y: 0 }, to: { x: 10, y: 10 } }} />);
    expect(screen.getByTestId("pending-wire")).toHaveAttribute("pointer-events", "none");
  });
});
