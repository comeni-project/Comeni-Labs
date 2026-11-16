import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LiveLiving } from "./LivingBuilder";

/** The live route draws what the session's frame says, and nothing it would have to guess.
 *
 * The frame is the server's: the visible graph, each step's recorded metadata, and the channels
 * that really enter. These hold that the page reads it whole — no
 * second request to draw the graph, no node twice, no input the frame did not name.
 */

afterEach(() => vi.unstubAllGlobals());

function live(changes: Record<string, unknown> = {}) {
  const graph = FAKE_SESSION.graph;
  return {
    ...FAKE_SESSION,
    id: "s1",
    canvas: {
      context: { draft_revision: 4, decision_revision: 0, session_version: 9, registry: "fixture" },
      current: true,
      graph,
      steps: Object.values(FAKE_STEPS),
      channels: FAKE_CHANNELS,
      placement: FAKE_SESSION.placement,
    },
    ...changes,
  };
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

function open(session: unknown) {
  const fetch = vi.fn(async (url: string, _init?: RequestInit) =>
    url.endsWith("/preview") ? ok({ revision: 4, state: "ready", text: "", findings: [] })
      : url.endsWith("/vocabulary") ? ok({ types: {} })
      : url.endsWith("/pipeline/authoring/s1") ? ok(session)
      : ok({}),
  );
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/a/d1/build"]}>
        <LiveLiving sessionId="s1" />
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
    expect(screen.getByTestId("node-name-star_align")).toBeInTheDocument();
  });

  it("says no count for a step the frame carries no metadata for", async () => {
    const frame = live().canvas;
    open(live({ canvas: { ...frame, steps: frame.steps.filter((s) => s.id !== "star_align") } }));
    const node = await screen.findByTestId("living-node-star_align");
    expect(node).not.toHaveTextContent("settled");
  });

  it("draws an input box only for a channel the frame names", async () => {
    open(live());
    await screen.findByTestId("living-node-star_align");
    const sources = screen.getAllByTestId(/^living-source-/).map((el) => el.dataset.testid);
    expect(sources.sort()).toEqual(["living-source-fasta", "living-source-gtf", "living-source-reads"]);
  });

  it("says when the drawn pipeline is outdated, and keeps drawing it", async () => {
    open(live({ canvas: { ...live().canvas, current: false } }));
    await screen.findByTestId("living-node-star_align");
    expect(screen.getByTestId("canvas-stale")).toHaveTextContent(/outdated/i);
  });
});

describe("the conversation", () => {
  it("polls while the agent works and draws its trail", async () => {
    open(live());
    expect(await screen.findByRole("status", { name: "working" })).toHaveTextContent("Reading the step samtools_sort…");
  });

  it("sends an answer to the agent's question by its id", async () => {
    const fetch = open(live({ working: false, turns: FAKE_SESSION.turns.slice(0, 2) }));
    const asked = await screen.findByRole("group", { name: "Are the reads stranded?" });
    fireEvent.click(within(asked).getByRole("button", { name: "reverse-stranded" }));
    await vi.waitFor(() => expect(fetch.mock.calls.some(([url]) =>
      String(url).endsWith("/pipeline/authoring/s1/questions/q-strand"))).toBe(true));
    const [, init] = fetch.mock.calls.find(([url]) => String(url).endsWith("/questions/q-strand"))!;
    expect(JSON.parse(String(init?.body))).toEqual({ value: "reverse-stranded" });
  });
});
