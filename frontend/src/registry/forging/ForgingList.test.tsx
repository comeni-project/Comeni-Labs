import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { routes } from "../../app/router";

afterEach(() => vi.unstubAllGlobals());

it("lists open adaptations with their progress", async () => {
  const list = { adaptations: [{ id: "a1", path: "quast", version: "5.3.0", phase: "reviewing",
    next_piece: "parameters", approved: 3, total: 5, waiting: 2, drafting: false,
    started_by: "rafael", started_at: "2026-10-30T10:00:00Z" }] };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => list }));
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/registry/forging"] })} />
    </QueryClientProvider>,
  );
  const link = await screen.findByRole("link", { name: /quast/ });
  expect(link.getAttribute("href")).toBe("/registry/forging/a1");
  expect(screen.getByText(/2 proposals waiting/)).toBeTruthy();
});
