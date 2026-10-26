import { describe, expect, it } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { FAKE_SESSION } from "./fake";
import { stageOf } from "./stage";

const at = (changes: Partial<AuthoringSession>) => ({ ...FAKE_SESSION, ...changes }) as AuthoringSession;
const pendingOf = (kind: string) =>
  ({ ...FAKE_SESSION.pending_proposal!, kind }) as AuthoringSession["pending_proposal"];
const nothingBuilt = { history: [], graph: { nodes: [], edges: [] } };

describe("which stage a session is in", () => {
  it.each(["understanding", "gathering", "goal_review", "resolving"] as const)(
    "is describe while %s", (phase) => {
      expect(stageOf(at({ phase }))).toBe("describe");
    });

  it("is describe while the pacing question is on offer, though the phase is building", () => {
    expect(stageOf(at({ phase: "building", pending_proposal: pendingOf("pacing") }))).toBe("describe");
  });

  it("is build while a step is on offer, and once complete", () => {
    expect(stageOf(at({ phase: "building", pending_proposal: pendingOf("step") }))).toBe("build");
    expect(stageOf(at({ phase: "complete", pending_proposal: null }))).toBe("build");
  });

  it.each(["stopped", "failed", "correcting"] as const)(
    "is describe when %s before any step was accepted, and build after one was", (phase) => {
      expect(stageOf(at({ phase, pending_proposal: null, ...nothingBuilt }))).toBe("describe");
      expect(stageOf(at({ phase, pending_proposal: null }))).toBe("build");
    });
});
