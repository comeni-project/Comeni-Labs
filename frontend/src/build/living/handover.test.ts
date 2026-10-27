import { describe, expect, it } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { FAKE_SESSION } from "./fake";
import { handoverId, stepsInOrder } from "./format";

const wrap = (seq: number) => ({ seq, role: "assistant", state: "answered", text: "", base_revision: 0, at: "",
  blocks: [{ kind: "receipt", id: `wrap-${seq}`, summary: "You'll get: counts.matrix.", revision: seq, by: "resolver" }] });
const done = (changes: Partial<AuthoringSession> = {}) =>
  ({ ...FAKE_SESSION, phase: "complete", pending_proposal: null, turns: [wrap(3), wrap(7)], ...changes }) as
    unknown as AuthoringSession;

describe("which wrap-up is the hand-over (issue 393)", () => {
  it("is the newest wrap-up of a complete session", () => {
    expect(handoverId(done())).toBe("wrap-7");
  });

  it("is none while the session is still building, or something is on offer", () => {
    expect(handoverId(done({ phase: "building" }))).toBeNull();
    expect(handoverId(done({ pending_proposal: FAKE_SESSION.pending_proposal }))).toBeNull();
  });

  it("names the decided steps in order, then a step added by hand", () => {
    const session = done({ graph: { ...FAKE_SESSION.graph, nodes: [...FAKE_SESSION.graph.nodes,
      { id: "fastqc_1", contract_id: "nf-core/fastqc@0.12.1", params: [] }] } } as Partial<AuthoringSession>);
    expect(stepsInOrder(session)).toEqual(["star_genomegenerate", "trimgalore", "star_align", "fastqc_1"]);
  });
});
