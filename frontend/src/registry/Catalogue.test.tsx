import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const row = (path: string, state: string, extra: object = {}) => ({
  source: "nf-core", path, name: path, description: `${path} does a thing`,
  formats_in: ["fastq"], formats_out: ["bam"], mentions_in: [], mentions_out: [],
  tool_version: "1.0", state,
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
              in_review: 1, merged_not_released: 0 },
    topics: { alignment: 1, assembly: 1 }, no_topic: 3, suites: { star: 1, quast: 1, gatk4: 65 },
    reads: { fastq: 2, bam: 1 }, makes: { bam: 1, vcf: 1 }, sources: { "nf-core": 2 },
  },
  last_good: SYNC, last: SYNC, next_offset: null, registry_at: "v0.4.0-37-g98b4566",
  wider: 0, aliases: { fq: "fastq" },
};

const LINKS = [{ reads: "fastq", makes: "bam", modules: 2 }];
const CHOICES = { types: [], roles: [], tools: [
  { id: "nf-core/star/align@2.7.11b", roles: ["alignment"], reads: [], makes: [],
    feeds: ["nf-core/samtools/sort@1.24"] },
  { id: "nf-core/samtools/sort@1.24", roles: ["bam_sorting"], reads: [], makes: [], feeds: [] },
] };
const FITS = { row: {}, module: {}, fits: { feeds_it: ["star/align"], reads_it: [] } };

function at(page: unknown = PAGE, entry = "/registry") {
  const fetch = vi.fn().mockImplementation((url: string) => {
    const reply = url.includes("/catalogue/flow") ? LINKS
      : url.includes("/registry/choices") ? CHOICES
        : url.includes("/catalogue/nf-core/") ? FITS : page;
    return Promise.resolve({ ok: true, json: async () => reply });
  });
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
  const states = screen.getByRole("group", { name: "Against your registry" });
  expect(within(states).getByRole("button", { name: /Imported/ }).textContent).toContain("1");
  expect(screen.getByText(/2 of 2/)).toBeTruthy();
  expect(screen.getByText(/synced/)).toBeTruthy();
  expect(screen.getByText(/v0.4.0-37-g98b4566/)).toBeTruthy();
});

it("the state filter writes the URL and refetches", async () => {
  const fetch = at();
  const states = await screen.findByRole("group", { name: "Against your registry" });
  fireEvent.click(within(states).getByRole("button", { name: /Not imported/ }));
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

it("not imported offers Forge, which starts an adaptation", async () => {
  const fetch = at();
  fireEvent.click(await screen.findByRole("row", { name: /quast/ }));
  const panel = screen.getByRole("complementary", { name: "Selected module" });
  fireEvent.click(within(panel).getByRole("button", { name: "Forge quast" }));
  await vi.waitFor(() => expect(fetch.mock.calls.some(([url, init]) =>
    String(url).endsWith("/forge/adaptations") && init?.method === "POST")).toBe(true));
});

it("the pull request states are filters like any other", async () => {
  at();
  const states = await screen.findByRole("group", { name: "Against your registry" });
  expect(within(states).getByRole("button", { name: /In review/ })).toBeTruthy();
  expect(within(states).queryByRole("button", { name: /Merged, not released/ })).toBeNull();
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

it("a long format list is cut with a count", async () => {
  at({ ...PAGE, rows: [row("samtools/sort", "not_imported",
                           { formats_in: ["bam", "cram", "fa", "fasta", "sam"] })] });
  const sort = await screen.findByRole("row", { name: /samtools\/sort/ });
  expect(sort.textContent).toContain("fastabamcram+2→bam");
});

it("while a sync runs it says so and reads again until it ends", async () => {
  const fetch = at({ ...PAGE, last: { ...SYNC, outcome: "running", finished_at: null } });
  expect(await screen.findByText(/Syncing from nf-core/)).toBeTruthy();
  const before = fetch.mock.calls.length;
  await vi.waitFor(() => expect(fetch.mock.calls.length).toBeGreaterThan(before), { timeout: 4000 });
});

it("a first sync that failed says why", async () => {
  at({ ...PAGE, rows: [], total: 0, last_good: null,
       last: { ...SYNC, outcome: "failed", error: "git clone failed: no network" } });
  expect(await screen.findByText(/not been synced yet/)).toBeTruthy();
  expect(screen.getByText(/git clone failed: no network/)).toBeTruthy();
});

it("a suggestion becomes a chip that filters and can be removed", async () => {
  const fetch = at();
  const box = await screen.findByLabelText("Search modules");
  fireEvent.focus(box);
  fireEvent.change(box, { target: { value: "fastq to bam" } });
  fireEvent.mouseDown(await screen.findByRole("button", { name: /fastq → bam/ }));
  await vi.waitFor(() => expect(fetch.mock.calls.some(([url]) =>
    String(url).includes("reads=fastq") && String(url).includes("makes=bam"))).toBe(true));
  fireEvent.click(await screen.findByRole("button", { name: "Remove reads fastq" }));
  await vi.waitFor(() =>
    expect(screen.queryByRole("button", { name: "Remove reads fastq" })).toBeNull());
});

it("following a format filters the list, and picking it again lets go", async () => {
  const fetch = at();
  const flow = await screen.findByRole("region", { name: "How file formats connect" });
  fireEvent.click(within(flow).getByRole("button", { name: /^fastq/ }));
  await vi.waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => /catalogue\?.*reads=fastq/.test(String(url)))).toBe(true));
  expect(await within(flow).findByText(/What fastq turns into/)).toBeTruthy();
});

it("modules with no topic are a filter of their own", async () => {
  const fetch = at();
  const rail = await screen.findByRole("complementary", { name: "Filters" });
  fireEvent.click(within(rail).getByRole("button", { name: /No topic/ }));
  await vi.waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => String(url).includes("no_topic=true"))).toBe(true));
});

it("a suite can be found by name even when it is not on show", async () => {
  at();
  const rail = await screen.findByRole("complementary", { name: "Filters" });
  fireEvent.change(within(rail).getByLabelText("Find a suite"), { target: { value: "gatk" } });
  expect(within(rail).getByRole("button", { name: /gatk4/ })).toBeTruthy();
  expect(within(rail).queryByRole("button", { name: /^star/ })).toBeNull();
});

it("says how many more only mention a format, and offers them", async () => {
  const fetch = at({ ...PAGE, wider: 93 }, "/registry?reads=fastq");
  expect(await screen.findByText(/93 more only mention it/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Include them" }));
  await vi.waitFor(() =>
    expect(fetch.mock.calls.some(([url]) => String(url).includes("mentioned=true"))).toBe(true));
});

it("a format only mentioned is marked apart from a declared one", async () => {
  at({ ...PAGE, rows: [row("fastqc", "not_imported", { formats_in: [], mentions_in: ["fastq"] })] });
  const line = await screen.findByRole("row", { name: /fastqc/ });
  expect(within(line).getByText("fastq").className).toContain("pill-mention");
});

it("the preview says what fits with the registry", async () => {
  at();
  const panel = await screen.findByRole("complementary", { name: "Selected module" });
  expect(await within(panel).findByRole("button", { name: /feeds it.*star\/align/ })).toBeTruthy();
});

it("the registry diagram draws the tools the server joined", async () => {
  at();
  const pictures = await screen.findByRole("group", { name: "Picture" });
  fireEvent.click(within(pictures).getByRole("button", { name: "Your registry" }));
  const graph = await screen.findByRole("region", { name: "What your registry can do today" });
  expect(await within(graph).findByRole("button", { name: /samtools\/sort/ })).toBeTruthy();
});
