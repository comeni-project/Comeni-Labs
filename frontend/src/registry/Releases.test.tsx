import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const UNRELEASED = { last: "v0.4.0", commit: "abcdef1234567890", ahead: 2, checks: "green", says: null,
                     fragments: [{ path: "changelog.d/a.md", text: "- `a@1`: added." }] };
const PAGE = { in_use: "Using v0.4.0, following latest.", published: [{ tag: "v0.4.0", notes: "", published_at: null }],
               unreleased: UNRELEASED, merged: [{ module: "nf-core/quast", version: "5.3.0", number: 7, url: "https://x/7" }],
               suggested: "v0.5.0", notes: "- `a@1`: added.", recent: [], unavailable: null, problem: null };

function at(body: object) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    calls.push({ url: String(url), method: init?.method ?? "GET",
                 body: init?.body ? JSON.parse(String(init.body)) : null });
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/registry/releases"] })} />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

it("the tab links here", async () => {
  at(PAGE);
  const tab = await screen.findByRole("link", { name: "Releases" });
  expect(tab.getAttribute("href")).toBe("/registry/releases");
});

it("shows what is merged and unreleased, and what is in use", async () => {
  at(PAGE);
  expect(await screen.findByText("nf-core/quast")).toBeTruthy();
  expect(screen.getByText("- `a@1`: added.", { selector: "li" })).toBeTruthy();
  expect(screen.getByText(/Using v0.4.0/)).toBeTruthy();
});

it("cutting sends the suggested version and notes, as edited, and states what it tags", async () => {
  const calls = at(PAGE);
  const version = await screen.findByLabelText("Version") as HTMLInputElement;
  expect(version.value).toBe("v0.5.0");
  expect(screen.getByText(/at commit/).textContent).toContain("abcdef123456");
  fireEvent.change(version, { target: { value: "v1.0.0" } });
  fireEvent.click(screen.getByRole("button", { name: "Cut release" }));
  await vi.waitFor(() => {
    const sent = calls.find((c) => c.method === "POST");
    expect(sent?.body).toEqual({ version: "v1.0.0", notes: "- `a@1`: added." });
  });
});

it("a red main disables cutting and says why", async () => {
  at({ ...PAGE, unreleased: { ...UNRELEASED, checks: "red", says: "failed: lint" } });
  expect(await screen.findByText(/CI on main is not green: failed: lint/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Cut release" }) as HTMLButtonElement).disabled).toBe(true);
});

it("nothing to release says so", async () => {
  at({ ...PAGE, unreleased: { ...UNRELEASED, ahead: 0, fragments: [] }, merged: [] });
  expect(await screen.findByText(/main has not moved/)).toBeTruthy();
});

it("a release being cut shows it, and offers no second", async () => {
  at({ ...PAGE, recent: [{ version: "v0.5.0", state: "cutting", says: null, commit: null,
                           cut_by: "rafael", cut_at: "2026-10-30T10:00:00Z" }] });
  expect(await screen.findByText(/being cut…/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Being cut…" }) as HTMLButtonElement).disabled).toBe(true);
});

it("without a token it says why and offers no form", async () => {
  at({ ...PAGE, unavailable: "MF0516: no GitHub token is set to publish with" });
  expect(await screen.findByText(/no GitHub token is set/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Cut release" })).toBeNull();
});

it("GitHub unreadable still draws the page and says so", async () => {
  at({ ...PAGE, unreleased: null, problem: "GitHub could not be reached: ConnectError" });
  expect(await screen.findByText(/could not be reached/)).toBeTruthy();
});
