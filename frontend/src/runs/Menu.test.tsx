import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { Menu, useContextMenu, type MenuItem } from "./Menu";

// A selection is document state and outlives a render, so one test's selection
// suppresses the next test's menu — which is the guard working and the isolation
// not. Found by the Escape test failing for the selection test's reason.
afterEach(() => window.getSelection()?.removeAllRanges());

const ITEMS: MenuItem[] = [
  { label: "Show its tasks", onPick: () => {} },
  { label: "Retry the failed tasks", w4: true },
];

function Harness({ items = ITEMS }: { items?: MenuItem[] }) {
  const menu = useContextMenu();
  return (
    <>
      <div data-testid="row-STAR_ALIGN" {...menu.bind}>STAR_ALIGN</div>
      <pre data-testid="failure-report">Command error: an oom-kill event was detected</pre>
      {menu.at && <Menu items={items} at={menu.at} onClose={menu.close} />}
    </>
  );
}

it("opens on a row and lists the W4 verbs as unavailable rather than hiding them", () => {
  // A menu that grows two new items in six months is worse than one that always had the
  // shape — people learn positions.
  render(<Harness />);
  fireEvent.contextMenu(screen.getByTestId("row-STAR_ALIGN"));
  expect(screen.getByText("Retry the failed tasks")).toHaveAttribute("aria-disabled", "true");
});

it("leaves the browser's own menu alone on a text selection", () => {
  // Overriding right-click everywhere steals Copy from people, which is worse than no menu.
  render(<Harness />);
  const report = screen.getByTestId("failure-report");
  const range = document.createRange();
  range.selectNodeContents(report);
  window.getSelection()?.removeAllRanges();
  window.getSelection()?.addRange(range);

  const notPrevented = fireEvent.contextMenu(screen.getByTestId("row-STAR_ALIGN"));
  expect(notPrevented).toBe(true);
  expect(screen.queryByTestId("menu")).toBeNull();
});

it("opens from the keyboard", () => {
  render(<Harness />);
  const row = screen.getByTestId("row-STAR_ALIGN");
  row.focus();
  fireEvent.keyDown(row, { key: "F10", shiftKey: true });
  expect(screen.getByTestId("menu")).toBeTruthy();
});

it("closes on Escape and gives the row its focus back", () => {
  render(<Harness />);
  const row = screen.getByTestId("row-STAR_ALIGN");
  fireEvent.contextMenu(row);
  expect(screen.getByTestId("menu")).toBeTruthy();

  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByTestId("menu")).toBeNull();
  expect(document.activeElement).toBe(row);
});
