import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "../app/router";

const HELP = "A setting this page has never seen, served by a newer API than it.";

/** **A setting the frontend has never seen.** The menu draws whatever the API serves; this is
 *  the proof that adding a setting needs no frontend change (spec §9). */
const MENU = {
  sections: [
    {
      key: "lab", title: "Laboratory", order: 1, served_by: "mendel",
      entries: [{
        setting: {
          key: "lab.flavour", label: "Flavour", help: HELP, kind: "choice", default: "plain",
          env: null, options: [{ value: "plain", label: "Plain" }, { value: "spiced", label: "Spiced" }],
          minimum: null, maximum: null, unavailable: null, where: "installation",
        },
        shown: { value: "plain", source: "default", locked: false, reason: null, set: null, last4: null },
      }],
    },
    {
      key: "other", title: "Other", order: 2, served_by: "mendel",
      entries: [{
        setting: {
          key: "other.on", label: "On", help: HELP, kind: "toggle", default: false, env: null,
          options: [], minimum: null, maximum: null, unavailable: null, where: "installation",
        },
        shown: { value: false, source: "default", locked: false, reason: null, set: null, last4: null },
      }],
    },
  ],
};

function at(path: string, fetch: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const serving = (menu = MENU) =>
  vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => menu });

afterEach(() => vi.unstubAllGlobals());

describe("the settings page", () => {
  it("opens on the first section and draws a setting it has never seen", async () => {
    const router = at("/settings", serving());
    await waitFor(() => expect(router.state.location.pathname).toBe("/settings/lab"));
    expect(await screen.findByText("Flavour")).toBeTruthy();
    expect(screen.getByLabelText("Spiced")).toBeTruthy();
  });

  it("lists every section and moves between them", async () => {
    at("/settings/lab", serving());
    await userEvent.click(await screen.findByRole("link", { name: "Other" }));
    expect(await screen.findByRole("checkbox", { name: "On" })).toBeTruthy();
  });

  it("writes a change and asks for the menu again", async () => {
    const fetch = serving();
    at("/settings/lab", fetch);
    await userEvent.click(await screen.findByLabelText("Spiced"));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith("/api/settings/lab.flavour", expect.objectContaining({
        method: "PUT", body: JSON.stringify({ value: "spiced" }),
      })));
    await waitFor(() =>
      expect(fetch.mock.calls.filter(([url]) => url === "/api/settings").length).toBeGreaterThan(1));
  });

  it("shows a 409's reason under the row", async () => {
    const fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      Promise.resolve(init?.method === "PUT"
        ? { ok: false, status: 409, json: async () => ({ detail: "MI0300: lab.flavour is locked: Pinned by .env (LAB_FLAVOUR)." }) }
        : { ok: true, status: 200, json: async () => MENU }));
    at("/settings/lab", fetch);
    await userEvent.click(await screen.findByLabelText("Spiced"));
    expect(await screen.findByText(/MI0300: lab.flavour is locked/)).toBeTruthy();
  });

  it("says so when the API cannot be reached", async () => {
    at("/settings", vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    expect(await screen.findByText(/500/)).toBeTruthy();
  });

  it("does not crash on a section that does not exist", async () => {
    at("/settings/nonsense", serving());
    expect(await screen.findByText(/no section called nonsense/i)).toBeTruthy();
  });

  it("is reached from the gear in the top bar", async () => {
    // Asserted on the link rather than by clicking from `/`: the home page fetches its own data,
    // and a stub serving the menu to every request would make that page the thing under test.
    at("/settings/lab", serving());
    expect((await screen.findByRole("link", { name: "Settings" })).getAttribute("href"))
      .toBe("/settings");
  });
});
