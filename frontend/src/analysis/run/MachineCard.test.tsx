import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

vi.mock("../../api/client", () => ({ get: vi.fn(async () => ({ cpus: 32, memory_gb: 47 })), post: vi.fn() }));
vi.mock("../../wiener/api/client", () => ({
  get: vi.fn(async () => ({
    from_ms: 0, to_ms: 300, open: false,
    curves: [
      { name: "cpu reserved", kind: "exact", unit: "cpus", points: [{ at_ms: 0, value: 12 }, { at_ms: 300, value: 0 }] },
      { name: "cpu used", kind: "derived", unit: "cpus", points: [{ at_ms: 0, value: 2.5 }, { at_ms: 300, value: 0 }] },
      { name: "memory reserved", kind: "exact", unit: "bytes", points: [{ at_ms: 0, value: 2 ** 31 }, { at_ms: 300, value: 0 }] },
      { name: "attempts in flight", kind: "exact", unit: "tasks", points: [{ at_ms: 0, value: 1 }, { at_ms: 300, value: 0 }] },
    ],
  })),
}));

import { MachineCard } from "./Overview";

it("says cores used beside cores reserved, and draws both (issue 532)", async () => {
  render(<QueryClientProvider client={new QueryClient()}>
    <MachineCard runId="r1" rows={[]} live={false} nameOf={(p) => p} />
  </QueryClientProvider>);
  const row = await screen.findByTestId("usage-cores");
  expect(row).toHaveTextContent("peak 12 reserved · 2.5 used");
  expect(row.querySelectorAll("[data-curve='used']")).toHaveLength(1);
});
