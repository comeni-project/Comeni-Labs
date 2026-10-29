import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const row = (path: string, state: string, extra: object = {}) => ({
  source: "nf-core", path, name: path, description: `${path} does a thing`,
  formats_in: ["fastq"], formats_out: ["bam"], tool_version: "1.0", state,
  registry_version: null, contract_id: null, problems: [], ...extra,
});

const SYNC = { outcome: "ok", started_at: "2026-10-29T10:00:00Z",
               finished_at: "2026-10-29T10:01:00Z", commit: "abc", error: null, stale: false };

const PAGE = {
  rows: [
    row("star/align", "imported", { contract_id: "nf-core/star/align@2.7.11b",
                                    registry_version: "2.7.11b", tool_version: "2.7.11b" }),
    row("quast", "not_imported"),
  ],
  total: 2,
  counts: {
    states: { imported: 1, update_available: 0, not_imported: 1, unknown: 0, gone_upstream: 0,
              in_review: 0, merged_not_released: 0 },
    topics: { alignment: 1, assembly: 1 }, formats: { bam: 1, fastq: 2 },
    sources: { "nf-core": 2 },
  },
  last_good: SYNC, last: SYNC, next_offset: null, registry_at: "v0.4.0-37-g98b4566",
};

function at(page: unknown = PAGE, entry = "/registry") {
  const fetch = vi.fn().mockImplementation(() =>
    Promise.resolve({ ok: true, json: async () => page }));
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [entry] })} />
    </QueryClientProvider>,
  );
  return fetch;
}

afterEach(() => vi.unstubAllGlobals());

it("renders rows, counts and the last sync", async () => {
  at();
  expect(await screen.findByRole("row", { name: /star\/align/ })).toBeTruthy();
  expect(screen.getByRole("row", { name: /quast/ })).toBeTruthy();
  const filters = screen.getByRole("group", { name: "In the registry" });
  expect(within(filters).getByLabelText(/Imported/).closest("label")?.textContent).toContain("1");
  expect(screen.getByText(/2 of 2/)).toBeTruthy();
  expect(screen.getByText(/synced/)).toBeTruthy();
  expect(screen.getByText(/v0.4.0-37-g98b4566/)).toBeTruthy();
});

it("the state filter writes the URL and refetches", async () => {
  const fetch = at();
  const filters = await screen.findByRole("group", { name: "In the registry" });
  fireEvent.click(within(filters).getByLabelText(/Not imported/));
  await vi.waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => String(url).includes("state=not_imported"))).toBe(true));
});

it("selecting a row fills the panel and links an imported tool", async () => {
  at();
  fireEvent.click(await screen.findByRole("row", { name: /star\/align/ }));
  const panel = screen.getByRole("complementary", { name: "Selected module" });
  const link = within(panel).getByRole("link", { name: "Open the tool" });
  expect(link.getAttribute("href")).toBe("/registry/tools/nf-core/star/align@2.7.11b");
});

it("not imported shows a disabled forge action saying part 2", async () => {
  at();
  fireEvent.click(await screen.findByRole("row", { name: /quast/ }));
  const panel = screen.getByRole("complementary", { name: "Selected module" });
  const button = within(panel).getByRole("button", { name: "Forge quast" });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  expect(within(panel).getByText(/Forging comes in part 2/)).toBeTruthy();
});

it("pull request states show 0 and the part 4 note", async () => {
  at();
  const filters = await screen.findByRole("group", { name: "In the registry" });
  const review = within(filters).getByLabelText(/In review/) as HTMLInputElement;
  expect(review.disabled).toBe(true);
  expect(within(filters).getAllByText(/Arrives with pull requests \(part 4\)/).length).toBe(2);
});

it("before any sync it offers Sync now", async () => {
  at({ ...PAGE, rows: [], total: 0, last_good: null, last: null });
  expect(await screen.findByRole("button", { name: "Sync now" })).toBeTruthy();
  expect(screen.getByText(/not been synced yet/)).toBeTruthy();
});

it("after a failed sync it says the catalogue is stale and why", async () => {
  at({ ...PAGE, last: { ...SYNC, outcome: "failed", error: "git clone failed", stale: true } });
  expect(await screen.findByText(/stale/)).toBeTruthy();
  expect(screen.getByText(/git clone failed/)).toBeTruthy();
});
