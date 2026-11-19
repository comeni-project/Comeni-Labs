import { describe, expect, it } from "vitest";

import type { DraftGraph } from "../api/types";
import { feedingOnly } from "./graphOps";

const node = (id: string) => ({ id, contract_id: `c/${id}` }) as DraftGraph["nodes"][number];
const edge = (from_node: string, to_node: string) =>
  ({ from_node, from_port: "out", to_node, to_port: "in" }) as DraftGraph["edges"][number];

describe("what goes with a removed step (#509)", () => {
  it("names a step that only fed it, and what only fed that", () => {
    const g = { nodes: ["trim", "fastqc", "multiqc"].map(node),
                edges: [edge("trim", "fastqc"), edge("fastqc", "multiqc")] } as DraftGraph;
    expect(feedingOnly(g, "multiqc")).toEqual(["trim", "fastqc"]);
  });

  it("keeps a step that also feeds something staying, and one that makes a result", () => {
    const g = { nodes: ["trim", "fastqc", "multiqc", "star"].map(node),
                edges: [edge("trim", "fastqc"), edge("trim", "star"), edge("fastqc", "multiqc")] } as DraftGraph;
    expect(feedingOnly(g, "multiqc")).toEqual(["fastqc"]);
    expect(feedingOnly(g, "star")).toEqual([]);
  });
});
