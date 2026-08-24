import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const RUNS = [
  { id: "4c1e9a07b2f1de40", phase: "running", executor: "local",
    submitted_by: "operator", submitted_at: "2026-08-23T20:01:00Z" },
  { id: "77b21de4c3802f1a", phase: "failed", executor: "local",
    submitted_by: "operator", submitted_at: "2026-08-22T09:30:00Z" },
];

function at(runs: unknown = RUNS) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => runs }));
  const router = createMemoryRouter(routes, { initialEntries: ["/runs"] });
  return render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("draws a run's phase as its own colour AND as a word", async () => {
  at();
  const row = await screen.findByTestId("run-4c1e9a07b2f1de40");
  expect(row).toHaveTextContent("running");
  // The word matters as much as the hue: `failed` and `lost` share `--undecided` on purpose,
  // and a colour alone is unreadable to somebody who cannot separate the two.
  const dot = row.querySelector("[aria-hidden]") as HTMLElement;
  expect(dot.style.background).toBe("var(--measured)");
});

it("gives failed and running different colours", async () => {
  at();
  const failed = await screen.findByTestId("run-77b21de4c3802f1a");
  const dot = failed.querySelector("[aria-hidden]") as HTMLElement;
  expect(dot.style.background).toBe("var(--undecided)");
});

it("never renders a samplesheet", async () => {
  // §12: Wiener stands in the data, and §7.1 keeps it out of every table. The board could not
  // show one even if it wanted to — this is the test that keeps that true as rows gain fields.
  at();
  await screen.findByTestId("run-4c1e9a07b2f1de40");
  expect(document.body.textContent).not.toMatch(/\.csv|samplesheet|sample/i);
});

it("says what to do when there are no runs, rather than showing an empty box", async () => {
  at([]);
  await waitFor(() => expect(screen.getByText(/No runs yet/)).toBeInTheDocument());
  expect(screen.getByText(/gated/)).toBeInTheDocument();
});

it("reads the board from Wiener, not from Mendel", async () => {
  // Two APIs on one origin, split by path (vite.config.ts). A board that fetched `/api/runs`
  // from the Mendel client would 404 in dev and hit the wrong service in prod.
  at();
  await screen.findByTestId("run-4c1e9a07b2f1de40");
  expect(vi.mocked(fetch).mock.calls[0][0]).toBe("/api/runs");
});

it("offers a token field when Wiener refuses, rather than a status code", async () => {
  // §12.1's check is one shared bearer token, and the board is the first Wiener page anybody
  // opens — so it is where a fresh install meets the 401. `Failed` would have printed
  // `/api/runs → 401`, which is true and tells nobody what to do about it.
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 }));
  const router = createMemoryRouter(routes, { initialEntries: ["/runs"] });
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByTestId("token-prompt")).toBeTruthy());
});
