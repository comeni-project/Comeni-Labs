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
    goal: null,
    working: turnState === "pending",
    ai_unreviewed: [],
    revision: 0,
    graph: { nodes: [], edges: [] },
    row_version: 1,
    model_configured: true,
    turns: [
      { seq: 0, role: "person", state: "answered", text: "count genes", blocks: [],
        base_revision: 0 },
      { seq: 1, role: "assistant", state: turnState, text: "", blocks: [], base_revision: 0 },
    ],
    ...overrides,
  };
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

describe("polling", () => {
  it("asks again while the agent works, and stops once its turn ends", async () => {
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
    expect(result.current.session?.working).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    await waitFor(() => expect(result.current.session?.working).toBe(false));

    const sessionReads = () =>
      fetch.mock.calls.filter(([url]) => String(url).endsWith("/authoring/s1")).length;
    const settled = sessionReads();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(sessionReads()).toBe(settled);
  });

  it("never polls a session the agent is not working on", async () => {
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

describe("a refused change", () => {
  it("shows the server's coded notice and re-reads the session", async () => {
    const reads = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "POST") {
          return {
            ok: false,
            status: 422,
            json: async () => ({ detail: "MI0201: the pipeline changed since you last saw it" }),
          };
        }
        if (url.endsWith("/preview")) return ok({ revision: 0, text: "" });
        reads();
        return ok(view("answered"));
      }),
    );

    const { result } = renderHook(() => useAuthoringSession("s1"), { wrapper: wrap(fresh()) });
    await waitFor(() => expect(result.current.session).not.toBeNull());
    const before = reads.mock.calls.length;

    act(() => result.current.keepWhole("nf-core/star/align@2.7.11b", true));
    await waitFor(() => expect(result.current.notice?.code).toBe("MI0201"));
    await waitFor(() => expect(reads.mock.calls.length).toBeGreaterThan(before));
  });
});

describe("talking to the agent", () => {
  it("draws a message at once, and lets it go once the transcript holds it", async () => {
    let said = false;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") { said = true; return ok({ seq: 2, queued: true }); }
      if (url.endsWith("/preview")) return ok({ revision: 0, text: "" });
      if (url.endsWith("/vocabulary")) return ok({ types: {} });
      return ok(view(said ? "pending" : "answered"));
    }));
    const { result } = renderHook(() => useAuthoringSession("s1"), { wrapper: wrap(fresh()) });
    await waitFor(() => expect(result.current.session).not.toBeNull());
    act(() => result.current.say("and a QC report"));
    expect(result.current.sending).toEqual(["and a QC report"]);
    await waitFor(() => expect(result.current.sending).toEqual([]));
    expect(result.current.session?.working).toBe(true);
  });

  it("retries the failed turn by its number", async () => {
    const fetch = vi.fn(async (url: string, init?: RequestInit) =>
      init?.method === "POST" ? ok({ seq: 1, queued: true })
        : url.endsWith("/preview") ? ok({ revision: 0, text: "" })
        : url.endsWith("/vocabulary") ? ok({ types: {} })
        : ok(view("answered")));
    vi.stubGlobal("fetch", fetch);
    const { result } = renderHook(() => useAuthoringSession("s1"), { wrapper: wrap(fresh()) });
    await waitFor(() => expect(result.current.session).not.toBeNull());
    act(() => result.current.retry(1));
    await waitFor(() => expect(fetch.mock.calls.some(([url, init]) =>
      String(url).endsWith("/authoring/s1/turns/1/retry") && init?.method === "POST")).toBe(true));
  });
});




describe("coming back to the page (issue 230)", () => {
  it("asks again when the page is shown, so a turn that ended while hidden appears", async () => {
    const fetch = vi.fn(async (url: string) =>
      url.endsWith("/preview") ? ok({ revision: 0, text: "" })
        : url.endsWith("/vocabulary") ? ok({ types: {} })
        : ok(view("answered")),
    );
    vi.stubGlobal("fetch", fetch);
    const sessionReads = () =>
      fetch.mock.calls.filter(([url]) => String(url).endsWith("/authoring/s1")).length;
    renderHook(() => useAuthoringSession("s1", { pollMs: 100 }), { wrapper: wrap(fresh()) });
    await waitFor(() => expect(sessionReads()).toBe(1));
    act(() => {
      window.dispatchEvent(new Event("visibilitychange"));
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
    });
    await waitFor(() => expect(sessionReads()).toBe(2));
  });
});
