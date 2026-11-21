import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { LegacyRun } from "./AnalysisFrame";

/** `/runs/:id` moves to the run's analysis (#613): the one the run records, not the first draft
 *  whose pipeline digest matches, since two analyses can share a pipeline. */

afterEach(() => vi.unstubAllGlobals());

function visit(run: object) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const body = String(url).includes("/api/runs") ? { runs: [run] }
      : { drafts: [{ id: "other", digest: "sha256:same" }, { id: "mine", digest: "sha256:same" }] };
    return { ok: true, status: 200, json: async () => body };
  }));
  const router = createMemoryRouter([
    { path: "/runs/:id", element: <LegacyRun fallback={null} /> },
    { path: "/a/:draft/run/:id", element: null },
  ], { initialEntries: ["/runs/r1"] });
  render(<QueryClientProvider client={new QueryClient()}><RouterProvider router={router} /></QueryClientProvider>);
  return router;
}

it("opens a run under the analysis it records", async () => {
  const router = visit({ id: "r1", pipeline_digest: "sha256:same", analysis: "mine" });
  await waitFor(() => expect(router.state.location.pathname).toBe("/a/mine/run/r1"));
});

it("falls back to the digest for a run that records no analysis", async () => {
  const router = visit({ id: "r1", pipeline_digest: "sha256:same", analysis: null });
  await waitFor(() => expect(router.state.location.pathname).toBe("/a/other/run/r1"));
});
