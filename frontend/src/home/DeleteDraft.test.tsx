import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DeleteDraft } from "./DeleteDraft";

/** Deleting a pipeline is permanent, so it asks first and says what goes (Part H). */

afterEach(() => vi.unstubAllGlobals());

function open(answer: { ok: boolean; status: number; json: () => Promise<unknown> } =
  { ok: true, status: 204, json: async () => null }) {
  const fetch = vi.fn(async () => answer);
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <MemoryRouter initialEntries={["/"]}><DeleteDraft id="d1" name="RNA-seq" /></MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}

describe("deleting a draft", () => {
  it("asks first, says it is permanent and what goes, and points at the retention settings", async () => {
    const fetch = open();
    fireEvent.click(screen.getByTestId("delete-draft"));
    // A request starts a tick after the click, so wait one before saying none was sent.
    await new Promise((settle) => setTimeout(settle, 20));
    expect(fetch).not.toHaveBeenCalled();
    const ask = screen.getByTestId("delete-draft-confirm");
    expect(ask).toHaveTextContent(/permanent/i);
    expect(ask).toHaveTextContent(/conversation/i);
    expect(screen.getByRole("link", { name: /data retention settings/i }))
      .toHaveAttribute("href", "/?settings=retention");
  });

  it("deletes on the second press, and only then", async () => {
    const fetch = open();
    fireEvent.click(screen.getByTestId("delete-draft"));
    fireEvent.click(screen.getByTestId("delete-draft-yes"));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/pipeline/drafts/d1", expect.objectContaining({ method: "DELETE" })));
  });

  it("says why when the server refuses", async () => {
    open({ ok: false, status: 422,
           json: async () => ({ detail: "MI0401: a gate is running on this draft" }) });
    fireEvent.click(screen.getByTestId("delete-draft"));
    fireEvent.click(screen.getByTestId("delete-draft-yes"));
    expect(await screen.findByText(/a gate is running/)).toBeInTheDocument();
  });

  it("can be put back down without deleting", () => {
    const fetch = open();
    fireEvent.click(screen.getByTestId("delete-draft"));
    fireEvent.click(screen.getByTestId("delete-draft-no"));
    expect(screen.queryByTestId("delete-draft-confirm")).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });
});
