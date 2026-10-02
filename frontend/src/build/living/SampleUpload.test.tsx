import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Refused } from "../../api/client";
import type { SampleInspected } from "../../api/types";
import { SampleResult, SampleUpload } from "./blocks/SampleUpload";

/** Issue 134: a person who is not sure uploads one file or a pair and sees what it measured. */

const fq = (name: string) => new File(["@r\nACGT\n+\nIIII\n"], name);
const LABEL = "Not sure: upload a sample and I'll measure it";

const result = (extra: Partial<SampleInspected> = {}): SampleInspected => ({
  outcome: "measured", type_id: "fastq.reads", reason: null, recorded: ["read_length"], kept: [],
  disagreed: [],
  steps: ["read the first 4 MB of 2 file(s)", "unpacked gzip", "confirmed FASTQ", "measured 3 fact(s)"],
  facts: [{
    measurement: "read_length", value: 151, undetermined: null,
    pieces: ["fastq@1.0.0", "read_length@1.0.0"], evidence: { records: 8412, share: 0.97 },
  }],
  session: { pending_proposal: { id: "p-gap" } } as never,
  ...extra,
});

function setup(onUpload = vi.fn().mockResolvedValue(result()), onAnswered = vi.fn()) {
  render(
    <SampleUpload proposalId="p-gap" label={LABEL} busy={false} onUpload={onUpload}
      onAnswered={onAnswered} />,
  );
  return { onUpload, onAnswered };
}

describe("uploading a sample", () => {
  it("lists a picked pair with sizes before anything is sent", async () => {
    const { onUpload } = setup();
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("s_R1.fq.gz"), fq("s_R2.fq.gz")]);
    expect(screen.getByText("s_R1.fq.gz")).toBeTruthy();
    expect(screen.getByText("s_R2.fq.gz")).toBeTruthy();
    expect(onUpload).not.toHaveBeenCalled();
  });

  it("measures and says what it found and how, when the question stays", async () => {
    const { onUpload, onAnswered } = setup();
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("s_R1.fq.gz"), fq("s_R2.fq.gz")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    expect(onUpload).toHaveBeenCalledWith([expect.any(File), expect.any(File)]);
    expect(await screen.findByText(/read_length 151/)).toBeTruthy();
    expect(screen.getByText(/fastq 1\.0\.0 · 8,412 reads, 97% at 151/)).toBeTruthy();
    expect(onAnswered).not.toHaveBeenCalled();
  });

  it("hands the result up when it answered this question", async () => {
    const answered = result({ session: { pending_proposal: { id: "p-next" } } as never });
    const { onAnswered } = setup(vi.fn().mockResolvedValue(answered));
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("s_R1.fq")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    await waitFor(() => expect(onAnswered).toHaveBeenCalledWith(answered, ["s_R1.fq"]));
  });

  it("refuses three files on the card, before any request", async () => {
    const { onUpload } = setup();
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("a.fq"), fq("b.fq"), fq("c.fq")]);
    expect(screen.getByRole("alert").textContent).toMatch(/3 files: upload one file, or a pair/);
    expect(screen.queryByRole("button", { name: "Measure" })).toBeNull();
    expect(onUpload).not.toHaveBeenCalled();
  });

  it("says why a file could not be read", async () => {
    setup(vi.fn().mockResolvedValue(result({
      outcome: "unreadable", facts: [], recorded: [],
      reason: "x.fastq is named like fastq, but does not start like one",
    })));
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("x.fastq")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    expect(await screen.findByText(/does not start like one/)).toBeTruthy();
    expect(screen.getByText(/nothing was recorded/i)).toBeTruthy();
  });

  it("says when nothing reads the type", async () => {
    setup(vi.fn().mockResolvedValue(result({
      outcome: "no_inspector", facts: [], recorded: [], reason: "nothing reads this type yet",
    })));
    // A person can pick any file through the dialog's "All files"; `accept` only guides.
    const user = userEvent.setup({ applyAccept: false });
    await user.upload(screen.getByLabelText(LABEL), [fq("r.bam")]);
    await user.click(screen.getByRole("button", { name: "Measure" }));
    expect(await screen.findByText(/nothing reads \.bam files yet/)).toBeTruthy();
  });

  it("shows an undetermined fact with its reason", async () => {
    setup(vi.fn().mockResolvedValue(result({
      recorded: [],
      facts: [{ measurement: "read_length", value: null, undetermined: "lengths vary: 139–151, trimmed?",
        pieces: ["fastq@1.0.0", "read_length@1.0.0"], evidence: {} }],
    })));
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("t.fq")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    expect(await screen.findByText(/lengths vary: 139–151, trimmed\?/)).toBeTruthy();
  });

  it("is never stuck inspecting when the request fails", async () => {
    setup(vi.fn().mockRejectedValue(new Error("Failed to fetch")));
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("a.fq")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    await waitFor(() => expect(screen.getByText(/could not be sent/i)).toBeTruthy());
    expect(screen.queryByText(/measuring/i)).toBeNull();
    expect(screen.getByLabelText(LABEL)).toBeTruthy();
  });

  it("shows a refusal's own sentence", async () => {
    setup(vi.fn().mockRejectedValue(new Refused("MI0213: the protection level is sealed")));
    await userEvent.upload(screen.getByLabelText(LABEL), [fq("a.fq")]);
    await userEvent.click(screen.getByRole("button", { name: "Measure" }));
    expect(await screen.findByText(/MI0213: the protection level is sealed/)).toBeTruthy();
  });
});

describe("what a sample measured", () => {
  it("shows a difference from what the person said, and that their word stands", () => {
    render(<SampleResult result={result({ kept: ["paired"], disagreed: ["paired"], facts: [
      ...result().facts,
      { measurement: "paired", value: true, undetermined: null, pieces: ["fastq@1.0.0", "paired@1.0.0"],
        evidence: { pairs: 4206, agreeing: 4206 } },
    ] })} files={["s_R1.fq.gz", "s_R2.fq.gz"]} />);
    expect(screen.getByText(/the sample reads it as yes/)).toBeTruthy();
    expect(screen.getByText(/what you said stands/i)).toBeTruthy();
  });
});
