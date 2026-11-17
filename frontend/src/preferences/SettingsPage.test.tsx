import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "../app/router";

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

function at(path: string, fetch = serving()) {
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, fetch };
}

afterEach(() => vi.unstubAllGlobals());

describe("the settings page (board 4 · Settings)", () => {
  it("is a page the gear opens", async () => {
    at("/registry/releases");
    const gear = await screen.findByRole("link", { name: "Settings" });
    expect(gear.getAttribute("href")).toBe("/settings");
  });

  it("draws a setting it has never seen, under its section's own title", async () => {
    at("/settings");
    expect(await screen.findByText("Flavour")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Laboratory" })).toBeTruthy();
    expect(screen.getByText("What this laboratory prefers, for everyone here.")).toBeTruthy();
    expect(screen.getByLabelText("Spiced")).toBeTruthy();
  });

  it("puts the board's sections first, in its order, and lists every section in the rail", async () => {
    const menu = { sections: [
      ...MENU.sections,
      { key: "models", title: "Models", lede: "", order: 3, served_by: "mendel", entries: MENU.sections[1].entries.slice(0, 1) },
      { key: "appearance", title: "Appearance", lede: "", order: 1, served_by: "mendel", entries: MENU.sections[0].entries },
    ] };
    at("/settings", serving(menu));
    const rail = await screen.findByRole("navigation", { name: "Settings sections" });
    await within(rail).findByText("General");
    const names = within(rail).getAllByRole("link").map((l) => l.textContent);
    expect(names.slice(0, 2)).toEqual(["General", "Models"]);
    expect(names).toContain("Laboratory");
    expect(within(rail).getByRole("link", { name: "Models" }).getAttribute("href")).toBe("#models");
  });

  it("writes a change and asks for the menu again", async () => {
    const { fetch } = at("/settings");
    await userEvent.click(await screen.findByLabelText("Spiced"));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith("/api/settings/lab.flavour", expect.objectContaining({
        method: "PUT", body: JSON.stringify({ value: "spiced" }),
      })));
    await waitFor(() =>
      expect(fetch.mock.calls.filter(([url]) => url === "/api/settings").length).toBeGreaterThan(1));
  });

  it("shows a 409's reason under the row", async () => {
    const refusing = vi.fn().mockImplementation((url: string, init?: RequestInit) => Promise.resolve(
      init?.method === "PUT"
        ? { ok: false, status: 409, json: async () => ({ detail: "MI0300: lab.flavour is locked by .env" }) }
        : url === "/api/wiener/settings" ? ok({ sections: [] }) : ok(MENU)));
    at("/settings", refusing);
    await userEvent.click(await screen.findByLabelText("Spiced"));
    expect(await screen.findByText(/MI0300: lab.flavour is locked/)).toBeTruthy();
  });

  it("says so when the API cannot be reached", async () => {
    at("/settings", vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    expect((await screen.findAllByText(/500/)).length).toBeGreaterThan(0);
  });

  it("puts Wiener's own sections under Running", async () => {
    const running = { sections: [{
      key: "running", title: "Running", lede: "As Wiener reports it.", order: 5, served_by: "wiener",
      entries: [{
        setting: setting("running.runtime", "readonly", { label: "Container runtime" }),
        shown: shown({ value: "docker", source: "reported", locked: true }),
      }],
    }] };
    at("/settings", serving(MENU, ok(running)));
    expect(await screen.findByText("docker")).toBeTruthy();
    const section = screen.getByRole("region", { name: "Running" });
    expect(within(section).getByText("Container runtime")).toBeTruthy();
  });

  it("still draws Mendel's sections when Wiener does not answer, and says so", async () => {
    at("/settings", serving(MENU, { ok: false, status: 401, json: async () => ({}) }));
    expect(await screen.findByText("Flavour")).toBeTruthy();
    expect(await screen.findByText(/Running could not be read/)).toBeTruthy();
  });

  it("says that .env wins", async () => {
    at("/settings");
    expect(await screen.findByText((_, el) => el?.tagName === "P"
      && el.textContent === "A value in .env always wins.")).toBeTruthy();
  });

  it("answers the old overlay address as nothing special: the page you were on", async () => {
    at("/registry/releases?settings=models");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Settings" })).toBeNull());
  });
});

/** Part H: the retention limits, on both servers, where a person looks for them. */
describe("data retention", () => {
  const limit = (key: string, value: string) => ({
    setting: setting(key, "choice", {
      label: key.split(".")[1], default: value,
      options: [{ value: "keep", label: "Kept until deleted" }, { value: "7", label: "After 7 days" },
                { value: "30", label: "After 30 days" }],
    }),
    shown: shown({ value }),
  });
  const MENDEL = { sections: [{
    key: "retention", title: "Data retention", lede: "How long this installation keeps it.",
    order: 5, served_by: "mendel", entries: [limit("retention.model_replies_days", "30")],
  }] };
  const WIENER = { sections: [{
    key: "retention_runs", title: "Data retention: runs", lede: "How long Wiener keeps it.",
    order: 6, served_by: "wiener", entries: [limit("retention_runs.work_failed_days", "7")],
  }] };
  const LAST = { ran_at: "2026-10-12T04:00:00Z", removed: { model_replies: 41, drafts: 0 } };
  const LAST_RUNS = { ran_at: "2026-10-12T04:00:00Z",
                      removed: { work_succeeded: 2, work_failed: 1, runs: 0 } };

  const both = (wiener: Answer = ok(WIENER)) => vi.fn().mockImplementation(
    (url: string, init?: RequestInit) => Promise.resolve(
      init?.method === "PUT" ? ok(shown({ value: "keep", source: "installation" }))
        : url === "/api/wiener/settings" ? wiener
          : url === "/api/wiener/retention/last" ? ok(LAST_RUNS)
            : url === "/api/settings/retention/last" ? ok(LAST)
              : ok(MENDEL),
    ));

  it("writes a Wiener limit to Wiener", async () => {
    const { fetch } = at("/settings", both());
    // Both limits are on the page: Mendel's first (its order), then Wiener's.
    await waitFor(() => expect(screen.getAllByLabelText("Kept until deleted")).toHaveLength(2));
    await userEvent.click(screen.getAllByLabelText("Kept until deleted")[1]);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/wiener/settings/retention_runs.work_failed_days",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ value: "keep" }) })));
    expect(fetch.mock.calls.some(([url]) => url === "/api/settings/retention_runs.work_failed_days"))
      .toBe(false);
  });

  it("writes a Mendel limit to Mendel", async () => {
    const { fetch } = at("/settings", both());
    await waitFor(() => expect(screen.getAllByLabelText("Kept until deleted")).toHaveLength(2));
    await userEvent.click(screen.getAllByLabelText("Kept until deleted")[0]);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/settings/retention.model_replies_days", expect.objectContaining({ method: "PUT" })));
  });

  it("puts both under Data & privacy, side by side", async () => {
    at("/settings", both());
    const section = await screen.findByRole("region", { name: "Data & privacy" });
    expect(await within(section).findByRole("heading", { name: "Data retention: runs" })).toBeTruthy();
    expect(within(section).getByRole("heading", { name: "Data retention" })).toBeTruthy();
  });

  it("keeps Mendel's limits usable when Wiener does not answer", async () => {
    at("/settings", both({ ok: false, status: 503, json: async () => ({}) }));
    expect(await screen.findByLabelText("Kept until deleted")).toBeTruthy();
    expect(screen.getByLabelText("After 30 days")).toBeChecked();
  });

  it("says when each side last cleared something, and what", async () => {
    at("/settings", both());
    expect(await screen.findByText(/Last cleared 12 Oct: 41 replies/)).toBeTruthy();
  });

  it("says one of a thing in the singular (issue 305)", async () => {
    const one = vi.fn().mockImplementation((url: string) => Promise.resolve(
      url === "/api/settings/retention/last"
        ? ok({ ran_at: "2026-10-12T04:00:00Z", removed: { model_replies: 1, drafts: 1 } })
        : url === "/api/wiener/settings" ? ok({ sections: [] }) : ok(MENDEL)));
    at("/settings", one);
    expect(await screen.findByText("Last cleared 12 Oct: 1 reply, 1 draft.")).toBeTruthy();
  });

  it("counts working folders together, and says nothing was due when nothing was", async () => {
    at("/settings", both());
    expect(await screen.findByText(/Last cleared 12 Oct: 3 working folders/)).toBeTruthy();
  });
});

it("opens without waiting for a value's slower check, then shows it in that row (walk 2026-11-17)", async () => {
  const menu = { sections: [{
    key: "system", title: "System", lede: "", order: 9, served_by: "mendel",
    entries: [{
      setting: setting("system.model", "readonly", { label: "Default model's server" }),
      shown: shown({ value: "gemma3:12b at http://ollama:11434", source: "reported", locked: true, checks: true }),
    }],
  }] };
  let answer: (body: unknown) => void = () => {};
  const fetch = vi.fn().mockImplementation((url: string) => url.endsWith("/system.model/check")
    ? new Promise((done) => { answer = (body) => done(ok(body)); })
    : Promise.resolve(url === "/api/wiener/settings" ? ok({ sections: [] }) : ok(menu)));
  at("/settings", fetch);
  expect(await screen.findByText("gemma3:12b at http://ollama:11434")).toBeTruthy();
  expect(screen.getByText("checking…")).toBeTruthy();
  answer({ says: "nothing answered" });
  expect(await screen.findByText("nothing answered")).toBeTruthy();
});
