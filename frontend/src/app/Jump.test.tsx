import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "./router";

/** Jump to a pipeline or run (redesign part 2, #372): the lists Home reads, filtered as you type. */
const DRAFTS = [
  { id: "d1", name: "rnaseq-star", updated_at: "2026-10-18T10:00:00Z", steps: 6 },
  { id: "d2", name: "chip-peaks", updated_at: "2026-10-19T10:00:00Z", steps: 3 },
];
const RUNS = [
  { id: "b71e04d2aaaa", name: "star-test", phase: "running", submitted_at: "2026-10-19T09:00:00Z" },
];

function at(path: string, { runsDown = false } = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.includes("/api/runs") && runsDown) {
      return { ok: false, status: 502, json: async () => ({ detail: "down" }) };
    }
    // The list only: a single draft's address must not answer with the list.
    const body = /\/pipeline\/drafts(\?|$)/.test(url) ? { drafts: DRAFTS, total: DRAFTS.length }
      : url.includes("/api/runs") ? { runs: RUNS, total: RUNS.length }
      : null;
    // Anything else is not this test's business: a 404 leaves the page in its error state
    // rather than half-drawn from an empty answer.
    if (body === null) return { ok: false, status: 404, json: async () => ({ detail: "not here" }) };
    return { ok: true, status: 200, json: async () => body };
  }));
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const press = (target: Element = document.body, meta = false) =>
  fireEvent.keyDown(target, { key: "k", ctrlKey: !meta, metaKey: meta });

afterEach(() => vi.unstubAllGlobals());

describe("jump to a pipeline or run", () => {
  it.each([[false], [true]])("opens on Ctrl+K or ⌘K (meta: %s) with the field focused", async (meta) => {
    at("/build");
    press(document.body, meta);
    const dialog = await screen.findByRole("dialog", { name: /jump/i });
    expect(within(dialog).getByRole("combobox")).toBe(document.activeElement);
  });

  it("opens even while you are typing in a field", async () => {
    at("/build");
    const field = document.createElement("textarea");
    document.body.appendChild(field);
    field.focus();
    press(field);
    expect(await screen.findByRole("dialog", { name: /jump/i })).toBeTruthy();
    field.remove();
  });

  it("stays one dialog when the shortcut is pressed twice", async () => {
    at("/build");
    press();
    await screen.findByRole("dialog", { name: /jump/i });
    press();
    expect(screen.getAllByRole("dialog", { name: /jump/i })).toHaveLength(1);
  });

  it("filters as you type and opens the chosen one", async () => {
    const router = at("/build");
    press();
    const field = await screen.findByRole("combobox");
    await userEvent.type(field, "star");
    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(2));
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      expect.stringContaining("rnaseq-star"), expect.stringContaining("star-test"),
    ]);
    await userEvent.keyboard("{ArrowDown}{Enter}");
    await waitFor(() => expect(router.state.location.pathname).toBe("/runs/b71e04d2aaaa"));
    expect(screen.queryByRole("dialog", { name: /jump/i })).toBeNull();
  });

  it("opens a pipeline at its builder address", async () => {
    const router = at("/build");
    press();
    await userEvent.type(await screen.findByRole("combobox"), "chip");
    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(1));
    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(router.state.location.pathname + router.state.location.search)
      .toBe("/build?draft=d2"));
  });

  it("still lists pipelines when runs cannot be read", async () => {
    at("/build", { runsDown: true });
    press();
    const dialog = await screen.findByRole("dialog", { name: /jump/i });
    await waitFor(() => expect(within(dialog).getByText("Runs could not be read")).toBeTruthy());
    expect(within(dialog).getAllByRole("option").map((o) => o.textContent)).toEqual([
      expect.stringContaining("chip-peaks"), expect.stringContaining("rnaseq-star"),
    ]);
  });

  it("says so when nothing matches", async () => {
    at("/build");
    press();
    await userEvent.type(await screen.findByRole("combobox"), "zzz");
    expect(await screen.findByText('Nothing matches "zzz"')).toBeTruthy();
  });

  it("closes on Esc without closing the settings behind it, and gives focus back", async () => {
    at("/build?settings=appearance");
    const opener = await screen.findByRole("button", { name: /jump to a pipeline or run/i });
    await userEvent.click(opener);
    await screen.findByRole("dialog", { name: /jump/i });
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: /jump/i })).toBeNull());
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeTruthy();
    expect(document.activeElement).toBe(opener);
  });
});
