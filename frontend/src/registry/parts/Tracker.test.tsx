import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { Tracker } from "./Tracker";

it("marks the current piece and lets a person move to any piece", () => {
  const onPick = vi.fn();
  render(<Tracker current="contract" onPick={onPick} pieces={[
    { name: "questions", state: "done", note: "approved" },
    { name: "contract", state: "now", note: "1 waiting for you" },
    { name: "parameters", state: "later", note: "not started" },
  ]} />);
  const current = screen.getByRole("button", { name: /contract/ });
  expect(current.getAttribute("aria-current")).toBe("step");
  expect(screen.getByRole("button", { name: /questions/ }).getAttribute("aria-current")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /parameters/ }));
  expect(onPick).toHaveBeenCalledWith("parameters");
});
