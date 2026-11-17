import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { routes } from "../../app/router";
import { DIGEST, OTHER, RUN, stubRunServers } from "./fixtures";

/** Run in the analysis frame (#511, board `Run.dc.html`). */

function at(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<QueryClientProvider client={makeClient()}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

afterEach(() => vi.unstubAllGlobals());

it("run is disabled while bindings report missing, and each links to data", async () => {
  stubRunServers({ runs: [], bindings: { params: {}, summary: "0 samples", missing: [
    { channel: "reads", type_id: "fastq.reads", why: "no kept sample is fastq.reads" },
    { channel: "fasta", type_id: "genome.fasta", why: "no reference is genome.fasta" },
  ] } });
  at("/a/d1/run");
  const checks = await screen.findByRole("list", { name: "Pre-flight checks" });
  const reads = within(checks).getByTestId("check-missing-0");
  expect(reads.dataset.state).toBe("fail");
  expect(within(reads).getByText("no kept sample is fastq.reads")).toBeTruthy();
  expect(within(reads).getByRole("link", { name: "Open Samples" }).getAttribute("href")).toBe("/a/d1/data/samples");
  expect(within(checks).getByTestId("check-missing-1").querySelector("a")?.getAttribute("href")).toBe("/a/d1/data/references");
  expect((screen.getByRole("button", { name: "Run on this machine" }) as HTMLButtonElement).disabled).toBe(true);
});

it("run is offered with the bindings' summary when nothing is missing", async () => {
  stubRunServers({ runs: [], bindings: { params: { reads: "x" }, summary: "3 samples, 1 reference", missing: [] } });
  at("/a/d1/run");
  const inputs = await screen.findByTestId("check-inputs");
  expect(inputs.dataset.state).toBe("ok");
  expect(inputs.textContent).toContain("3 samples, 1 reference");
  expect((screen.getByRole("button", { name: "Run on this machine" }) as HTMLButtonElement).disabled).toBe(false);
  expect(screen.queryByRole("textbox")).toBeNull();
});

it("the rail lists only this analysis's runs", async () => {
  stubRunServers({ runs: [
    RUN("r1", DIGEST, "2026-11-16T09:00:00Z"),
    RUN("x9", OTHER, "2026-11-16T09:30:00Z"),
    RUN("r2", DIGEST, "2026-11-16T10:00:00Z", "running"),
  ] });
  at("/a/d1/run/r2");
  const rail = await screen.findByRole("list", { name: "Runs of this analysis" });
  const links = await within(rail).findAllByRole("link", { name: /^Run \d/ });
  expect(links.map((l) => l.textContent)).toEqual([expect.stringContaining("Run 2"), expect.stringContaining("Run 1")]);
  expect(links[0].textContent).toContain("now");
  expect(links).toHaveLength(2);
  expect(links[0].getAttribute("href")).toBe("/a/d1/run/r2");
  expect(links[1].getAttribute("href")).toBe("/a/d1/run/r1");
  expect(within(rail).getByRole("link", { name: "+ New run" })).toBeTruthy();
});

it("run opens a new run, with the earlier runs in the rail", async () => {
  stubRunServers({ runs: [RUN("r1", DIGEST, "2026-11-16T09:00:00Z")],
                   bindings: { params: { reads: "x" }, summary: "3 samples", missing: [] } });
  const router = at("/a/d1/run");
  await screen.findByRole("heading", { name: "New run" });
  expect(router.state.location.pathname).toBe("/a/d1/run");
  const rail = await screen.findByRole("list", { name: "Runs of this analysis" });
  expect(within(rail).getByRole("link", { name: /^Run 1/ }).getAttribute("href")).toBe("/a/d1/run/r1");
});
