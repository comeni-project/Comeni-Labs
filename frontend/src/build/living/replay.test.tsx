import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { COLLECT_CHANNELS, COLLECT_SESSION, COLLECT_STEPS, FAKE_SESSION } from "./fake";
import { useFirstArrival } from "./LivingBuilder";
import { LivingCanvas } from "./LivingCanvas";
import { lastSeen, markSeen, REVEAL_CAP_MS, REVEAL_STEP_MS, revealPlan } from "./replay";

/** The first-arrival reveal: steps placed before this tab looked are revealed once, in order,
 *  and never again on reload. Spawn's once; every session's since 14.7.8.3b, because a walk paced
 *  *stop only where needed* places many steps at once (spec §13 of the consultant build). Restored
 *  from the deleted `Spawn.test.tsx` by the final review of 3b run 1. */

afterEach(() => window.sessionStorage.clear());

const mount = (ui: React.ReactElement) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

/** A session that arrived with every step already accepted. */
function arrived(): AuthoringSession {
  const steps = ["star_genomegenerate", "trimgalore", "star_align", "samtools_sort"];
  return {
    ...FAKE_SESSION,
    id: "arrived",
    phase: "complete",
    pending_proposal: null,
    history: steps.map((node, i) => ({
      id: `h${i}`, kind: "step", state: "accepted", by: "resolver", chosen_option: "keep",
      chosen_contract: "x@1", at: `2026-09-13T12:0${i}:00+00:00`,
      block: { kind: "step_proposal", id: `step-${node}`, node, contract: "x@1", consumes: [],
        produces: [], reason: "", tier: 2, alternatives: [] },
    })),
  } as AuthoringSession;
}

describe("the reveal plan", () => {
  it("brings a column in together, one pause after the column before it", () => {
    const x: Record<string, number> = { a: 40, b: 40, c: 264, d: 488 };
    expect(revealPlan(["a", "b", "c", "d"], (n) => x[n])).toEqual({
      a: 0, b: 0, c: REVEAL_STEP_MS, d: 2 * REVEAL_STEP_MS,
    });
  });

  it("never takes longer than the cap, however long the pipeline", () => {
    const steps = Array.from({ length: 60 }, (_, i) => `s${i}`);
    const plan = revealPlan(steps, (n) => Number(n.slice(1)) * 224);
    expect(Math.max(...Object.values(plan))).toBeLessThanOrEqual(REVEAL_CAP_MS);
  });
});

describe("first arrival and reload", () => {
  it("remembers only a count, and treats anything else as a first arrival", () => {
    expect(lastSeen("s")).toBeNull();
    markSeen("s", 4);
    expect(window.sessionStorage.getItem("comeni-living-seen:s")).toBe("4");
    expect(lastSeen("s")).toBe(4);
    window.sessionStorage.setItem("comeni-living-seen:s", "the transcript");
    expect(lastSeen("s")).toBeNull();
  });

  it("reveals a pipeline that arrived built in a fresh tab, and shows it at once on reload", () => {
    const session = arrived();
    const first = renderHook(() => useFirstArrival(session.id, session));
    expect(Object.keys(first.result.current).sort()).toEqual(
      ["samtools_sort", "star_align", "star_genomegenerate", "trimgalore"],
    );
    first.unmount();

    const reload = renderHook(() => useFirstArrival(session.id, session));
    expect(reload.result.current).toEqual({});
  });

  it("draws a revealing step with its delay, so it waits its turn", () => {
    mount(
      <LivingCanvas graph={COLLECT_SESSION.graph} ghost={null} positions={COLLECT_SESSION.placement}
                    steps={COLLECT_STEPS} channels={COLLECT_CHANNELS} authors={{}} selected={null}
                    onSelect={vi.fn()} reveal={{ multiqc: 360 }} />,
    );
    const node = screen.getByTestId("living-node-multiqc");
    expect(node).toHaveClass("living-reveal");
    expect(node.style.animationDelay).toBe("360ms");
    expect(screen.getByTestId("living-node-fastqc")).not.toHaveClass("living-reveal");
  });
});
