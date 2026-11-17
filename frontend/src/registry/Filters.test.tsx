import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { expect, it } from "vitest";

import { Filters } from "./Filters";

function Where() { return <span data-testid="where">{useLocation().search}</span>; }

it("topics are bars, most first, and picking one filters by it (board 7 · Registry)", () => {
  render(<MemoryRouter initialEntries={["/registry"]}>
    <Filters counts={{ topics: { alignment: 183, genomics: 380 }, no_topic: 990, suites: {}, states: {}, reads: {}, makes: {} } as never} />
    <Where />
  </MemoryRouter>);
  const bars = screen.getAllByRole("button");
  expect(bars.map((b) => b.textContent)).toEqual(["Genomics380", "Alignment183"]);
  fireEvent.click(bars[1]);
  expect(screen.getByTestId("where").textContent).toContain("topic=alignment");
});
