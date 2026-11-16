import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";

import { Tabs } from "./Tabs";

function Two() {
  const [value, setValue] = useState("step");
  return <Tabs label="Panel" value={value} onChange={setValue}
               tabs={[{ id: "step", label: "Step" }, { id: "assistant", label: "Assistant" }]} />;
}

it("tabs move with arrow keys", () => {
  render(<Two />);
  const step = screen.getByRole("tab", { name: "Step" });
  expect(step.getAttribute("aria-selected")).toBe("true");
  fireEvent.keyDown(step, { key: "ArrowRight" });
  const assistant = screen.getByRole("tab", { name: "Assistant" });
  expect(assistant.getAttribute("aria-selected")).toBe("true");
  expect(document.activeElement).toBe(assistant);
  fireEvent.keyDown(assistant, { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: "Step" }).getAttribute("aria-selected")).toBe("true");
});

it("Home and End go to the first and last tab", () => {
  render(<Two />);
  fireEvent.keyDown(screen.getByRole("tab", { name: "Step" }), { key: "End" });
  expect(screen.getByRole("tab", { name: "Assistant" }).getAttribute("aria-selected")).toBe("true");
  fireEvent.keyDown(screen.getByRole("tab", { name: "Assistant" }), { key: "Home" });
  expect(screen.getByRole("tab", { name: "Step" }).getAttribute("aria-selected")).toBe("true");
});
