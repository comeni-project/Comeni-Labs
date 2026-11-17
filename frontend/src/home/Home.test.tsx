import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

/** Welcome and Home (#511, board `Welcome.dc.html` and `Home.dc.html`). */

const DIGEST = "sha256:" + "a".repeat(64);
const COUNTS = {
  id: "aaaa1111", name: "Liver RNA-seq counts", who: "R. Correia",
  updated_at: "2026-11-16T10:00:00Z", steps: 4, makes: ["counts.matrix"],
  kept: true, changed_since_kept: false, digest: DIGEST,
  provenance: { settled: 9, measured: 1, open: 0, optional: 0, by_person: 4, by_model: 0 },
  open_values: [], open_not_named: 0,
  data: { samples: 24, checks: 0, scan: "done", folders: 1 },
};
const ISOLATES = {
  ...COUNTS, id: "bbbb2222", name: "E. coli isolate assembly QC", digest: null, kept: false,
  open_values: [{ step: "nf-core/quast@5.2.0", setting: "min_contig" }], open_not_named: 1,
  data: { samples: 3, checks: 2, scan: "done", folders: 1 },
};
const RUNNING = {
  id: "cccc3333", phase: "running", executor: "local", name: null, submitted_by: "operator",
  submitted_at: "2026-11-16T09:00:00Z", ended_at: null,
  tasks_done: 14, tasks_seen: 24, pipeline_digest: DIGEST,
};

function at({ drafts = [COUNTS, ISOLATES] as unknown[], runs = [RUNNING] as unknown[], model = true,
              wiener = true, posted = vi.fn() } = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/pipeline/drafts") && init?.method === "POST") {
      posted(JSON.parse(String(init.body)));
      return { ok: true, status: 201, json: async () => ({ id: "new1" }) };
    }
    if (url.endsWith("/health/ai")) return new Promise(() => {});
    if (url.includes("/api/runs") && !wiener) throw new TypeError("unreachable");
    const body = url.endsWith("/settings/ai") ? { configured: model }
      : url.includes("/pipeline/drafts") ? { drafts, total: drafts.length }
      : url.includes("/api/runs") ? { runs, total: runs.length }
      : url.endsWith("/data/machine")
        ? { cpus: 12, load: 10, memory_gb: 64, memory_free_gb: 33, disk_free_gb: 212 }
      : url.includes("/data/tree") ? { path: null, files: 0, folders: [] }
      : url.includes("/api/data/") ? { folders: [], samples: [], references: [], checks: [], files: 0,
                                       scan: { state: "idle" }, rule: {}, fixes: [], kinds: [],
                                       columns: {}, measured: [], unfit: 0 }
      : url.includes("/pipeline/drafts/") ? { id: "new1", name: "", graph: { nodes: [], edges: [] } }
      : {};
    return { ok: true, status: 200, json: async () => body };
  }));
  const router = createMemoryRouter(routes, { initialEntries: ["/"] });
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

afterEach(() => vi.unstubAllGlobals());

describe("Welcome", () => {
  it("no drafts renders Welcome without a rail", async () => {
    at({ drafts: [], runs: [] });
    expect(await screen.findByText("Omnes omnia omnino")).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "What do you want to find out?" })).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Comeni" })).toBeNull();
    for (const starter of ["Gene counts from RNA-seq", "Assemble and check bacterial isolates",
      "Variants against a reference", "Species in a metagenome"]) {
      expect(screen.getByRole("button", { name: starter })).toBeTruthy();
    }
  });

  it("add a folder creates a draft and opens its data", async () => {
    const posted = vi.fn();
    const router = at({ drafts: [], runs: [], posted });
    fireEvent.click(await screen.findByRole("button", { name: "Add a folder" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/a/new1/data"));
    expect(posted).toHaveBeenCalledOnce();
  });

  it("build by hand opens an empty analysis's Build", async () => {
    const router = at({ drafts: [], runs: [] });
    fireEvent.click(await screen.findByRole("button", { name: "Build by hand" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/a/new1/build"));
  });

  it("a starter fills the question rather than starting at once", async () => {
    at({ drafts: [], runs: [] });
    fireEvent.click(await screen.findByRole("button", { name: "Species in a metagenome" }));
    expect((screen.getByRole("textbox", { name: "What do you want to find out?" }) as HTMLInputElement)
      .value).toBe("Species in a metagenome");
  });

  it("without a model the question says why it waits, and a folder still starts", async () => {
    at({ drafts: [], runs: [], model: false });
    expect(await screen.findByText(/Set up a model/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Start" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Add a folder" }) as HTMLButtonElement).disabled).toBe(false);
  });
});

describe("Home", () => {
  it("an analysis card shows the data, build and run strip from data_summary", async () => {
    at();
    const analyses = await screen.findByRole("region", { name: "Analyses" });
    const card = within(analyses).getByRole("link", { name: /E\. coli isolate assembly QC/ });
    expect(within(card).getByText("3 samples · 2 to check")).toBeTruthy();
    const strip = within(card).getByRole("list", { name: "Data, Build, Run" });
    expect(within(strip).getAllByRole("listitem").map((li) => li.getAttribute("aria-label")))
      .toEqual(["Data: needs a look", "Build: needs a look", "Run: not yet"]);
    const counts = within(analyses).getByRole("link", { name: /Liver RNA-seq counts/ });
    expect(within(counts).getByRole("listitem", { name: "Run: running" })).toBeTruthy();
  });

  it("puts running now, then needs you, then the analyses", async () => {
    at();
    const running = await screen.findByRole("region", { name: "Running now" });
    expect(within(running).getByText(/14 of 24 tasks/)).toBeTruthy();
    const needs = screen.getByRole("region", { name: "Needs you" });
    expect(within(needs).getByText("E. coli isolate assembly QC")).toBeTruthy();
    expect(within(needs).getByText(/2 to check in Data/)).toBeTruthy();
    const analyses = screen.getByRole("region", { name: "Analyses" });
    expect(running.compareDocumentPosition(needs) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(needs.compareDocumentPosition(analyses) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(analyses).getByRole("button", { name: "+ New analysis" })).toBeTruthy();
  });

  it("running now and needs you are absent when empty", async () => {
    at({ drafts: [COUNTS], runs: [] });
    await screen.findByRole("region", { name: "Analyses" });
    expect(screen.queryByRole("region", { name: "Running now" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Needs you" })).toBeNull();
  });

  it("home never renders a contract id", async () => {
    at();
    await screen.findByRole("region", { name: "Analyses" });
    expect(document.body.textContent).not.toContain("nf-core/quast");
  });

  it("the rail lists recent analyses", async () => {
    at();
    const recent = await screen.findByRole("group", { name: "Recent" });
    expect(within(recent).getAllByRole("link").map((a) => a.textContent))
      .toEqual([expect.stringContaining("Liver RNA-seq counts"), expect.stringContaining("E. coli")]);
  });

  it("this machine shows CPU, memory and disk", async () => {
    at();
    const machine = await screen.findByRole("region", { name: "This machine" });
    await within(machine).findByText("10/12");
    expect(within(machine).getByText("31/64 GB")).toBeTruthy();
    expect(within(machine).getByText("212 GB")).toBeTruthy();
  });

  it("search narrows the analyses", async () => {
    at();
    const analyses = await screen.findByRole("region", { name: "Analyses" });
    fireEvent.change(within(analyses).getByRole("searchbox"), { target: { value: "liver" } });
    expect(within(analyses).queryByText("E. coli isolate assembly QC")).toBeNull();
    expect(within(analyses).getByText("Liver RNA-seq counts")).toBeTruthy();
  });

  it("still lists the analyses when Wiener is unreachable", async () => {
    at({ wiener: false });
    const analyses = await screen.findByRole("region", { name: "Analyses" });
    expect(within(analyses).getByRole("link", { name: /Liver RNA-seq counts/ })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Running now" })).toBeNull();
  });
});

describe("Home's runs", () => {
  it("a run that is not an analysis's (a Forge test) is not running now", async () => {
    at({ runs: [{ ...RUNNING, id: "f1", name: "forge test: nf-core/quast@5.3.0", pipeline_digest: "sha256:" + "f".repeat(64) }] });
    await screen.findByRole("region", { name: "Analyses" });
    expect(screen.queryByRole("region", { name: "Running now" })).toBeNull();
    expect(document.body.textContent).not.toContain("nf-core/quast");
  });
});
