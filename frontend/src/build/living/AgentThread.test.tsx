import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringTurn } from "../../api/types";
import { AgentThread } from "./AgentThread";
import { ChatPanel } from "./ChatPanel";
import { LivingNode } from "./LivingNode";
import { StepCard } from "./StepCard";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";

const AT = "2026-11-15T10:00:00Z";

const person = (seq: number, text: string): AuthoringTurn => ({
  seq, role: "person", state: "answered", text, blocks: [], base_revision: 0, at: AT,
});

const tool = (id: string, label: string, running = false) =>
  ({ id, kind: "tool", name: "read_tools", label, ok: true, summary: "", running }) as const;

const said = (id: string, text: string, narration = false) =>
  ({ id, kind: "message", text, narration }) as const;

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
      ...tools, said("m", "I chose STAR because your reads are spliced.")])]} />);
    const fold = screen.getByRole("button", { name: /How I got here · 3 steps/ });
    expect(screen.queryByText("Read the goal")).toBeNull();
    expect(screen.getByText(/I chose STAR/)).toBeVisible();
    fireEvent.click(fold);
    expect(screen.getByText("Read the goal")).toBeVisible();
  });

  it("tells what it is doing as it works: its words in order with its tools, and the tool running", () => {
    const props = { onAnswer: vi.fn(), onRetry: vi.fn() };
    const { rerender } = render(<AgentThread working {...props} turns={[person(1, "counts"),
      agent(2, "pending", [said("n1", "Let me see which aligners fit paired reads.", true),
        tool("t1", "Looking at the aligners for fastq.reads", true)])]} />);
    const live = screen.getByRole("status", { name: "working" });
    expect(live.textContent).toMatch(/Let me see which aligners.*Looking at the aligners for fastq\.reads/);
    expect(within(live).getByTestId("running")).toHaveTextContent("Looking at the aligners for fastq.reads");
    expect(within(live).queryByText("Thinking…")).toBeNull();

    // Between tools the model itself is answering: that is thinking.
    rerender(<AgentThread working {...props} turns={[person(1, "counts"),
      agent(2, "pending", [said("n1", "Let me see which aligners fit paired reads.", true),
        tool("t1", "Looked at the aligners for fastq.reads")])]} />);
    expect(within(screen.getByRole("status", { name: "working" })).getByText("Thinking…")).toBeVisible();

    // Answered: the narration folds with the tools, and only the answer is prose.
    rerender(<AgentThread working={false} {...props} turns={[person(1, "counts"),
      agent(2, "answered", [said("n1", "Let me see which aligners fit paired reads.", true),
        tool("t1", "Looked at the aligners for fastq.reads"), said("m", "STAR it is.")])]} />);
    expect(screen.queryByText("Let me see which aligners fit paired reads.")).toBeNull();
    expect(screen.getByText("STAR it is.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /How I got here · 1 step/ }));
    expect(screen.getByText("Let me see which aligners fit paired reads.")).toBeVisible();
  });

  it("fades a new thread item in, and leaves what was there when the page opened still", () => {
    const props = { onAnswer: vi.fn(), onRetry: vi.fn(), working: false };
    const first = [person(1, "counts"), agent(2, "answered", [said("m", "Built it.")])];
    const { rerender } = render(<AgentThread {...props} turns={first} />);
    const items = () => Array.from(screen.getByRole("log", { name: "conversation" }).children);
    expect(items().some((li) => li.classList.contains("agent-arrive"))).toBe(false);
    // The person's own words already faded in as they were sent; the agent's reply fades in.
    rerender(<AgentThread {...props} turns={[...first, person(3, "and QC?"), agent(4, "pending", [])]} />);
    expect(items().map((li) => li.classList.contains("agent-arrive"))).toEqual([false, false, false, true]);
  });

  it("links an answer to the steps its tools touched, and says nothing else about it (issue 499)", () => {
    const onStep = vi.fn();
    render(<AgentThread working={false} onAnswer={vi.fn()} onRetry={vi.fn()} onStep={onStep} turns={[
      person(1, "why STAR?"),
      agent(2, "answered", [{ ...tool("t1", "Read the step star_align"), node: "star_align" },
        { ...tool("t2", "Read the goal"), node: undefined }, { ...tool("t3", "Read the step star_align"), node: "star_align" },
        said("m", "STAR suits long reads.")])]} />);
    const links = screen.getByRole("group", { name: "what this answer used" });
    expect(screen.queryByText(/the AI's words/)).toBeNull();
    const steps = within(links).getAllByRole("button");
    expect(steps.map((b) => b.textContent)).toEqual(["STAR_ALIGN"]);
    fireEvent.click(steps[0]);
    expect(onStep).toHaveBeenCalledWith("star_align");
  });

  it("draws bullet lines as a list even under a lead-in line (walk 2026-11-15)", () => {
    render(<AgentThread working={false} onAnswer={vi.fn()} onRetry={vi.fn()} turns={[person(1, "why?"),
      agent(2, "answered", [said("m", "The main trade-off is:\n- STAR: fast, more RAM\n- HISAT2: less RAM")])]} />);
    expect(screen.getByText("The main trade-off is:")).toBeInTheDocument();
    const items = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toEqual(expect.arrayContaining(["STAR: fast, more RAM", "HISAT2: less RAM"]));
    expect(screen.queryByText(/^- STAR/)).toBeNull();
  });

  it("draws a fenced code block as code, not as backticks (walk 2026-11-15)", () => {
    render(<AgentThread working={false} onAnswer={vi.fn()} onRetry={vi.fn()} turns={[person(1, "how?"),
      agent(2, "answered", [said("m", "Like this:\n\n```bash\nsome_tool sample.bam\n```\n\nThat is all.")])]} />);
    const code = screen.getByText("some_tool sample.bam");
    expect(code.closest("pre")).not.toBeNull();
    expect(screen.queryByText(/```/)).toBeNull();
    expect(screen.getByText("That is all.")).toBeInTheDocument();
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
    expect(screen.getByTestId("node-ai-star_align")).toHaveTextContent(/^AI$/);
    expect(screen.getByTestId("node-ai-star_align")).toHaveAttribute("title", expect.stringMatching(/not reviewed/));
    rerender(node(false));
    expect(screen.queryByTestId("node-ai-star_align")).toBeNull();

    const onReviewed = vi.fn();
    render(<StepCard node="star_align" kind="settings" onKind={vi.fn()} step={FAKE_STEPS.star_align} graph={FAKE_SESSION.graph}
                      onSetParam={vi.fn()} onEdit={vi.fn()} onClose={vi.fn()}
                      aiChoices={[{ what: "chose star_align" }]} onReviewed={onReviewed} />);
    fireEvent.click(screen.getByRole("button", { name: "Looks right" }));
    expect(onReviewed).toHaveBeenCalledWith("star_align");
  });

  it("keeps the chat height fixed: a new message does not resize the rail", () => {
    render(<ChatPanel session={FAKE_SESSION} sending={[]} composer="" onCompose={vi.fn()} onSay={vi.fn()}
                      onAnswer={vi.fn()} onRetry={vi.fn()} notices={null} />);
    const rail = screen.getByRole("region", { name: "build panel" });
    expect(rail.style.height).toBe("var(--rail-h)");
    expect(screen.getByTestId("thread-scroll").style.overflowY).toBe("auto");
  });
});
