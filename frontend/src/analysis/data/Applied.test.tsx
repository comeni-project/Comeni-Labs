import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { Applied } from "./Applied";
import { analysis } from "./fixtures";

it("every fix is listed with whose it is and why, and the AI's can be kept or undone", () => {
  const keep = vi.fn();
  const undo = vi.fn();
  render(<Applied data={analysis({ fixes: [
    { kind: "use_file", sample: "Y4_R1", file: "Y4_2.fq.gz", measurement: null, by: "ai", reason: "same stem" },
    { kind: "leave_out", sample: "Y3", file: null, measurement: null, by: "you", reason: null },
  ] })} onKeep={keep} onUndo={undo} />);
  expect(screen.getByText("Y4_2.fq.gz used as Y4_R1's mate")).toBeTruthy();
  expect(screen.getByText("same stem")).toBeTruthy();
  expect(screen.getByText("AI")).toBeTruthy();
  expect(screen.getByText("YOU")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Keep: Y4_2.fq.gz used as Y4_R1's mate" }));
  expect(keep).toHaveBeenCalledWith(0);
  fireEvent.click(screen.getByRole("button", { name: "Undo: Y3 left out" }));
  expect(undo).toHaveBeenCalledWith(1);
  expect(screen.queryByRole("button", { name: "Keep: Y3 left out" })).toBeNull();
});

it("nothing applied, nothing shown", () => {
  const { container } = render(<Applied data={analysis({ fixes: [] })} onKeep={vi.fn()} onUndo={vi.fn()} />);
  expect(container.textContent).toBe("");
});
