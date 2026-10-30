import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const ID = "nf-core/star/align@2.7.11b";

const PAGE = {
  id: ID, roles: ["alignment"], container: "community.wave.seqera.io/library/star:1",
  consumes: [
    { name: "reads", type_id: "fastq.reads", states_required: [], states_conventional: ["trimmed"],
      conventional_because: "STAR soft-clips adapters.", states_made: [] },
  ],
  produces: [{ name: "bam", type_id: "alignment.bam", states_required: [],
               states_conventional: [], conventional_because: null, states_made: [] }],
  source_path: null, emits_total: null, emits_declared: null, rules_aiming: ["alignment"],
  inputs_from: [], outputs_feed: [], competes_with: [], pipeline_pins: null,
  name: "STAR", description: "An aligner that maps sequencing reads.",
  params: [
    { name: "seq_platform", default: null, asks_person: true, via: "ext", key: "args",
      template: "--outSAMattrRGline 'PL:{value}'", domain: null, because: null },
    { name: "star_ignore_sjdbgtf", default: false, asks_person: false, via: "positional",
      key: null, template: null, domain: { kind: "boolean" }, because: "Align with the annotation." },
  ],
  ext_args: "--readFilesCommand zcat", ext_args_because: "The reads are gzipped.",
  priority: 10, priority_because: "nf-core/rnaseq's default aligner.",
  tests: [],
  rules: [{ role: "alignment", effect: "implementation", because: "read length decides",
            cite: "Dobin et al. 2013",
            rows: [{ when: { read_length: ">= 70" }, then: ID, because: "built for long reads",
                     cite: null }] }],
  upstream: { repo: "https://github.com/nf-core/modules.git", sha: "6d46786420b4",
              path: "modules/nf-core/star/align" },
  licence: "MIT", approved_by: "rafael", approved_at: "2026-08-03",
  registry_at: "v0.4.0-37-g98b4566",
  catalogue: {
    row: { source: "nf-core", path: "star/align", name: "star/align", description: "Align reads",
           formats_in: ["fastq"], formats_out: ["bam"], tool_version: "2.7.11c",
           state: "update_available", registry_version: "2.7.11b", contract_id: ID, problems: [] },
    module: { source: "nf-core", path: "star/align", name: "star/align",
              description: "Align reads to a reference genome using STAR", authors: ["@drpatelh"],
              tool_version: "2.7.11c", formats_in: ["fastq", "gtf"], formats_out: ["bam"] },
  },
};

function at(answer: { ok: boolean; status?: number; body: unknown }) {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve({
    ok: answer.ok, status: answer.status ?? 200, json: async () => answer.body }));
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: [`/registry/tools/${ID}`] })} />
    </QueryClientProvider>,
  );
  return fetch;
}

afterEach(() => vi.unstubAllGlobals());

it("loads by direct link with a slash and an at sign in the id", async () => {
  const fetch = at({ ok: true, body: PAGE });
  expect(await screen.findByRole("heading", { level: 1, name: "star/align" })).toBeTruthy();
  expect(String(fetch.mock.calls[0][0])).toBe(`/api/registry/tools/${ID}`);
});

it("shows each param's reason and asks-the-person", async () => {
  at({ ok: true, body: PAGE });
  const settings = await screen.findByRole("region", { name: "Settings" });
  expect(within(settings).getByText("asks the person")).toBeTruthy();
  expect(within(settings).getByText("Align with the annotation.")).toBeTruthy();
  expect(within(settings).getByText("--readFilesCommand zcat")).toBeTruthy();
});

it("update available shows both versions", async () => {
  at({ ok: true, body: PAGE });
  const nfcore = await screen.findByRole("region", { name: "From nf-core" });
  expect(within(nfcore).getByText(/2\.7\.11c/)).toBeTruthy();
  expect(within(nfcore).getByText(/2\.7\.11b/)).toBeTruthy();
});

it("re-forge is offered, and a tool with no tests says how to add them", async () => {
  at({ ok: true, body: PAGE });
  const reforge = await screen.findByRole("button", { name: "Re-forge" });
  expect((reforge as HTMLButtonElement).disabled).toBe(false);
  expect(screen.getByText(/re-forge the tool to add them/)).toBeTruthy();
});

it("a tool's tests are listed", async () => {
  at({ ok: true, body: { ...PAGE, tests: [{ name: "small", feeds: ["reads"], expects: ["*.bam"] }] } });
  expect(await screen.findByText("small")).toBeTruthy();
  expect(screen.getByText("reads → *.bam")).toBeTruthy();
});

it("an unknown id shows the MF0504 refusal", async () => {
  at({ ok: false, status: 404, body: { detail: "MF0504: no tool 'x' in the registry" } });
  expect(await screen.findByText(/MF0504: no tool/)).toBeTruthy();
});
