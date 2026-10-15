import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";

import { get, post, put } from "../api/client";
import { usePipelineDraft } from "./usePipelineDraft";

vi.mock("../api/client", () => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }));
const graph = { nodes: [], edges: [] };
const changed = { nodes: [{ id: "align", contract_id: "nf-core/star/align@1.11.0" }], edges: [] };
const row = { id: "one", name: "draft", graph, revision: 3 };

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: {
    queries: { retry: false }, mutations: { retry: false },
  } })}><MemoryRouter initialEntries={["/build?draft=one"]}>{children}</MemoryRouter>
  </QueryClientProvider>;
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(get).mockResolvedValue(row);
});

it("checks the loaded revision and renames without replacing the graph", async () => {
  vi.mocked(put).mockResolvedValue({ ...row, name: "new", revision: 4 });
  const { result } = renderHook(usePipelineDraft, { wrapper });
  await waitFor(() => expect(result.current.name).toBe("draft"));
  act(() => result.current.rename("new", changed));
  await waitFor(() => expect(put).toHaveBeenCalledOnce());
  expect(put).toHaveBeenCalledWith("/pipeline/drafts/one", { name: "new", expected_revision: 3 });
});

it("serializes overlapping rename and autosave using the acknowledged version", async () => {
  let finish!: (value: unknown) => void;
  vi.mocked(put).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }))
    .mockResolvedValueOnce({ ...row, name: "new", graph: changed, revision: 5 });
  const { result } = renderHook(usePipelineDraft, { wrapper });
  await waitFor(() => expect(result.current.name).toBe("draft"));
  let saved!: Promise<unknown>;
  act(() => {
    result.current.rename("new", graph);
    saved = result.current.save(changed);
  });
  await waitFor(() => expect(put).toHaveBeenCalledOnce());
  await act(async () => { finish({ ...row, name: "new", revision: 4 }); await saved; });
  expect(put).toHaveBeenLastCalledWith("/pipeline/drafts/one", {
    graph: changed, expected_revision: 4,
  });
  expect(post).not.toHaveBeenCalled();
});

it("keeps a conflict visible and never retries an old graph with a fresh version", async () => {
  vi.mocked(put).mockRejectedValue(new Error("MI0201: draft changed"));
  const { result } = renderHook(usePipelineDraft, { wrapper });
  await waitFor(() => expect(result.current.name).toBe("draft"));
  await act(async () => { await expect(result.current.save(changed)).rejects.toThrow("MI0201"); });
  expect(result.current.error).toContain("MI0201");
  await act(async () => { await expect(result.current.save(graph)).rejects.toThrow("MI0201"); });
  expect(put).toHaveBeenCalledOnce();
});
