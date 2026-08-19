import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAnswer } from "./useAnswer";

afterEach(() => vi.unstubAllGlobals());

function wrap(client: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("useAnswer", () => {
  it("invalidates the queue rather than patching it", async () => {
    // The answer changes the draft's `remaining` AND the queue's aggregation. Recomputing
    // that client-side is a second implementation of aggregate(), and the two would drift.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ draft: "fastqc", subject: "roles", remaining: [] }),
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useAnswer(), { wrapper: wrap(client) });
    await act(async () => {
      await result.current.mutateAsync({
        draft: "fastqc", subject: "roles", value: ["x"], why: "because",
      });
    });

    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ["questions"] })));
  });

  it("surfaces the API's coded refusal instead of a generic failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 422,
      json: async () => ({ detail: "MF0003: 'nonsense' is not legal for roles" }),
    }));
    const client = new QueryClient({ defaultOptions: {
      queries: { retry: false }, mutations: { retry: false } } });

    const { result } = renderHook(() => useAnswer(), { wrapper: wrap(client) });
    await act(async () => {
      await result.current.mutateAsync({
        draft: "fastqc", subject: "roles", value: "nonsense", why: "w",
      }).catch(() => {});
    });

    await waitFor(() => expect(String(result.current.error)).toContain("MF0003"));
  });
});
