import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeClient } from "../app/queryClient";
import { Measured } from "./Measured";

function show(body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, status: 200, json: async () => body }));
  return render(
    <QueryClientProvider client={makeClient()}>
      <Measured runId="r1" live={false} />
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

const fact = (sample: string, value: number, status: string, extra = {}) => ({
  measurement: "read_length", sample, value, status, estimate: 150,
  used_by: ["selection:star_align"], coverage: "all", by: [], reason: null, ...extra,
});

describe("what the run measured (issue 465)", () => {
  it("flags a fact that disagrees, and names the decisions built on the estimate", async () => {
    show({ facts: [fact("s1", 150, "confirmed"), fact("s2", 100, "disagrees")], decided: [] });
    const rows = await screen.findAllByTestId("measured-fact");
    expect(rows.map((r) => r.getAttribute("data-status"))).toEqual(["confirmed", "disagrees"]);
    expect(screen.getByTestId("measured-flag").textContent).toContain("1 fact disagrees");
    expect(screen.getByTestId("measured-estimate").textContent).toContain(
      "built on 150; used by selection:star_align");
  });

  it("lists the values settings took at run time", async () => {
    show({ facts: [], decided: [{ step: "star_genomegenerate", setting: "sa_index_nbases",
                                  sample: "genome", value: "6" }] });
    expect((await screen.findByTestId("measured-decided")).textContent).toContain(
      "star_genomegenerate.sa_index_nbases was 6 for genome");
  });

  it("renders nothing for a run that measured nothing", async () => {
    const { container } = show({ facts: [], decided: [] });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(container.textContent).toBe("");
  });
});
