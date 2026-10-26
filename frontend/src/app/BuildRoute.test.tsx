import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "./router";

/** **One builder** (#395): every pipeline opens at `/build?session=`, whatever address it was
 *  reached by. A drawn draft gets its conversation opened; a bare `/build` is a new pipeline. */
function at(path: string) {
  const fetch = vi.fn(async (url: string, request?: RequestInit) => {
    const body = request?.method === "POST" && url.endsWith("/pipeline/drafts")
      ? { id: "d9", name: "", graph: { nodes: [], edges: [] }, revision: 0 }
      : request?.method === "POST" && /\/pipeline\/drafts\/[^/]+\/session$/.test(url)
        ? { session_id: url.includes("/d1/") ? "s1" : "s9" }
        : null;
    // The builder's own reads are not this test's business.
    if (body === null) return new Promise(() => {});
    return { ok: true, status: 200, json: async () => body };
  });
  vi.stubGlobal("fetch", fetch);
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, fetch };
}

afterEach(() => vi.unstubAllGlobals());

describe("BuildRoute", () => {
  it("opens a drawn draft's conversation and lands on it", async () => {
    const { router } = at("/build?draft=d1");
    await waitFor(() => expect(router.state.location.search).toBe("?session=s1"));
  });

  it("starts a new pipeline at a bare /build, once", async () => {
    const { router, fetch } = at("/build");
    await waitFor(() => expect(router.state.location.search).toBe("?session=s9"));
    const created = fetch.mock.calls.filter(([url, request]) =>
      String(url).endsWith("/pipeline/drafts") && request?.method === "POST");
    expect(created).toHaveLength(1);
  });

  it("keeps the fakes at /build", () => {
    const { router } = at("/build?fake=1");
    expect(router.state.location.search).toBe("?fake=1");
    expect(routes.flatMap((r) => r.children ?? []).some((r) => r.path === "/build/living"))
      .toBe(false);
  });
});
