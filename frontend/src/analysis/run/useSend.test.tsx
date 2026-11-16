import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { stubRunServers } from "./fixtures";
import { useSend } from "./useSend";

afterEach(() => vi.unstubAllGlobals());

const wrapper = ({ children }: { children: ReactNode }) =>
  <QueryClientProvider client={makeClient()}>{children}</QueryClientProvider>;

it("sending posts the bindings' params to wiener, with no form", async () => {
  const params = {
    reads: { stage: [{ sample: "WT_REP1", files: ["/data/yeast/WT_REP1_R1.fastq.gz", "/data/yeast/WT_REP1_R2.fastq.gz"] }] },
    fasta: "/data/yeast/reference/genome.fasta",
  };
  const posted = vi.fn();
  stubRunServers({ bindings: { params, summary: "1 sample, 1 reference", missing: [] }, posted });
  const { result } = renderHook(() => useSend("d1", { name: "Yeast counts" }), { wrapper });
  await waitFor(() => expect(result.current.bindings?.summary).toBe("1 sample, 1 reference"));
  let accepted: { run_id: string } | undefined;
  await act(async () => { accepted = await result.current.send(); });
  expect(accepted?.run_id).toBe("new-run");
  const run = posted.mock.calls.find(([url]) => String(url).endsWith("/api/runs"));
  expect(run?.[1]).toEqual({ artifact_id: "art1", params, executor: "local" });
});

it("a missing input stops the send before anything reaches wiener", async () => {
  const posted = vi.fn();
  stubRunServers({ bindings: { params: {}, summary: "", missing: [{ channel: "reads", type_id: "fastq.reads", why: "no kept sample is fastq.reads" }] }, posted });
  const { result } = renderHook(() => useSend("d1"), { wrapper });
  await waitFor(() => expect(result.current.bindings).not.toBeNull());
  await act(async () => { await result.current.send().catch(() => null); });
  expect(posted.mock.calls.some(([url]) => String(url).includes("/api/"))).toBe(false);
});
