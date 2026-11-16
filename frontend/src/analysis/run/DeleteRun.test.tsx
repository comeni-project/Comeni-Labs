import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DeleteRun } from "./DeleteRun";

/** Deleting a run is permanent and only for a finished one (Part H). */

afterEach(() => vi.unstubAllGlobals());

function open(phase: string, answer: { ok: boolean; status: number; json: () => Promise<unknown> } =
  { ok: true, status: 204, json: async () => null }) {
  const fetch = vi.fn(async () => answer);
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <MemoryRouter initialEntries={["/runs/r1"]}><DeleteRun runId="r1" phase={phase} /></MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}

describe("deleting a run", () => {
  it("offers nothing for a run that is still going", () => {
    open("running");
    expect(screen.queryByTestId("delete-run")).toBeNull();
  });

  it("asks first, says what goes, and points at the retention settings", async () => {
    const fetch = open("succeeded");
    fireEvent.click(screen.getByTestId("delete-run"));
    // A request starts a tick after the click, so wait one before saying none was sent.
    await new Promise((settle) => setTimeout(settle, 20));
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByTestId("delete-run-confirm")).toHaveTextContent(/permanent/i);
    expect(screen.getByTestId("delete-run-confirm")).toHaveTextContent(/results/i);
    expect(screen.getByRole("link", { name: /data retention settings/i }))
      .toHaveAttribute("href", "/runs/r1?settings=retention_runs");
  });

  it("deletes on the second press", async () => {
    const fetch = open("failed");
    fireEvent.click(screen.getByTestId("delete-run"));
    fireEvent.click(screen.getByTestId("delete-run-yes"));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/runs/r1", expect.objectContaining({ method: "DELETE" })));
  });

  it("says the server's sentence when it refuses", async () => {
    open("cancelled", { ok: false, status: 409,
                        json: async () => ({ detail: "this run is running: cancel it first" }) });
    fireEvent.click(screen.getByTestId("delete-run"));
    fireEvent.click(screen.getByTestId("delete-run-yes"));
    expect(await screen.findByText(/cancel it first/)).toBeInTheDocument();
  });
});
