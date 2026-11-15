import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringTurn } from "../../api/types";
import { AgentThread } from "./AgentThread";
import { ChatPanel } from "./ChatPanel";
import { LivingNode } from "./LivingNode";
import { StepSheet } from "./StepSheet";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";

const AT = "2026-11-15T10:00:00Z";

const person = (seq: number, text: string): AuthoringTurn => ({
  seq, role: "person", state: "answered", text, blocks: [], base_revision: 0, at: AT,
});

const tool = (id: string, label: string) =>
  ({ id, kind: "tool", name: "read_tools", label, ok: true, summary: "" }) as const;

const agent = (seq: number, state: AuthoringTurn["state"], blocks: AuthoringTurn["blocks"]): AuthoringTurn => ({
  seq, role: "assistant", state, text: "", blocks, base_revision: 0, at: AT,
});

describe("the agent's thread", () => {
  it("shows each tool call while the turn runs, then folds them under How I got here", () => {
    const tools = [tool("t1", "Read the goal"), tool("t2", "Looked at aligners for reads"), tool("t3", "Built the pipeline")];
    const props = { onAnswer: vi.fn(), onRetry: vi.fn() };
    const { rerender } = render(
      <AgentThread turns={[person(1, "gene counts"), agent(2, "pending", tools)]} working {...props} />);
    for (const t of tools) expect(screen.getByText(t.label)).toBeVisible();
    expect(screen.queryByText(/How I got here/)).toBeNull();

    rerender(<AgentThread working={false} {...props} turns={[person(1, "gene counts"), agent(2, "answered", [
      ...tools, { id: "m", kind: "message", text: "I chose STAR because your reads are spliced." }])]} />);
    const fold = screen.getByRole("button", { name: /How I got here · 3 steps/ });
    expect(screen.queryByText("Read the goal")).toBeNull();
    expect(screen.getByText(/I chose STAR/)).toBeVisible();
    fireEvent.click(fold);
    expect(screen.getByText("Read the goal")).toBeVisible();
  });

  it("draws an agent question's options as buttons and sends the choice", () => {
    const onAnswer = vi.fn();
    render(<AgentThread working={false} onRetry={vi.fn()} onAnswer={onAnswer} turns={[person(1, "counts"),
      agent(2, "answered", [{ id: "a", kind: "ask", question_id: "q1", question: "Which organism?",
        shape: "options", options: ["human", "mouse"], unit: "", type_id: null }])]} />);
    const asked = screen.getByRole("group", { name: "Which organism?" });
    fireEvent.click(within(asked).getByRole("button", { name: "mouse" }));
    expect(onAnswer).toHaveBeenCalledWith("q1", "mouse");
  });

  it("offers Retry on a failed turn", () => {
    const onRetry = vi.fn();
    render(<AgentThread working={false} onAnswer={vi.fn()} onRetry={onRetry} turns={[person(1, "counts"),
      agent(2, "failed", [{ id: "f", kind: "notice", notice: "refusal", text: "The AI did not answer.", code: "MA0002" }])]} />);
    expect(screen.getByText("The AI did not answer.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledWith(2);
  });

  it("marks a step the AI chose until it is reviewed", () => {
    const node = (aiChoice: boolean) => (
      <LivingNode id="star_align" at={{ x: 0, y: 0 }} author="model" ports={[]} aiChoice={aiChoice} />);
    const { rerender } = render(node(true));
    expect(screen.getByText("chosen by the AI · review")).toBeVisible();
    rerender(node(false));
    expect(screen.queryByText("chosen by the AI · review")).toBeNull();

    const onReviewed = vi.fn();
    render(<StepSheet node="star_align" step={FAKE_STEPS.star_align} graph={FAKE_SESSION.graph}
                      onSetParam={vi.fn()} onEdit={vi.fn()} onClose={vi.fn()}
                      aiChoices={["chose star_align"]} onReviewed={onReviewed} />);
    fireEvent.click(screen.getByRole("button", { name: "Looks right" }));
    expect(onReviewed).toHaveBeenCalledWith("star_align");
  });

  it("keeps the chat height fixed: a new message does not resize the rail", () => {
    render(<ChatPanel session={FAKE_SESSION} sending={[]} composer="" onCompose={vi.fn()} onSay={vi.fn()}
                      onAnswer={vi.fn()} onRetry={vi.fn()} selected={null} onSelect={vi.fn()}
                      graph={FAKE_SESSION.graph} steps={{}} onEdit={vi.fn()} onSetParam={vi.fn()}
                      onReviewed={vi.fn()} notices={null} />);
    const rail = screen.getByRole("region", { name: "build panel" });
    expect(rail.style.height).toBe("var(--rail-h)");
    expect(screen.getByTestId("thread-scroll").style.overflowY).toBe("auto");
  });
});
