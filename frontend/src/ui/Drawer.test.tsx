import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";

import { Drawer } from "./Drawer";

function Opener() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Assistant</button>
      <Drawer open={open} onClose={() => setOpen(false)} label="Assistant"><input aria-label="Message" /></Drawer>
    </>
  );
}

it("drawer closes on Escape and returns focus", () => {
  render(<Opener />);
  const opener = screen.getByRole("button", { name: "Assistant" });
  opener.focus();
  fireEvent.click(opener);
  const dialog = screen.getByRole("dialog", { name: "Assistant" });
  expect(dialog.contains(document.activeElement)).toBe(true);
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(opener);
});
