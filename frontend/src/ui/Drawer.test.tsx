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

it("keeps focus where the person is typing when the page re-renders with a new onClose", () => {
  function Live() {
    const [open, setOpen] = useState(true);
    const [tick, setTick] = useState(0);
    return (
      <>
        <button type="button" onClick={() => setTick(tick + 1)}>render {tick}</button>
        <Drawer open={open} onClose={() => setOpen(false)} label="Assistant">
          <button type="button">first</button>
          <input aria-label="Message" />
        </Drawer>
      </>
    );
  }
  render(<Live />);
  const message = screen.getByRole("textbox", { name: "Message" });
  message.focus();
  fireEvent.click(screen.getByRole("button", { name: /render/ }));
  message.focus();
  fireEvent.click(screen.getByRole("button", { name: /render/ }));
  expect(document.activeElement).toBe(message);
});
