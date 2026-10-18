import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LivingBuilder } from "./LivingBuilder";

/** The live route draws what the session's frame says, and nothing it would have to guess.
 *
 * The frame is the server's: the visible graph with the step on offer, each step's recorded
 * metadata, and the channels that really enter. These hold that the page reads it whole — no
 * second request to draw the graph, no node twice, no input the frame did not name.
 */

afterEach(() => vi.unstubAllGlobals());

const SORT_EDGE = { from_node: "star_align", from_port: "bam", to_node: "samtools_sort", to_port: "bam" };

function live(changes: Record<string, unknown> = {}) {
  const graph = FAKE_SESSION.graph;
  return {
    ...FAKE_SESSION,
    id: "s1",
    canvas: {
      context: { draft_revision: 4, decision_revision: 0, session_version: 9, registry: "fixture" },
      proposal_id: "p-sort",
      current: true,
      graph: { nodes: [...graph.nodes, { id: "samtools_sort", contract_id: "nf-core/samtools/sort@1.21.0",
                                          params: [] }],
               edges: [...graph.edges, SORT_EDGE] },
      steps: Object.values(FAKE_STEPS),
      channels: FAKE_CHANNELS,
      placement: FAKE_SESSION.placement,
    },
    progress: { reviewed: 3, total: 5, active: { position: 4, total: 5, again: false } },
    show_gap_details: false,
    ...changes,
  };
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

function open(session: unknown) {
  const fetch = vi.fn(async (url: string) =>
    url.endsWith("/preview") ? ok({ revision: 4, state: "ready", text: "", findings: [] })
      : url.endsWith("/vocabulary") ? ok({ types: {} })
      : url.endsWith("/pipeline/authoring/s1") ? ok(session)
      : ok({}),
  );
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/build/living?session=s1"]}>
        <LivingBuilder />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}

describe("the live canvas", () => {
  it("uses the session frame without asking the manual draw endpoint", async () => {
    const fetch = open(live());
    await screen.findByTestId("living-node-star_align");
    expect(fetch.mock.calls.some(([url]) => String(url).endsWith("/pipeline/draw"))).toBe(false);
    expect(screen.getByTestId("living-node-star_align")).toHaveTextContent("3 settled");
  });

  it("says no count for a step the frame carries no metadata for", async () => {
    const frame = live().canvas;
    open(live({ canvas: { ...frame, steps: frame.steps.filter((s) => s.id !== "star_align") } }));
    const node = await screen.findByTestId("living-node-star_align");
    expect(node).not.toHaveTextContent("settled");
  });

  it("draws the step on offer once, though the frame's graph already holds it", async () => {
    open(live());
    await screen.findByTestId("living-node-samtools_sort");
    expect(screen.getAllByTestId("living-node-samtools_sort")).toHaveLength(1);
    expect(screen.getAllByTestId("ghost-wire-star_align-samtools_sort")).toHaveLength(1);
    expect(screen.queryByTestId("wire-star_align-samtools_sort")).toBeNull();
  });

  it("draws an input box only for a channel the frame names", async () => {
    open(live());
    await screen.findByTestId("living-node-star_align");
    const sources = screen.getAllByTestId(/^living-source-/).map((el) => el.dataset.testid);
    expect(sources.sort()).toEqual(["living-source-fasta", "living-source-gtf", "living-source-reads"]);
  });

  it("draws no offered step the frame does not include, as for a draft owned by hand", async () => {
    const frame = live().canvas;
    open(live({ canvas: { ...frame, proposal_id: null, graph: FAKE_SESSION.graph,
                          steps: frame.steps.filter((s) => s.id !== "samtools_sort") } }));
    await screen.findByTestId("living-node-star_align");
    expect(screen.queryByTestId("living-node-samtools_sort")).toBeNull();
  });

  it("says a held review in the step's header, keeping its footer to one line", async () => {
    open(live({ review_applicability: { star_align: "retained" } }));
    const node = await screen.findByTestId("living-node-star_align");
    expect(within(node).getByText("REVIEWED")).toBeInTheDocument();
    expect(within(node).getByText(/settled/)).not.toHaveTextContent("reviewed");
  });

  it("says when the drawn pipeline is outdated, and keeps drawing it", async () => {
    open(live({ canvas: { ...live().canvas, current: false } }));
    await screen.findByTestId("living-node-star_align");
    expect(screen.getByTestId("canvas-stale")).toHaveTextContent(/outdated/i);
  });
});

describe("progress", () => {
  it("numbers the offer by where it stands in the plan", async () => {
    open(live());
    const card = await screen.findByRole("region", { name: /step 4 of 5/i });
    expect(within(card).getByText(/Step 4 of 5 — SAMTOOLS_SORT/)).toBeInTheDocument();
    expect(screen.getByTestId("living-status")).toHaveTextContent("3 of 5 steps reviewed");
  });

  it("asks to review a step again when it was reviewed before", async () => {
    open(live({ progress: { reviewed: 2, total: 5, active: { position: 4, total: 5, again: true } } }));
    expect(await screen.findByText(/Review step 4 of 5 again — SAMTOOLS_SORT/)).toBeInTheDocument();
  });

  it("keeps a decided step's original place, and invents none for an older one", async () => {
    // Only trimgalore's offer recorded its place; the others are older than the record.
    const history = FAKE_SESSION.history.map((d) => ({ ...d, envelope: d.id === "h-trim" ? {
      offer: "step", progress: { position: 2, total: 5, again: false } } : undefined }));
    open(live({ history }));
    await screen.findByTestId("living-node-star_align");
    const log = screen.getByRole("list", { name: "decisions and conversation" });
    expect(within(log).getByText(/step 2 of 5/)).toBeInTheDocument();
    expect(within(log).queryByText(/step 1\b/)).toBeNull();
  });

  it("says why a tier-4 offer went, and calls it open only once decided", async () => {
    // #354, walk 4: answering strandedness withdrew featureCounts' offer, and its row read
    // *step 5 of 5 · open  withdrawn* — open, though nothing was left to answer.
    const offer = (state: string, node: string) => ({
      id: `h-${node}`, envelope: { offer: "step", progress: { position: 5, total: 5, again: false } },
      kind: "step", state, by: "engine", actor_kind: "engine", at: "2026-10-18T10:00:00Z",
      block: { kind: "step_proposal", id: `step-${node}`, node, contract: "nf-core/subread/featurecounts@2.0.6",
               produces: ["counts.matrix"], reason: "uncontested", tier: 4, alternatives: [] } });
    open(live({ history: [...FAKE_SESSION.history, offer("stale", "subread_featurecounts"),
                          offer("accepted", "featurecounts_again")] }));
    await screen.findByTestId("living-node-star_align");
    const log = screen.getByRole("list", { name: "decisions and conversation" });
    const [went, decided] = within(log).getAllByText(/step 5 of 5/);
    expect(went.closest("li")).toHaveTextContent("answers changed");
    expect(went.closest("li")).not.toHaveTextContent(/open|withdrawn/);
    expect(decided).toHaveTextContent("· open");
  });
});

describe("registry gaps", () => {
  const gapped = (details: boolean) => live({
    show_gap_details: details,
    pending_proposal: { ...FAKE_SESSION.pending_proposal, block: {
      ...FAKE_SESSION.pending_proposal!.block,
      gaps: [{ kind: "no_domain", subject: "seq_platform",
               fix: "registry/tools/nf-core/samtools/sort/contract.yml" }],
      unresolved_settings: ["seq_platform"] } },
  });

  it("names an unresolved setting in plain words, without a path, when Dev mode is off", async () => {
    open(gapped(false));
    const gaps = await screen.findByTestId("step-gaps");
    expect(gaps).toHaveTextContent("seq_platform");
    expect(gaps).not.toHaveTextContent("registry/tools/");
  });

  it("adds the kind and the file to fix under Dev mode", async () => {
    open(gapped(true));
    const gaps = await screen.findByTestId("step-gaps");
    expect(gaps).toHaveTextContent("registry/tools/nf-core/samtools/sort/contract.yml");
  });
});
