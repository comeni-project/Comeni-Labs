import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AnsweredStep } from "../useBuilder";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";
import { StepSheet } from "./StepSheet";

function sheet(overrides = {}) {
  const props = {
    node: "star_align", step: FAKE_STEPS.star_align as AnsweredStep, graph: FAKE_SESSION.graph, requests: [],
    onSetParam: vi.fn(), onEdit: vi.fn(), onClose: vi.fn(), ...overrides,
  };
  render(<QueryClientProvider client={new QueryClient()}><StepSheet {...props} /></QueryClientProvider>);
  return props;
}

describe("a step opened over the conversation (one builder plan 3)", () => {
  it("groups its values by how they were decided, the rule's folded", () => {
    sheet();
    const measured = screen.getByRole("region", { name: "Measured" });
    expect(within(measured).getByText("sjdbOverhang")).toBeInTheDocument();
    const settled = screen.getByRole("region", { name: "Settled by a rule" });
    expect(within(settled).queryByText("outSAMtype")).toBeNull();
    fireEvent.click(within(settled).getByRole("button", { name: /show/ }));
    expect(within(settled).getByText("outSAMtype")).toBeInTheDocument();
    expect(within(settled).getByText("twopassMode")).toBeInTheDocument();
  });

  it("shows a value's reason in place", () => {
    sheet();
    fireEvent.click(screen.getByRole("button", { name: /sjdbOverhang/ }));
    expect(screen.getByText("Read length is 151 bp, measured from your files, minus one.")).toBeInTheDocument();
  });

  it("asks what still needs the person first", () => {
    const open = { name: "strandedness", value: null, via: "ext", tier: 4, reason: "", because: "",
      axis_reason: "", optional: false, premise: [] };
    sheet({ step: { ...FAKE_STEPS.star_align, settings: [...FAKE_STEPS.star_align.settings, open] } });
    expect(screen.getByRole("region", { name: "Needs you" })).toHaveTextContent("strandedness");
  });

  it("closes from × and from Back to the conversation", () => {
    const p = sheet();
    fireEvent.click(screen.getByRole("button", { name: "Close the step" }));
    fireEvent.click(screen.getByRole("button", { name: "‹ Back to the conversation" }));
    expect(p.onClose).toHaveBeenCalledTimes(2);
  });
});
