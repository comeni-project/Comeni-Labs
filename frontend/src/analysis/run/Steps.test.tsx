import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { routes } from "../../app/router";
import { DIGEST, RUN, stubRunServers } from "./fixtures";

function at(path: string) {
  stubRunServers({ runs: [RUN("r1", DIGEST, "2026-11-16T09:00:00Z")] });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<QueryClientProvider client={makeClient()}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

afterEach(() => vi.unstubAllGlobals());

it("selected step survives switching graph to timeline", async () => {
  const router = at("/a/d1/run/r1/steps?step=star_align");
  expect(await screen.findByRole("heading", { name: "Align reads" })).toBeTruthy();
  expect((await screen.findByTestId("living-node-star_align")).getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByRole("button", { name: "Timeline" }));
  await waitFor(() => expect(screen.getByTestId("gantt-star_align").getAttribute("aria-pressed")).toBe("true"));
  expect(new URLSearchParams(router.state.location.search).get("step")).toBe("star_align");
  expect(screen.getByRole("heading", { name: "Align reads" })).toBeTruthy();
});

it("clicking a gantt bar selects that step's tasks", async () => {
  const router = at("/a/d1/run/r1/steps?view=timeline");
  fireEvent.click(await screen.findByTestId("gantt-samtools_sort"));
  expect(await screen.findByRole("heading", { name: "Sort alignments" })).toBeTruthy();
  expect(new URLSearchParams(router.state.location.search).get("step")).toBe("samtools_sort");
  // One row a sample: two seen, the third still to come.
  expect((await screen.findByTestId("task-row-WT_REP1")).textContent).toContain("done");
  expect(screen.getByTestId("task-row-WT_REP2").textContent).toContain("running");
  expect(screen.getByTestId("task-row-RAP1").textContent).toContain("did not run");
});
