import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { Panel } from "./Panel";
import { Tile } from "./Tile";

it("tile shows its label, value and hint", () => {
  render(<Tile label="Samples" value="24" hint="paired" />);
  expect(screen.getByText("Samples")).toBeTruthy();
  expect(screen.getByText("24")).toBeTruthy();
  expect(screen.getByText("paired")).toBeTruthy();
});

it("panel titles its section and carries its actions", () => {
  render(<Panel title="Check these" actions={<button type="button">Fix</button>}><p>body</p></Panel>);
  expect(screen.getByRole("region", { name: "Check these" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Fix" })).toBeTruthy();
});
