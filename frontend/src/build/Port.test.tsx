import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Port } from "./Port";

const out = { name: "bam", type_id: "alignment.bam", side: "out" as const, met: true, states: [] };
const inp = { name: "bam", type_id: "alignment.bam", side: "in" as const, met: false, states: [] };

describe("drag-to-connect", () => {
  it("an output starts a wire and an input does not", () => {
    // Direction is the port's, not the gesture's. That is what makes MD0502 — a wire running
    // backwards — unreachable from the canvas rather than merely reported by it.
    const start = vi.fn();
    const { rerender } = render(<Port port={out} side={out.side} y={56} onStartWire={start} />);
    fireEvent.pointerDown(screen.getByTestId("port"));
    expect(start).toHaveBeenCalledTimes(1);

    start.mockClear();
    rerender(<Port port={inp} side={inp.side} y={56} onStartWire={start} />);
    fireEvent.pointerDown(screen.getByTestId("port"));
    expect(start).not.toHaveBeenCalled();
  });

  it("an input finishes a wire and an output does not", () => {
    const finish = vi.fn();
    const { rerender } = render(<Port port={inp} side={inp.side} y={56} onFinishWire={finish} />);
    fireEvent.pointerUp(screen.getByTestId("port"));
    expect(finish).toHaveBeenCalledTimes(1);

    finish.mockClear();
    rerender(<Port port={out} side={out.side} y={56} onFinishWire={finish} />);
    fireEvent.pointerUp(screen.getByTestId("port"));
    expect(finish).not.toHaveBeenCalled();
  });

  it("carries the verdict so a refactor cannot silently drop the colour", () => {
    // jsdom has no layout engine and no computed palette, so asserting the class string is
    // worth what testing CSS is worth. The attribute names the failure instead.
    render(<Port port={inp} side={inp.side} y={56} verdict="no" />);
    expect(screen.getByTestId("port")).toHaveAttribute("data-verdict", "no");
  });

  it("says nothing about a verdict when nobody is dragging", () => {
    render(<Port port={inp} side={inp.side} y={56} />);
    expect(screen.getByTestId("port")).toHaveAttribute("data-verdict", "");
  });

  it("still says what it is on hover", () => {
    render(<Port port={inp} side={inp.side} y={56} />);
    fireEvent.mouseEnter(screen.getByTestId("port"));
    expect(screen.getByTestId("port-label")).toHaveTextContent("alignment.bam");
    expect(screen.getByTestId("port-label")).toHaveTextContent("nothing feeds this");
  });
});

describe("click a port, get what fits", () => {
  it("a press that does not travel asks what could go here", () => {
    // **`n-bport` says CLICK an output.** It needed a double click, on a 7px square — which is
    // why the operator's verdict was that the feature does not exist. It was not missing:
    // `Picker` and `GET /pipeline/candidates` have shipped since phase 3b, bound to a gesture
    // nobody would find.
    const explore = vi.fn();
    render(<Port port={out} side={out.side} y={56} onExplore={explore} />);
    const port = screen.getByTestId("port");

    fireEvent.pointerDown(port, { clientX: 100, clientY: 100 });
    fireEvent.pointerUp(port, { clientX: 100, clientY: 100 });
    expect(explore).toHaveBeenCalledTimes(1);
  });

  it("a press that travels draws a wire instead", () => {
    // The other half, and the reason the double click was chosen in the first place: an output
    // has to do both, and a click that also ended a wire would open the popover every time
    // somebody let go of one.
    const explore = vi.fn();
    const finish = vi.fn();
    render(<Port port={inp} side={inp.side} y={56} onExplore={explore} onFinishWire={finish} />);
    const port = screen.getByTestId("port");

    fireEvent.pointerDown(port, { clientX: 100, clientY: 100 });
    fireEvent.pointerUp(port, { clientX: 160, clientY: 220 });
    expect(explore).not.toHaveBeenCalled();
    expect(finish).toHaveBeenCalledTimes(1);
  });

  it("is reachable without a pointer at all", () => {
    // The 2026-08-29 walk found the module palette absent from the accessibility tree, so drag
    // and double-click were the only two ways to add a step. A port is a real button with a
    // label, so it is tab-reachable and announced.
    render(<Port port={out} side={out.side} y={56} onExplore={vi.fn()} />);
    const port = screen.getByTestId("port");
    expect(port.tagName).toBe("BUTTON");
    expect(port.getAttribute("aria-label")).toMatch(/Output bam: alignment\.bam/);
  });
});
