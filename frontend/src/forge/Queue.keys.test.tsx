import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// FORGE-REWORK — mounts `legacyRoutes`, not the application's table. `/forge/queue` and
// `/forge/tools` redirect into the Registry section as of Task 13; these screens are kept
// compiled and exercised until the cleanup PR deletes them. `make forge-rework` is the list.
import { legacyRoutes as routes } from "../app/router";

const TWO = {
  total: 2,
  questions: [
    { subject: "roles", what: "the job", why_open: "no role", band: "routing",
      asked_by: ["fastqc"], candidates: [], closed: true, evidence: [],
      suggested: null, changed_at: null },
    { subject: "consumes[0].name", what: "the label", why_open: "no label",
      band: "cosmetic", asked_by: ["fastqc"], candidates: [], closed: true,
      evidence: [], suggested: null, changed_at: null },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("the queue, by keyboard", () => {
  it("opens the selected row on Enter", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => TWO,
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter(routes, { initialEntries: ["/forge/queue"] });
    render(
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("roles")).toBeTruthy());
    // Inside `act`, because each keystroke sets state. Outside it React warns and the
    // assertion below can read a render that has not happened yet.
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "j", bubbles: true }));
    });
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });

    await waitFor(() =>
      expect(router.state.location.pathname).toContain("consumes"));
  });
});
