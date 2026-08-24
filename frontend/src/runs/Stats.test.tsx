import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { routes } from "../app/router";

const STATE = {
  run_id: "4c1e9a07b2f1de40", phase: "succeeded",
  counts: { succeeded: 5, failed: 0, cached: 0, running: 0, submitted: 0 },
  started_at_ms: 1787517649000, ended_at_ms: 1787517689000,
};

const RESOURCED = [
  { process: "STAR_ALIGN", tasks: 12,
    memory_asked_bytes: 34_359_738_368, memory_peak_bytes: 32_212_254_720,
    cpus_asked: 8, cpu_used_pct: 104, realtime_ms: 401_000, queue_wait_ms: 23_000,
    read_bytes: 442_450_944, write_bytes: 104_857_600 },
  { process: "TRIMGALORE", tasks: 12,
    memory_asked_bytes: 1_073_741_824, memory_peak_bytes: 8_810_496,
    cpus_asked: 6, cpu_used_pct: 210, realtime_ms: 1_400, queue_wait_ms: 740,
    read_bytes: 81_920, write_bytes: 0 },
];

const BARE = [{ process: "GREET", tasks: 1, memory_asked_bytes: null, memory_peak_bytes: null,
                cpus_asked: 1, cpu_used_pct: null, realtime_ms: 25, queue_wait_ms: null,
                read_bytes: null, write_bytes: null }];

function at(stats: unknown = RESOURCED) {
  vi.stubGlobal("WebSocket", class { constructor() {} close() {} });
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    const body = url.includes("/stats") ? stats
      : url.includes("/events") ? { events: [], cursor: -1, stream_id: "0-0" }
        : url.includes("/graph") ? { nodes: [], wires: [], width: 0, height: 0 }
          : STATE;
    return Promise.resolve({ ok: true, json: async () => body });
  }));
  const router = createMemoryRouter(routes, {
    initialEntries: ["/runs/4c1e9a07b2f1de40?more=1"],
  });
  return render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("shows what was asked for beside what was used", async () => {
  at();
  const star = await screen.findByTestId("stats-STAR_ALIGN");
  expect(star).toHaveTextContent("30 GB");     // peak
  expect(star).toHaveTextContent("of 32 GB");  // asked
  expect(star).toHaveTextContent("12 tasks · worst case");
});

it("says a run reported nothing rather than drawing bars against zero", async () => {
  // §4.3 finding 6: the resource fields are opt-in. Four empty bars would read as a process
  // that used no memory, and a reader cannot tell that from a true zero.
  at(BARE);
  expect(await screen.findByText(/No resource metrics were recorded/)).toBeInTheDocument();
  expect(screen.queryByText(/of 0 B/)).toBeNull();
});

it("draws a nearly-full bar in the colour that means look at this", async () => {
  // 30 of 32 GB is the next exit 137, and it should not look like the process using 8 MB of 1 GB.
  at();
  const tight = (await screen.findByTestId("stats-STAR_ALIGN")).querySelectorAll("span[style]");
  const bars = Array.from(tight, (s) => (s as HTMLElement).style.background).filter(Boolean);
  expect(bars.some((b) => b.includes("undecided"))).toBe(true);

  const roomy = (await screen.findByTestId("stats-TRIMGALORE")).querySelectorAll("span[style]");
  const roomyBars = Array.from(roomy, (s) => (s as HTMLElement).style.background)
    .filter(Boolean);
  expect(roomyBars.some((b) => b.includes("undecided"))).toBe(false);
});

it("is collapsed until asked for", async () => {
  vi.stubGlobal("WebSocket", class { constructor() {} close() {} });
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) =>
    Promise.resolve({ ok: true, json: async () =>
      url.includes("/events") ? { events: [], cursor: -1, stream_id: "0-0" } : STATE })));
  const router = createMemoryRouter(routes, { initialEntries: ["/runs/4c1e9a07b2f1de40"] });
  render(
    <QueryClientProvider client={makeClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("button", { name: "More" })).toHaveAttribute(
    "aria-expanded", "false");
  expect(screen.queryByTestId("stats")).toBeNull();
});
