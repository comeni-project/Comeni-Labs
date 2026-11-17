import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

const answers: Record<string, unknown[]> = {};
vi.mock("../../wiener/api/client", () => ({
  get: vi.fn(async (url: string) => {
    const queue = answers[url];
    return queue.length > 1 ? queue.shift() : queue[0];
  }),
}));

import { useRun } from "./useRuns";

it("reads the run's progress once more when it ends, so a finished run never shows 4 of 5 (issue 532)", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  answers["/api/runs/r1"] = [{ run_id: "r1", phase: "running", counts: {} }, { run_id: "r1", phase: "succeeded", counts: {} }];
  // Its last poll lands just before the last task finishes: still 4 when the run says done.
  answers["/api/runs/r1/overview"] = [{ rows: [{ process: "QUAST", done: 4 }] }, { rows: [{ process: "QUAST", done: 4 }] },
                                      { rows: [{ process: "QUAST", done: 5 }] }];
  answers["/api/runs/r1/graph"] = [{ nodes: [] }];
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { result } = renderHook(() => useRun("r1"), {
    wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
  await waitFor(() => expect(result.current.overview.data?.rows[0].done).toBe(4));
  await vi.advanceTimersByTimeAsync(4_100);
  await waitFor(() => expect(result.current.live).toBe(false));
  await vi.advanceTimersByTimeAsync(8_200);
  await waitFor(() => expect(result.current.overview.data?.rows[0].done).toBe(5), { timeout: 500 });
  vi.useRealTimers();
});
