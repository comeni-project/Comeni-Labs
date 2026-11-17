import { describe, expect, it } from "vitest";

import type { PortView } from "../../api/types";
import { foldedInputs, shownPorts } from "./LivingNode";

const port = (name: string, side: "in" | "out", extra: Partial<PortView> = {}) =>
  ({ name, type_id: `t.${name}`, side, accepts: [], optional: false, adds: [], met: true, states: [], gathers: false,
     ...extra }) as PortView;

/** A card draws what the step uses (#511): optional inputs not in use fold into +N optional. */
describe("the ports a card draws", () => {
  const ports = [
    port("consensus", "in"),
    port("fasta", "in", { optional: true, met: false, state: "off", adds: ["misassemblies"] }),
    port("gff", "in", { optional: true, met: false, state: "required" }),
    port("bam", "in", { optional: true, met: false, state: null }),
    port("report", "out"),
    port("misassemblies", "out"),
  ];

  it("keeps required inputs and optional ones in use, folding the rest", () => {
    expect(shownPorts(ports).filter((p) => p.side === "in").map((p) => p.name)).toEqual(["consensus", "gff"]);
    expect(foldedInputs(ports)).toBe(2);
  });

  it("hides an output only an unused optional input would make", () => {
    expect(shownPorts(ports).filter((p) => p.side === "out").map((p) => p.name)).toEqual(["report"]);
  });

  it("draws a connected optional input even with no state recorded", () => {
    const fed = [port("x", "in", { optional: true, met: true, state: null })];
    expect(shownPorts(fed)).toHaveLength(1);
    expect(foldedInputs(fed)).toBe(0);
  });
});
