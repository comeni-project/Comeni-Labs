import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { initialAuthoring } from "./authoringReducer";
import { ChangeSetCard } from "./blocks/ChangeSetCard";
import { GoalCard } from "./blocks/GoalCard";
import { SettingCard } from "./blocks/SettingCard";
import { Composer } from "./Composer";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";
import { guidedStart } from "./guided";
import { GuidedLiving } from "./LivingBuilder";
import { LivingSurface } from "./LivingSurface";

/** Task 10: the cards a person answers, and the two ways the checkpoint says they must be
 *  answerable — with only the keyboard, and with a pointer that cannot hover. */

const mount = (ui: React.ReactElement) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

const blocksIn = (seq: number) => FAKE_SESSION.turns.find((t) => t.seq === seq)!.blocks;

// ── the checkpoint ────────────────────────────────────────────────────────────────────────

describe("completing a guided pipeline", () => {
  it("can be done with only the keyboard", async () => {
    const user = userEvent.setup();
    mount(<GuidedLiving />);

    /** Tab until focus lands on the control, as a keyboard user would, then press Enter. */
    const reach = async (testId: string) => {
      for (let i = 0; i < 80; i += 1) {
        if (document.activeElement?.getAttribute("data-testid") === testId) break;
        await user.tab();
      }
      expect(document.activeElement).toHaveAttribute("data-testid", testId);
      await user.keyboard("{Enter}");
    };

    await reach("accept-goal");
    for (const step of ["star_genomegenerate", "trimgalore", "star_align", "samtools_sort"]) {
      expect(screen.getByTestId(`living-node-${step}`)).toHaveAttribute("data-ghost", "true");
      await reach("accept-step");
      expect(screen.getByTestId(`living-node-${step}`)).not.toHaveAttribute("data-ghost");
    }
    expect(screen.getByTestId("living-status")).toHaveTextContent("complete");
    expect(screen.queryByTestId("accept-step")).toBeNull();
  });

  it("can be done with a touch pointer that never hovers, previewing an option on the way", async () => {
    const user = userEvent.setup();
    mount(<GuidedLiving />);
    const tap = (element: Element) => user.pointer({ keys: "[TouchA]", target: element });

    await tap(screen.getByTestId("accept-goal"));
    for (const step of ["star_genomegenerate", "trimgalore", "star_align"]) {
      await tap(screen.getByTestId("accept-step"));
      expect(screen.getByTestId(`living-node-${step}`)).not.toHaveAttribute("data-ghost");
    }

    // The sorter offers an alternative. With no hover, Preview is the way to see it in the slot.
    await tap(screen.getByTestId("preview-alt_1"));
    expect(screen.getByTestId("node-name-samtools_sort")).toHaveTextContent("SAMTOOLS_SORMADUP");
    expect(screen.getByTestId("living-node-samtools_sort")).toHaveTextContent("INSTEAD");
    await tap(screen.getByTestId("preview-alt_1"));
    expect(screen.getByTestId("node-name-samtools_sort")).toHaveTextContent("SAMTOOLS_SORT");

    await tap(screen.getByTestId("accept-step"));
    expect(screen.getByTestId("living-status")).toHaveTextContent("complete");
  });

  it("names every choice for a screen reader", () => {
    mount(<GuidedLiving />);
    expect(screen.getByRole("button", { name: "That's right" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "add to what you want" })).toBeInTheDocument();
  });
});

// ── the goal card ─────────────────────────────────────────────────────────────────────────

describe("the goal card", () => {
  it("is drawn once — as the card — and not again in the turn that produced it", () => {
    // **Found by rendering, not by reading.** The first version drew the goal twice: read-only in
    // its turn and editable beneath, which is two goals on a screen whose job is to check one.
    mount(<GuidedLiving />);
    expect(screen.getAllByRole("region", { name: "the goal as understood" })).toHaveLength(1);
    expect(screen.getByTestId("canvas-empty")).toHaveTextContent("Nothing built yet");
  });

  const goal = guidedStart().pending_proposal!;
  const vocabulary = { "counts.matrix": ["gene_level"], "qc.report": ["aggregated"] };

  it("confirms an unedited goal without sending one", () => {
    const onConfirm = vi.fn();
    mount(<GoalCard proposal={goal} vocabulary={vocabulary} busy={false} onConfirm={onConfirm}
                    onReject={vi.fn()} />);
    fireEvent.click(screen.getByTestId("accept-goal"));
    expect(onConfirm).toHaveBeenCalledWith();
  });

  it("sends the edited goal when a field changed — and only from the declared vocabulary", () => {
    const onConfirm = vi.fn();
    mount(<GoalCard proposal={goal} vocabulary={vocabulary} busy={false} onConfirm={onConfirm}
                    onReject={vi.fn()} />);
    const add = screen.getByRole("combobox", { name: "add to what you want" });
    expect(within(add).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "+ add a type",
      "qc.report",
    ]);
    fireEvent.change(add, { target: { value: "qc.report" } });
    fireEvent.click(screen.getByTestId("accept-goal"));
    expect(onConfirm.mock.calls[0][0].want).toEqual(["counts.matrix", "qc.report"]);
  });

  it("keeps the states of an input the person did not touch", () => {
    const withStates = {
      ...goal,
      block: { ...goal.block, goal: { have: [{ type_id: "fastq.reads", states: ["trimmed"] }],
        want: ["counts.matrix"] } },
    } as typeof goal;
    const onConfirm = vi.fn();
    mount(<GoalCard proposal={withStates} vocabulary={vocabulary} busy={false}
                    onConfirm={onConfirm} onReject={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "remove counts.matrix from what you want" }));
    fireEvent.click(screen.getByTestId("accept-goal"));
    expect(onConfirm.mock.calls[0][0].have).toEqual([{ type_id: "fastq.reads", states: ["trimmed"] }]);
  });
});

// ── settings and change sets ──────────────────────────────────────────────────────────────

describe("a setting the engine could not settle", () => {
  it("offers an open field when no values are declared, and applies what was typed", () => {
    const block = blocksIn(3).find((b) => b.kind === "setting_request")!;
    const onApply = vi.fn();
    if (block.kind !== "setting_request") throw new Error("fixture moved");
    mount(<SettingCard block={block} onApply={onApply} />);
    fireEvent.change(screen.getByPlaceholderText("type a value"), { target: { value: "illumina" } });
    fireEvent.click(screen.getByTestId("apply-seq_platform"));
    expect(onApply).toHaveBeenCalledWith("star_align", "seq_platform", "illumina");
  });

  it("offers the declared values as a choice when there are some", () => {
    const block = { ...blocksIn(3).find((b) => b.kind === "setting_request")!,
      options: [{ id: "o1", label: "bai", recommended: true }, { id: "o2", label: "csi", recommended: false }] };
    if (block.kind !== "setting_request") throw new Error("fixture moved");
    mount(<SettingCard block={block} onApply={vi.fn()} />);
    expect(screen.getByRole("radiogroup", { name: "values for seq_platform" })).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("type a value")).toBeNull();
  });
});

describe("a change that touches several steps", () => {
  it("shows every affected step and needs a second, named press before applying", () => {
    const block = blocksIn(3).find((b) => b.kind === "change_set")!;
    if (block.kind !== "change_set") throw new Error("fixture moved");
    const onApply = vi.fn();
    mount(<ChangeSetCard block={block} onApply={onApply} />);

    const affected = screen.getByRole("list", { name: "affected steps" });
    expect(affected).toHaveTextContent("STAR_ALIGN removed");
    expect(affected).toHaveTextContent("HISAT2_ALIGN proposed next");

    fireEvent.click(screen.getByTestId("apply-change"));
    expect(onApply).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Remove 1 step" }));
    expect(onApply).toHaveBeenCalledWith(block);
  });
});

// ── the composer and the follow-up ────────────────────────────────────────────────────────

describe("saying something", () => {
  it("sends on Enter and keeps Shift+Enter for a new line", () => {
    const onSend = vi.fn();
    const onChange = vi.fn();
    mount(<Composer value="why STAR?" onChange={onChange} onSend={onSend} />);
    const box = screen.getByTestId("composer");
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("why STAR?");
  });

  it("draws a follow-up at once, marked as sending, before the transcript holds it", () => {
    const quiet = { ...FAKE_SESSION, turns: FAKE_SESSION.turns.filter((t) => t.state !== "pending") };
    mount(
      <LivingSurface
        session={quiet as AuthoringSession}
        graph={quiet.graph}
        steps={FAKE_STEPS}
        state={{ ...initialAuthoring, snapshot: quiet as AuthoringSession, saying: "and the sorter?" }}
        preview={null}
        busy={() => false}
        onAccept={vi.fn()} onReject={vi.fn()} onPreviewOption={vi.fn()} onSelect={vi.fn()}
        onCompose={vi.fn()} onSay={vi.fn()} onRetry={vi.fn()} onAddStep={vi.fn()}
        onDismiss={vi.fn()} onSetParam={vi.fn()} onApplyChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("saying")).toHaveTextContent("and the sorter?");
    expect(screen.getByText("sending…")).toBeInTheDocument();
  });
});

// ── bidirectional selection ───────────────────────────────────────────────────────────────

describe("the card and the canvas point at each other", () => {
  it("selecting the proposal card selects its step on the canvas", async () => {
    mount(<GuidedLiving />);
    await act(async () => fireEvent.click(screen.getByTestId("accept-goal")));
    fireEvent.click(screen.getByTestId("select-step"));
    expect(screen.getByTestId("living-node-star_genomegenerate")).toHaveAttribute("aria-pressed", "true");
  });

  it("selecting a step on the canvas marks its decision in the log", async () => {
    mount(<GuidedLiving />);
    await act(async () => fireEvent.click(screen.getByTestId("accept-goal")));
    await act(async () => fireEvent.click(screen.getByTestId("accept-step")));
    fireEvent.click(screen.getByTestId("living-node-star_genomegenerate"));
    expect(screen.getByRole("button", { name: /STAR_GENOMEGENERATE step 1/ }))
      .toHaveAttribute("aria-pressed", "true");
  });
});
