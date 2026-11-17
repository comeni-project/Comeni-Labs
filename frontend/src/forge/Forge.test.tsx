import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";
import quast from "./quast.fixture.json";

type Call = { url: string; method: string; body: unknown };

/** The recorded quast forging, with one output put back to an AI proposal waiting for review. */
function waitingView() {
  const view = structuredClone(quast);
  const item = view.items.find((i) => i.key === "contract:output:misassemblies")!;
  item.status = "proposed";
  item.revisions = [{ ...item.revisions[0], actor: "ai", move: "draft", because: "only made with a reference" }];
  view.phase = "reviewing";
  view.tests = [];
  view.pull_request = null;
  return view;
}

function at(path: string, view: object) {
  const calls: Call[] = [];
  const summary = { id: quast.id, path: "quast", version: "5.3.0", phase: "merged", next_piece: null, approved: 29,
                    total: 29, waiting: 0, drafting: false, started_by: "person", started_at: quast.started_at,
                    tests_failed: 0, pull_request: "merged" };
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null });
    const body = u.endsWith("/forge/adaptations") ? { adaptations: [summary] }
      : u.includes(`/forge/adaptations/${quast.id}`) && !u.includes("/events") ? view
      : u.includes("/forge/catalogue?") ? { rows: [], total: 0, counts: {}, aliases: {} }
      : u.includes("/forge/catalogue/") ? { row: { description: "Quality Assessment Tool for Genome Assemblies", state: "merged_not_released" }, fits: { takes_from: [], feeds: [] } }
      : u.includes("/registry/choices") ? { types: [], roles: [] }
      : [];
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

it("Forge home lists the forgings with how far each is, and what needs you", async () => {
  at("/forge", quast);
  const forgings = await screen.findByRole("region", { name: "Forgings" });
  expect(await within(forgings).findByText("quast 5.3.0")).toBeTruthy();
  expect(within(forgings).getByLabelText("Tool done, Tests done, Publish done")).toBeTruthy();
  const needs = await screen.findByRole("region", { name: "Needs you" });
  expect(within(needs).getByText(/merged, waiting for a release/)).toBeTruthy();
});

it("the tool draws its ports, and Looks right approves the AI's waiting choice", async () => {
  const calls = at(`/forge/${quast.id}`, waitingView());
  const tool = await screen.findByRole("region", { name: "The tool" });
  expect(within(tool).getByRole("button", { name: "Input consensus" })).toBeTruthy();
  expect(within(tool).queryByRole("button", { name: "Output transcriptome" })).toBeNull();
  // Waiting, it is both a port on the canvas and a row under Review in the rail.
  expect(within(tool).getByRole("button", { name: "Output misassemblies" })).toBeTruthy();
  expect(screen.getAllByRole("button", { name: /misassemblies/ }).length).toBe(2);
  fireEvent.click(await screen.findByRole("button", { name: "Looks right" }));
  await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/commands"))).toBe(true));
  const sent = calls.find((c) => c.url.endsWith("/commands"))!.body as { move: string; item: string };
  expect([sent.move, sent.item]).toEqual(["approve", "contract:output:misassemblies"]);
});

it("Tests lists the cases and what they cover", async () => {
  at(`/forge/${quast.id}/tests`, quast);
  const cases = await screen.findByRole("region", { name: "Test cases" });
  expect(within(cases).getByText("sarscov2 noref")).toBeTruthy();
  const cover = screen.getByRole("region", { name: "What the tests cover" });
  expect(within(cover).getByText("misassemblies")).toBeTruthy();
});

it("Publish shows the track to release and what the pull request carries", async () => {
  at(`/forge/${quast.id}/publish`, quast);
  expect(await screen.findByText("Pull request #1 opened")).toBeTruthy();
  const files = screen.getByRole("region", { name: "What the pull request carries" });
  expect(within(files).getByText("tools/nf-core/quast/contract.yml")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Cut a release" }).getAttribute("href")).toBe("/registry/releases");
});
