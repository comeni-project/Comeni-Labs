import { describe, expect, it } from "vitest";
import type { AdaptationList } from "./useAdaptation";
import { listInterval } from "./useAdaptation";

const forging = (phase: string, drafting = false) => ({ phase, drafting });
const list = (...forgings: { phase: string; drafting: boolean }[]) =>
  ({ adaptations: forgings }) as unknown as AdaptationList;

describe("listInterval (#576)", () => {
  it("asks every five seconds while a forging works", () => {
    expect(listInterval(list(forging("testing"), forging("in_review")))).toBe(5_000);
    expect(listInterval(list(forging("drafting", true)))).toBe(5_000);
  });
  it("asks every fifteen while forgings only wait in review", () => {
    expect(listInterval(list(forging("in_review"), forging("done")))).toBe(15_000);
  });
  it("does not ask when nothing is moving", () => {
    expect(listInterval(list(forging("done")))).toBe(false);
    expect(listInterval(undefined)).toBe(false);
  });
});
