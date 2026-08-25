import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Tasks } from "./Tasks";

function page(total: number, drawn = Math.min(total, 500)) {
  return {
    total,
    tasks: Array.from({ length: drawn }, (_, n) => ({
      task_id: n + 1, process: n % 2 ? "STAR_ALIGN" : "TRIMGALORE",
      status: "COMPLETED", tag: `sample_${n}`, attempts: n === 3 ? 2 : 1,
      latest_exit: 0, last_change_ms: 0,
      peak_rss_bytes: 1_000 * (drawn - n), realtime_ms: 10 * n, pct_cpu: 99,
    })),
  };
}

function at(body: unknown = page(12)) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    calls.push(url);
    return Promise.resolve({ ok: true, json: async () => body });
  }));
  render(
    <QueryClientProvider client={makeClient()}>
      <Tasks runId="r1" />
    </QueryClientProvider>,
  );
  return calls;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("draws a bounded number of rows for a five-thousand-task run", async () => {
  // The window, not the run. A test that only asserts "it renders" passes on the version
  // that puts 5,000 rows in the DOM and janks.
  at(page(5_000));
  await waitFor(() => expect(screen.getAllByTestId(/^task-/).length).toBeGreaterThan(0));
  expect(screen.getAllByTestId(/^task-/).length).toBeLessThan(80);
});

it("says how many it is not drawing rather than truncating quietly", async () => {
  at(page(5_000));
  expect(await screen.findByTestId("not-drawn")).toHaveTextContent("500");
  expect(screen.getByTestId("not-drawn")).toHaveTextContent("5,000");
});

it("asks the server to filter and sort, rather than doing it here", async () => {
  const calls = at();
  // The options are built from what came back, so wait for the page before picking one.
  await screen.findByRole("option", { name: "STAR_ALIGN" });
  await userEvent.selectOptions(screen.getByLabelText("process"), "STAR_ALIGN");
  await waitFor(() => expect(calls.some((url) =>
    url.includes("process=STAR_ALIGN"))).toBe(true));

  await userEvent.click(screen.getByTestId("sort--peak_rss_bytes"));
  await waitFor(() => expect(calls.some((url) =>
    url.includes("sort=-peak_rss_bytes"))).toBe(true));
});

it("shows the process column, because this tab spans processes", async () => {
  at();
  expect((await screen.findAllByTestId("process"))[0]).toBeInTheDocument();
});
