import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { FAKE_SESSION } from "./fake";
import { useAlternativePreview, type PreviewSelection } from "./useAlternativePreview";

/** A saved preview is read once per offer and context, and never again on its own: hovering,
 *  focusing, pinning and reopening reuse it; a failed read waits for a deliberate Retry. */

afterEach(() => vi.unstubAllGlobals());

const CONTEXT = { draft_revision: 4, decision_revision: 2, session_version: 9, registry: "sha256:r" };

function session(context = CONTEXT): AuthoringSession {
  return {
    ...FAKE_SESSION,
    id: "s1",
    canvas: { context, proposal_id: "p-sort", current: true, graph: FAKE_SESSION.graph, steps: [],
              channels: [], placement: {} },
    pending_proposal: { ...FAKE_SESSION.pending_proposal!, envelope: {
      offer: "step", context, preview_options: ["alt_1"], node: "samtools_sort",
      options: { keep: "x", alt_1: "y" }, amendments: {}, edges: [],
      block: FAKE_SESSION.pending_proposal!.block } },
  } as unknown as AuthoringSession;
}

const saved = (option: string, observed = CONTEXT) => ({
  option_id: option, contract: "nf-core/samtools/sormadup@1.21.0", observed_context: observed,
  frame: { context: CONTEXT, proposal_id: "p-sort", current: true,
           graph: { nodes: [], edges: [] }, steps: [], channels: [], placement: {} },
});

type Answer = { ok: boolean; status: number; json: () => Promise<unknown> };
type Fetch = (url: string) => Promise<Answer>;
const ok = (body: unknown): Answer => ({ ok: true, status: 200, json: async () => body });
const refused = (): Answer => ({ ok: false, status: 409, json: async () => ({ detail: "MI0201 changed" }) });

function harness(fetch: ReturnType<typeof vi.fn<Fetch>>) {
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient();
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { client, wrapper };
}

const previewCalls = (fetch: ReturnType<typeof vi.fn<Fetch>>) =>
  fetch.mock.calls.filter(([url]) => String(url).includes("/alternatives/")).length;

describe("reading a saved preview", () => {
  it("asks once, and hover, focus, pin and reopen reuse it", async () => {
    const fetch = vi.fn<Fetch>(async () => ok(saved("alt_1")));
    const { wrapper } = harness(fetch);
    const { result, rerender } = renderHook(
      ({ s, sel }: { s: AuthoringSession; sel: PreviewSelection }) => useAlternativePreview(s, sel),
      { wrapper, initialProps: { s: session(), sel: { option: "alt_1", pinned: false } } },
    );
    await waitFor(() => expect(result.current.preview).not.toBeNull());
    for (const sel of [null, { option: "alt_1", pinned: false }, { option: "alt_1", pinned: true },
                       null, { option: "alt_1", pinned: true }] as PreviewSelection[]) {
      rerender({ s: session(), sel });
    }
    await waitFor(() => expect(result.current.preview).not.toBeNull());
    expect(previewCalls(fetch)).toBe(1);
    expect(String(fetch.mock.calls[0][0])).toContain(
      "/pipeline/authoring/s1/proposals/p-sort/alternatives/alt_1?expected_revision=4");
  });

  it("asks for nothing that was not offered as a saved preview", async () => {
    const fetch = vi.fn<Fetch>(async () => ok(saved("alt_9")));
    const { wrapper } = harness(fetch);
    const { result } = renderHook(() => useAlternativePreview(session(), { option: "alt_9", pinned: true }),
                                  { wrapper });
    expect(result.current.available).toBe(false);
    expect(previewCalls(fetch)).toBe(0);
  });

  it("after a failed read, reopening does not ask again; Retry does", async () => {
    const fetch = vi.fn<Fetch>(async () => refused());
    const { wrapper } = harness(fetch);
    const { result, rerender } = renderHook(
      ({ sel }: { sel: PreviewSelection }) => useAlternativePreview(session(), sel),
      { wrapper, initialProps: { sel: { option: "alt_1", pinned: true } as PreviewSelection } },
    );
    await waitFor(() => expect(result.current.error).not.toBeNull());
    rerender({ sel: null });
    rerender({ sel: { option: "alt_1", pinned: true } });
    await new Promise((r) => setTimeout(r, 20));
    expect(previewCalls(fetch)).toBe(1);
    fetch.mockImplementation(async () => ok(saved("alt_1")));
    await act(async () => { await result.current.retry(); });
    await waitFor(() => expect(result.current.preview).not.toBeNull());
    expect(previewCalls(fetch)).toBe(2);
  });

  it("refuses a snapshot whose observed context is not the one asked about", async () => {
    const fetch = vi.fn<Fetch>(async () => ok(saved("alt_1", { ...CONTEXT, decision_revision: 3 })));
    const { wrapper } = harness(fetch);
    const { result } = renderHook(() => useAlternativePreview(session(), { option: "alt_1", pinned: true }),
                                  { wrapper });
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.preview).toBeNull();
  });

  it("a changed context is a different preview, read afresh", async () => {
    const later = { ...CONTEXT, decision_revision: 3 };
    const fetch = vi.fn<Fetch>(async (url: string) =>
      ok(saved("alt_1", String(url).includes("expected_decision_revision=3") ? later : CONTEXT)));
    const { wrapper } = harness(fetch);
    const { result, rerender } = renderHook(
      ({ s }: { s: AuthoringSession }) => useAlternativePreview(s, { option: "alt_1", pinned: true }),
      { wrapper, initialProps: { s: session() } },
    );
    await waitFor(() => expect(result.current.preview).not.toBeNull());
    rerender({ s: session(later) });
    await waitFor(() => expect(result.current.preview?.observed_context.decision_revision).toBe(3));
    expect(previewCalls(fetch)).toBe(2);
  });

  it("a slow answer for A does not show once B is selected", async () => {
    let releaseA: (v: unknown) => void = () => undefined;
    const fetch = vi.fn<Fetch>((url: string) => String(url).includes("/alt_1?")
      ? new Promise<Answer>((r) => { releaseA = r as (v: unknown) => void; })
      : Promise.resolve(ok(saved("alt_2"))));
    const { wrapper } = harness(fetch);
    const two = session();
    (two.pending_proposal!.envelope as { preview_options: string[] }).preview_options = ["alt_1", "alt_2"];
    const { result, rerender } = renderHook(
      ({ sel }: { sel: PreviewSelection }) => useAlternativePreview(two, sel),
      { wrapper, initialProps: { sel: { option: "alt_1", pinned: true } as PreviewSelection } },
    );
    rerender({ sel: { option: "alt_2", pinned: true } });
    await waitFor(() => expect(result.current.preview?.option_id).toBe("alt_2"));
    await act(async () => { releaseA(ok(saved("alt_1"))); });
    expect(result.current.preview?.option_id).toBe("alt_2");
  });
});
