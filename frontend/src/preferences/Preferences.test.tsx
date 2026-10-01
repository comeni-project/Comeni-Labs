import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, Navigate, RouterProvider, type RouteObject } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "../app/router";
import { Shell } from "../app/Shell";

const HELP = "A setting this page has never seen. Served by a newer API than it.";

const setting = (key: string, kind: string, extra: Record<string, unknown> = {}) => ({
  key, label: key.split(".")[1], help: HELP, kind, default: null, env: null, options: [],
  minimum: null, maximum: null, unavailable: null, where: "installation", fields: [],
  item_name: "name", from_env: null, actions: [], of: null, ...extra,
});
const shown = (extra: Record<string, unknown> = {}) => ({
  value: null, source: "default", locked: false, reason: null, set: null, last4: null, ...extra,
});

/** **A setting the frontend has never seen.** The menu draws whatever the API serves; this is
 *  the proof that adding a setting needs no frontend change (spec §9). Three sections, one of
 *  each group the rail draws: kept by this browser, by this installation, and reported. */
const MENU = {
  sections: [
    {
      key: "look", title: "Look", lede: "How it looks in this browser, and only here.", order: 1,
      served_by: "mendel",
      entries: [{
        setting: setting("look.shade", "choice", {
          label: "Shade", where: "browser", default: "dim",
          options: [{ value: "dim", label: "Dim" }, { value: "bright", label: "Bright" }],
        }),
        shown: shown({ value: "dim" }),
      }],
    },
    {
      key: "lab", title: "Laboratory", lede: "What this laboratory prefers, for everyone here.",
      order: 2, served_by: "mendel",
      entries: [
        {
          setting: setting("lab.flavour", "choice", {
            label: "Flavour", default: "plain",
            options: [{ value: "plain", label: "Plain" }, { value: "spiced", label: "Spiced" }],
          }),
          shown: shown({ value: "plain" }),
        },
        {
          setting: setting("lab.on", "toggle", { label: "On", default: false }),
          shown: shown({ value: true, source: "installation" }),
        },
        {
          // Stored, but equal to its default: not counted as set.
          setting: setting("lab.off", "toggle", { label: "Off", default: false }),
          shown: shown({ value: false, source: "installation" }),
        },
      ],
    },
    {
      key: "facts", title: "Facts", lede: "What the server reports about itself.", order: 3,
      served_by: "mendel",
      entries: [{
        setting: setting("facts.version", "readonly", { label: "Version" }),
        shown: shown({
          value: "1.2.3", source: "reported", locked: true,
          reason: { kind: "read_only_here", why: "reported", says: "Shown here, set elsewhere: reported." },
        }),
      }],
    },
  ],
};

type Answer = { ok: boolean; status: number; json: () => Promise<unknown> };
const ok = (body: unknown): Answer => ({ ok: true, status: 200, json: async () => body });

/** Mendel answers with `menu`, Wiener with `wiener` (none by default). */
const serving = (menu: unknown = MENU, wiener: Answer = ok({ sections: [] })) =>
  vi.fn().mockImplementation((url: string, init?: RequestInit) =>
    Promise.resolve(
      url === "/api/wiener/settings" ? wiener
        : init?.method === "PUT" ? ok(shown({ value: "spiced", source: "installation" }))
          : ok(menu),
    ));

/** The shell over a page that fetches nothing, so the overlay is the only thing under test. */
const table: RouteObject[] = [
  {
    element: <Shell />,
    children: [
      { path: "/page", element: <p>The page underneath</p> },
      { path: "/settings/:section?", element: <Navigate to="/page" /> },
    ],
  },
];

function at(path: string, fetch = serving(), table_: RouteObject[] = table) {
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(table_, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, fetch };
}

afterEach(() => vi.unstubAllGlobals());

describe("the settings overlay", () => {
  it("opens over the page you are on, at the first section", async () => {
    at("/page?settings=");
    const dialog = await screen.findByRole("dialog", { name: "Settings" });
    expect(await within(dialog).findByRole("heading", { name: "Look" })).toBeTruthy();
    expect(screen.getByText("The page underneath")).toBeTruthy();
  });

  it("is opened by the gear, which keeps you on the same page", async () => {
    at("/page?tab=x");
    const gear = await screen.findByRole("link", { name: "Settings" });
    expect(gear.getAttribute("href")).toBe("/page?tab=x&settings=");
  });

  it("draws a setting it has never seen, under its section's own line", async () => {
    at("/page?settings=lab");
    expect(await screen.findByText("Flavour")).toBeTruthy();
    expect(screen.getByText("What this laboratory prefers, for everyone here.")).toBeTruthy();
    expect(screen.getByLabelText("Spiced")).toBeTruthy();
  });

  it("groups the sections by where their values live, and counts what is set here", async () => {
    at("/page?settings=lab");
    const rail = await screen.findByRole("navigation", { name: "Settings sections" });
    for (const group of ["This browser", "This installation", "Reported"]) {
      expect(within(rail).getByText(group)).toBeTruthy();
    }
    expect(within(rail).getByText("1 set")).toBeTruthy();
  });

  it("moves between sections in the address, so a section can be linked", async () => {
    const { router } = at("/page?settings=lab");
    await userEvent.click(await screen.findByRole("button", { name: /Facts/ }));
    await waitFor(() => expect(router.state.location.search).toBe("?settings=facts"));
    expect(await screen.findByText("1.2.3")).toBeTruthy();
  });

  it("closes on Escape and leaves you where you were", async () => {
    const { router } = at("/page?tab=x&settings=lab");
    await screen.findByRole("dialog", { name: "Settings" });
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(router.state.location.pathname).toBe("/page");
    expect(router.state.location.search).toBe("?tab=x");
  });

  it("closes from its close button and from a click on the dimmed page, not from inside", async () => {
    at("/page?settings=lab");
    const dialog = await screen.findByRole("dialog", { name: "Settings" });
    await userEvent.click(await within(dialog).findByText("Flavour"));
    expect(screen.getByRole("dialog")).toBeTruthy();
    await userEvent.click(screen.getByTestId("settings-scrim"));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("closes a row's note on Escape before it closes itself", async () => {
    at("/page?settings=lab");
    await userEvent.click(await screen.findByRole("button", { name: "About Flavour" }));
    expect(screen.getByRole("note")).toBeTruthy();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("note")).toBeNull();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("takes the focus when it opens", async () => {
    at("/page?settings=lab");
    const dialog = await screen.findByRole("dialog", { name: "Settings" });
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
  });

  it("writes a change and asks for the menu again", async () => {
    const { fetch } = at("/page?settings=lab");
    await userEvent.click(await screen.findByLabelText("Spiced"));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith("/api/settings/lab.flavour", expect.objectContaining({
        method: "PUT", body: JSON.stringify({ value: "spiced" }),
      })));
    await waitFor(() =>
      expect(fetch.mock.calls.filter(([url]) => url === "/api/settings").length).toBeGreaterThan(1));
  });

  it("shows a 409's reason under the row", async () => {
    const fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) =>
      Promise.resolve(
        url === "/api/wiener/settings" ? ok({ sections: [] })
          : init?.method === "PUT"
            ? { ok: false, status: 409, json: async () => ({ detail: "MI0300: lab.flavour is locked: Pinned by .env (LAB_FLAVOUR)." }) }
            : ok(MENU),
      ));
    at("/page?settings=lab", fetch);
    await userEvent.click(await screen.findByLabelText("Spiced"));
    expect(await screen.findByText(/MI0300: lab.flavour is locked/)).toBeTruthy();
  });

  it("says so inside the overlay when the API cannot be reached", async () => {
    at("/page?settings=lab", vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    const dialog = await screen.findByRole("dialog", { name: "Settings" });
    expect(await within(dialog).findByText(/500/)).toBeTruthy();
  });

  it("does not crash on a section that does not exist", async () => {
    at("/page?settings=nonsense");
    expect(await screen.findByText(/no section called nonsense/i)).toBeTruthy();
  });

  it("adds Wiener's sections in their order", async () => {
    const running = { sections: [{
      key: "running", title: "Running", lede: "As Wiener reports it.", order: 5, served_by: "wiener",
      entries: [{
        setting: setting("running.runtime", "readonly", { label: "Container runtime" }),
        shown: shown({ value: "docker", source: "reported", locked: true }),
      }],
    }] };
    at("/page?settings=running", serving(MENU, ok(running)));
    expect(await screen.findByText("docker")).toBeTruthy();
    const rail = screen.getByRole("navigation", { name: "Settings sections" });
    const names = within(rail).getAllByRole("button").map((b) => b.textContent ?? "");
    expect(names.findIndex((n) => n.startsWith("Running")))
      .toBeGreaterThan(names.findIndex((n) => n.startsWith("Facts")));
  });

  it("still draws Mendel's sections when Wiener does not answer, and says so", async () => {
    at("/page?settings=lab", serving(MENU, { ok: false, status: 401, json: async () => ({}) }));
    expect(await screen.findByText("Flavour")).toBeTruthy();
    expect(await screen.findByText(/Running could not be read/)).toBeTruthy();
  });

  it("sends an old /settings link to the overlay", async () => {
    const router = createMemoryRouter(routes, { initialEntries: ["/settings/models"] });
    vi.stubGlobal("fetch", serving());
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(router.state.location.search).toBe("?settings=models"));
  });
});
