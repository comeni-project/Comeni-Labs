import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useSearchParams } from "react-router";
import { describe, expect, it } from "vitest";

import { Controls } from "./Controls";

function Show() {
  const [params] = useSearchParams();
  return <output data-testid="url">{params.toString()}</output>;
}

function at(search = "") {
  render(
    <MemoryRouter initialEntries={[`/forge/queue${search}`]}>
      <Controls />
      <Show />
    </MemoryRouter>,
  );
}

describe("the queue's controls", () => {
  it("puts a chosen sort in the URL", async () => {
    at();
    await userEvent.selectOptions(screen.getByLabelText(/sort/i), "recent");
    expect(screen.getByTestId("url").textContent).toContain("sort=recent");
  });

  it("puts a chosen band in the URL and can clear it again", async () => {
    at();
    await userEvent.selectOptions(screen.getByLabelText(/band/i), "cosmetic");
    expect(screen.getByTestId("url").textContent).toContain("band=cosmetic");
    await userEvent.selectOptions(screen.getByLabelText(/band/i), "");
    expect(screen.getByTestId("url").textContent).not.toContain("band");
  });

  it("shows the state the URL describes rather than its own", async () => {
    // A link somebody sent must open on the view it describes. This fails the moment a
    // control keeps its own useState and writes the URL as an afterthought.
    at("?group=module");
    expect((screen.getByLabelText(/group/i) as HTMLSelectElement).value).toBe("module");
  });
});
