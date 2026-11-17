import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { Segmented } from "./Segmented";

it("segmented marks the pressed option", () => {
  const onChange = vi.fn();
  render(<Segmented label="View" value="graph" onChange={onChange}
                    options={[{ id: "graph", label: "Graph" }, { id: "timeline", label: "Timeline" }]} />);
  expect(screen.getByRole("group", { name: "View" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Graph" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.getByRole("button", { name: "Timeline" }).getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(screen.getByRole("button", { name: "Timeline" }));
  expect(onChange).toHaveBeenCalledWith("timeline");
});
