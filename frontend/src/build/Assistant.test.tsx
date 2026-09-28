import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Assistant } from "./Rail";

/** The manual builder's *Assistant* tab, once door 1 exists.
 *
 * **It is the only way into a living session on an installation that has any pipeline**: `Home`
 * draws the first-run prompt only while the lab has none, and *New pipeline* opens this builder.
 * So the tab stops promising the door and becomes it — the same sentence and mode `First` sends,
 * to the same verb.
 */

afterEach(() => vi.unstubAllGlobals());

const ok = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });

function rail(configured: boolean, begin = vi.fn()) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/health/ai")) {
      return ok({ configured, worker_available: true, queue_depth: 0, concurrency: 1 });
    }
    if (url.endsWith("/pipeline/authoring") && init?.method === "POST") {
      begin(JSON.parse(String(init.body)));
      return ok({ session: { id: "s42" }, queued: true }, 201);
    }
    return ok({});
  }));
  const router = createMemoryRouter([{ path: "/build", element: <Assistant /> }], {
    initialEntries: ["/build"],
  });
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, begin };
}

describe("the Assistant tab", () => {
  it("no longer says the door is unwired", async () => {
    rail(true);
    await screen.findByRole("form", { name: "describe an analysis" });
    expect(screen.getByTestId("ask").textContent).not.toMatch(/not wired yet/i);
  });

  it("starts a Build session from the rail and opens it", async () => {
    const { router, begin } = rail(true);
    const input = await screen.findByRole("textbox", { name: /what do you want to make/i });
    await waitFor(() => expect(input).toBeEnabled());

    fireEvent.change(input, { target: { value: "gene counts from paired-end RNA-seq" } });
    fireEvent.click(screen.getByTestId("ask-start"));

    await waitFor(() => expect(router.state.location.search).toBe("?session=s42"));
    expect(begin).toHaveBeenCalledWith({ prompt: "gene counts from paired-end RNA-seq", mode: "build" });
  });

  it("sends Spawn when Spawn is chosen", async () => {
    const { begin } = rail(true);
    const input = await screen.findByRole("textbox", { name: /what do you want to make/i });
    await waitFor(() => expect(input).toBeEnabled());
    fireEvent.click(screen.getByRole("radio", { name: /spawn/i }));
    fireEvent.change(input, { target: { value: "count genes" } });
    fireEvent.click(screen.getByTestId("ask-start"));
    await waitFor(() => expect(begin).toHaveBeenCalledWith({ prompt: "count genes", mode: "spawn" }));
  });

  it("says plainly when no model is configured, and offers nothing that would start", async () => {
    rail(false);
    await waitFor(() => expect(screen.getByTestId("ask")).toHaveTextContent("No model is configured"));
    expect(screen.getByRole("textbox", { name: /what do you want to make/i })).toBeDisabled();
    expect(screen.queryByTestId("ask-start")).toBeNull();
  });
});
