import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const BOARD = {
  rows: [],
  counts: { undrafted: 1, drafted: 1, landed: 12 },
  status_counts: { drifted: 1, unverifiable: 2, matching: 9 },
  known: null,
  sources: ["nf-core"],
};

const HEALTH = {
  contracts: 12,
  matching: 9,
  unverifiable: 2,
  types: 22,
  checked_at: "2026-08-19T03:00:00Z",
};

/** Two endpoints, because they answer two different facts — see the phase 4 correction note.
 *  `/health/registry` reads what the nightly worker wrote; `/tools` is composed now. */
function at(board: unknown = BOARD, health: unknown = HEALTH) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => (String(url).includes("/health") ? health : board),
      }),
    ),
  );
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/forge/tools"] })} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("the status board", () => {
  it("answers is everything okay before it lists anything", async () => {
    // Vercel's pattern, and the one thing three screens never did: surface the metric that
    // answers "is everything okay?" first, and let a person drill in on demand.
    at();
    await waitFor(() => expect(screen.getByTestId("verdict")).toBeTruthy());
  });

  it("says something is wrong when something is", async () => {
    at();
    await waitFor(() =>
      expect(screen.getByTestId("verdict").getAttribute("data-ok")).toBe("false"),
    );
  });

  it("says so plainly when nothing is wrong", async () => {
    at({ ...BOARD, status_counts: { drifted: 0, unverifiable: 0, matching: 12 } });
    await waitFor(() =>
      expect(screen.getByTestId("verdict").getAttribute("data-ok")).toBe("true"),
    );
  });

  it("draws one cell per landed contract, so the whole registry is one glance", async () => {
    at();
    await waitFor(() => expect(screen.getAllByTestId("cell")).toHaveLength(12));
  });

  it("renders an unknown catalogue total as an absence, never as a zero", async () => {
    // #77. Discovery reads `vendor/modules/`, so the size of the known world is unknown.
    at();
    await waitFor(() => expect(screen.getByTestId("known").textContent).toBe("—"));
    expect(screen.queryByText(/0 known/)).toBeNull();
  });

  it("withholds the check time rather than inventing one", async () => {
    // Phase 4's own rule and phase 3A's: `matching` and `unverifiable` are 0 on a fresh
    // database because nothing was measured, not because nothing matches.
    at(BOARD, { ...HEALTH, checked_at: null });
    await waitFor(() => expect(screen.getByTestId("checked").textContent).toMatch(/never/i));
  });
});
