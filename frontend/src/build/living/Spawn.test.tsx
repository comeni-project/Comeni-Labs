import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { initialAuthoring } from "./authoringReducer";
import { COLLECT_CHANNELS, COLLECT_SESSION, COLLECT_STEPS, FAKE_SESSION, FAKE_STEPS } from "./fake";
import { useFirstArrival } from "./LivingBuilder";
import { LivingCanvas } from "./LivingCanvas";
import { LivingSurface } from "./LivingSurface";
import { lastSeen, markSeen, REVEAL_CAP_MS, REVEAL_STEP_MS, revealPlan } from "./replay";

/** Task 12, the browser half: Spawn is a policy, not a page — and a pipeline that arrives built
 *  is revealed once, in order, and never again on reload. */

afterEach(() => window.sessionStorage.clear());

const mount = (ui: React.ReactElement) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

/** A Spawn session that arrived with every step already accepted. */
function arrived(mode: "spawn" | "build" = "spawn"): AuthoringSession {
  const steps = ["star_genomegenerate", "trimgalore", "star_align", "samtools_sort"];
  return {
    ...FAKE_SESSION,
    id: `arrived-${mode}`,
    mode,
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

  it("reveals a Spawn pipeline that arrived built, and shows it at once on reload", () => {
    const session = arrived();
    const first = renderHook(() => useFirstArrival(session.id, session));
    expect(Object.keys(first.result.current).sort()).toEqual(
      ["samtools_sort", "star_align", "star_genomegenerate", "trimgalore"],
    );
    first.unmount();

    const reload = renderHook(() => useFirstArrival(session.id, session));
    expect(reload.result.current).toEqual({});
  });

  it("never replays a Build session — a person watched every step arrive", () => {
    const session = arrived("build");
    const { result } = renderHook(() => useFirstArrival(session.id, session));
    expect(result.current).toEqual({});
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

describe("a mode is a policy, not a page", () => {
  it("renders the same regions and controls for Build and Spawn — only the mode says which", () => {
    const tree = (mode: "build" | "spawn") => {
      const session = { ...FAKE_SESSION, mode } as AuthoringSession;
      const view = mount(
        <LivingSurface session={session} graph={session.graph} steps={FAKE_STEPS}
                       state={{ ...initialAuthoring, snapshot: session }} preview={null}
                       busy={() => false} onAccept={vi.fn()} onReject={vi.fn()}
                       onPreviewOption={vi.fn()} onSelect={vi.fn()} onCompose={vi.fn()}
                       onSay={vi.fn()} onRetry={vi.fn()} onAddStep={vi.fn()} onDismiss={vi.fn()}
                       onSetParam={vi.fn()} onApplyChange={vi.fn()} />,
      );
      const ids = Array.from(view.container.querySelectorAll("[data-testid]"))
        .map((el) => el.getAttribute("data-testid"))
        .sort();
      const mode_ = screen.getByTestId("mode").textContent;
      view.unmount();
      return { ids, mode_ };
    };
    const build = tree("build");
    const spawn = tree("spawn");
    expect(spawn.ids).toEqual(build.ids);
    expect([build.mode_, spawn.mode_]).toEqual(["build", "spawn"]);
  });

  it("says a goal the policy accepted was read by the model, not chosen by the person", () => {
    const session = {
      ...FAKE_SESSION,
      mode: "spawn",
      history: FAKE_SESSION.history.map((d) => (d.kind === "goal" ? { ...d, by: "model" } : d)),
      turns: FAKE_SESSION.turns.filter((t) => t.state !== "pending"),
    } as AuthoringSession;
    mount(
      <LivingSurface session={session} graph={session.graph} steps={FAKE_STEPS}
                     state={{ ...initialAuthoring, snapshot: session }} preview={null}
                     busy={() => false} onAccept={vi.fn()} onReject={vi.fn()}
                     onPreviewOption={vi.fn()} onSelect={vi.fn()} onCompose={vi.fn()}
                     onSay={vi.fn()} onRetry={vi.fn()} onAddStep={vi.fn()} onDismiss={vi.fn()}
                     onSetParam={vi.fn()} onApplyChange={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /Goal confirmed/ })).toHaveTextContent("read by the model");
  });
});
