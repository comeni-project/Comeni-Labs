import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { AuthoringSession } from "../../api/types";
import { CurrentFacts } from "./CurrentFacts";
import { FAKE_SESSION } from "./fake";

const show = (session: AuthoringSession, onUnits?: (type: string, on: boolean) => Promise<unknown>) =>
  render(<QueryClientProvider client={new QueryClient()}>
    <CurrentFacts session={session} open onUnits={onUnits} />
  </QueryClientProvider>);

const reads = (units: boolean) => ({ ...FAKE_SESSION, inputs: [{ key: "fastq.reads", type_id: "fastq.reads",
  present: true, origin: "person_said" as const, states: [], units }] }) as unknown as AuthoringSession;

describe("an input whose samples may span several lanes (issue 466)", () => {
  it("is said with one click on the input", async () => {
    const onUnits = vi.fn().mockResolvedValue(undefined);
    show(reads(false), onUnits);
    await userEvent.click(screen.getByLabelText("a sample may span several rows of fastq.reads (lanes)"));
    expect(onUnits).toHaveBeenCalledWith("fastq.reads", true);
  });

  it("shows what was said", () => {
    show(reads(true), vi.fn());
    expect((screen.getByLabelText("a sample may span several rows of fastq.reads (lanes)") as HTMLInputElement)
      .checked).toBe(true);
  });
});
