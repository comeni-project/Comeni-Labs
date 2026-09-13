import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { First } from "./First";

/** The first-run prompt, once door 1 exists: live when a model is, and honest when not.
 *
 * The routing half — that `/build?session=` opens the living builder and `/build?draft=` the
 * manual one — is `BuildRoute`'s, and is tested at the bottom through the real route table.
 */

afterEach(() => vi.unstubAllGlobals());

const ok = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => body });

function first(configured: boolean | "pending", begin = vi.fn()) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/health/ai")) {
      return configured === "pending" ? new Promise(() => {}) : ok({ configured, worker_available: true,
        queue_depth: 0, concurrency: 1 });
    }
    if (url.endsWith("/pipeline/authoring") && init?.method === "POST") {
      begin(JSON.parse(String(init.body)));
      return ok({ session: { id: "s42" }, queued: true }, 201);
    }
    return ok({});
  });
  vi.stubGlobal("fetch", fetch);
  const router = createMemoryRouter(
    [{ path: "/", element: <First /> }, { path: "/build", element: <p data-testid="landed">landed</p> }],
    { initialEntries: ["/"] },
  );
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router, begin, fetch };
}

describe("with no model configured", () => {
  it("draws the prompt disabled, says why, and offers the canvas — no mode choice, no start", async () => {
    first(false);
    await waitFor(() => expect(screen.getByTestId("first-aside")).toHaveTextContent("No model is configured"));
    expect(screen.getByPlaceholderText(/RNA-seq/)).toBeDisabled();
    expect(screen.queryByTestId("start-building")).toBeNull();
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(screen.getByRole("link", { name: /draw it yourself/i })).toHaveAttribute("href", "/build");
  });

  it("does not look live while it is still asking", () => {
    first("pending");
    expect(screen.getByPlaceholderText(/RNA-seq/)).toBeDisabled();
    expect(screen.queryByTestId("start-building")).toBeNull();
  });
});

describe("with a model configured", () => {
  it("starts a Build session from the sentence and opens it", async () => {
    const { router, begin } = first(true);
    const input = await screen.findByRole("textbox", { name: /what do you want to make/i });
    await waitFor(() => expect(input).toBeEnabled());
    expect(screen.getByTestId("start-building")).toBeDisabled();

    fireEvent.change(input, { target: { value: "gene counts from paired-end RNA-seq" } });
    fireEvent.click(screen.getByTestId("start-building"));

    await waitFor(() => expect(router.state.location.search).toBe("?session=s42"));
    expect(begin).toHaveBeenCalledWith({ prompt: "gene counts from paired-end RNA-seq", mode: "build" });
  });

  it("sends the mode it was given, and nothing but the sentence beside it", async () => {
    const { begin } = first(true);
    const input = await screen.findByRole("textbox", { name: /what do you want to make/i });
    await waitFor(() => expect(input).toBeEnabled());

    fireEvent.click(screen.getByTestId("mode-spawn"));
    expect(screen.getByTestId("mode-spawn")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("mode-build")).toHaveAttribute("aria-checked", "false");
    fireEvent.change(input, { target: { value: "  count genes  " } });
    fireEvent.submit(screen.getByRole("form", { name: "describe an analysis" }));

    await waitFor(() => expect(begin).toHaveBeenCalledOnce());
    expect(Object.keys(begin.mock.calls[0][0]).sort()).toEqual(["mode", "prompt"]);
    expect(begin.mock.calls[0][0]).toEqual({ prompt: "count genes", mode: "spawn" });
  });

  it("will not start from a blank sentence", async () => {
    const { begin } = first(true);
    const input = await screen.findByRole("textbox", { name: /what do you want to make/i });
    await waitFor(() => expect(input).toBeEnabled());
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.submit(screen.getByRole("form", { name: "describe an analysis" }));
    expect(screen.getByTestId("start-building")).toBeDisabled();
    expect(begin).not.toHaveBeenCalled();
  });
});

describe("where /build goes", () => {
  async function at(entry: string) {
    const { routes } = await import("../app/router");
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(
      <QueryClientProvider client={makeClient()}>
        <RouterProvider router={createMemoryRouter(routes, { initialEntries: [entry] })} />
      </QueryClientProvider>,
    );
  }

  it("restores a living session from ?session=", async () => {
    await at("/build?session=s42");
    expect(await screen.findByTestId("living-loading")).toBeInTheDocument();
  });

  it("keeps an existing draft, and a bare /build, in the manual builder", async () => {
    await at("/build?draft=d7");
    await waitFor(() => expect(document.body.textContent).not.toBe(""));
    expect(screen.queryByTestId("living-loading")).toBeNull();
    expect(screen.queryByText(/Open a session with/)).toBeNull();
  });
});
