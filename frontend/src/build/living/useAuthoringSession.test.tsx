import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAuthoringSession } from "./useAuthoringSession";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function wrap(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const fresh = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

function view(turnState: "pending" | "answered", overrides: Record<string, unknown> = {}) {
  return {
    id: "s1",
    draft_id: "d1",
    mode: "build",
    phase: "understanding",
    failed_from: null,
    goal: null,
    revision: 0,
    graph: { nodes: [], edges: [] },
    row_version: 1,
    model_configured: true,
    turns: [
      { seq: 0, role: "person", state: "answered", text: "count genes", blocks: [],
        base_revision: 0 },
      { seq: 1, role: "assistant", state: turnState, text: "", blocks: [], base_revision: 0 },
    ],
    pending_proposal: null,
    ...overrides,
  };
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

describe("polling", () => {
  it("asks again while the turn is pending, and stops once it is answered", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const answers = [view("pending"), view("pending"), view("answered")];
    const fetch = vi.fn(async (url: string) =>
      url.endsWith("/preview") ? ok({ revision: 0, text: "" })
        : url.endsWith("/vocabulary") ? ok({ types: {} })
        : ok(answers.shift() ?? view("answered")),
    );
    vi.stubGlobal("fetch", fetch);

    const { result } = renderHook(() => useAuthoringSession("s1", { pollMs: 100 }), {
      wrapper: wrap(fresh()),
    });
    await waitFor(() => expect(result.current.session).not.toBeNull());
    expect(result.current.waiting).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    await waitFor(() => expect(result.current.waiting).toBe(false));

    const sessionReads = () =>
      fetch.mock.calls.filter(([url]) => String(url).endsWith("/authoring/s1")).length;
    const settled = sessionReads();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(sessionReads()).toBe(settled);
  });

  it("never polls a session with nothing on its way", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetch = vi.fn(async (url: string) =>
      url.endsWith("/preview") ? ok({ revision: 0, text: "" })
        : url.endsWith("/vocabulary") ? ok({ types: {} })
        : ok(view("answered")),
    );
    vi.stubGlobal("fetch", fetch);

    const { result } = renderHook(() => useAuthoringSession("s1", { pollMs: 100 }), {
      wrapper: wrap(fresh()),
    });
    await waitFor(() => expect(result.current.session).not.toBeNull());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    // Counted by URL: the preview and the vocabulary are one-time reads, and only the session is
    // polled. Counting "everything but the preview" broke the day a vocabulary read was added.
    expect(fetch.mock.calls.filter(([url]) => String(url).endsWith("/authoring/s1"))).toHaveLength(1);
  });
});

describe("a refused decision", () => {
  it("shows the server's coded notice and re-reads the session", async () => {
    const proposal = {
      id: "p1",
      kind: "goal",
      draft_revision: 0,
      options: ["accept"],
      edges: [],
      block: { kind: "goal_summary", id: "goal-1", goal: {}, have: "a", do: "b", get: "c" },
    };
    const reads = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          return {
            ok: false,
            status: 422,
            json: async () => ({ detail: "MI0201: this draft moved while you were looking at it" }),
          };
        }
        if (url.endsWith("/preview")) return ok({ revision: 0, text: "" });
        reads();
        return ok(view("answered", { phase: "goal_review", pending_proposal: proposal }));
      }),
    );

    const { result } = renderHook(() => useAuthoringSession("s1"), { wrapper: wrap(fresh()) });
    await waitFor(() => expect(result.current.session).not.toBeNull());
    const before = reads.mock.calls.length;

    act(() => result.current.accept(result.current.session!.pending_proposal!));
    await waitFor(() => expect(result.current.state.notice?.code).toBe("MI0201"));
    await waitFor(() => expect(reads.mock.calls.length).toBeGreaterThan(before));
  });
});
