import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { analysis } from "./fixtures";
import { useAnalysisData } from "./useAnalysisData";

afterEach(() => vi.unstubAllGlobals());
it("blocks twenty rapid clicks until the first choice is saved, then unlocks", async () => {
  let finish: (value: unknown) => void = () => {};
  const response = (revision = 0) => ({ ok: true, status: 200, json: async () => analysis({ revision }) });
  const fetch = vi.fn((_: string, init?: RequestInit) => init?.method === "POST"
    ? new Promise((resolve) => { finish = resolve; }) : Promise.resolve(response()));
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { result } = renderHook(() => useAnalysisData("d"), { wrapper: ({ children }: { children: ReactNode }) =>
    <QueryClientProvider client={client}>{children}</QueryClientProvider> });
  await waitFor(() => expect(result.current.data).toBeTruthy());
  act(() => { for (let i = 0; i < 20; i++) result.current.fix({ kind: "leave_out", sample: "L17_R1", by: "you", reason: null, file: null, measurement: null }); });
  await waitFor(() => expect(fetch.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
  expect(result.current.busy).toBe(true);
  expect(result.current.pendingFix).toBe("sample:L17_R1");
  await act(async () => finish(response(1)));
  await waitFor(() => expect(result.current.busy).toBe(false));
  expect(result.current.pendingFix).toBeNull();
  act(() => result.current.undoFix(0));
  await waitFor(() => expect(result.current.busy).toBe(false));
});
