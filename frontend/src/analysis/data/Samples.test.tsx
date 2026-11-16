import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { analysis } from "./fixtures";
import { Samples } from "./Samples";
import type { AnalysisData } from "./useAnalysisData";

function actions() {
  return { setRule: vi.fn(), confirmRule: vi.fn(), undoFix: vi.fn(), setColumn: vi.fn() };
}

function samples(data: AnalysisData = analysis(), act = actions()) {
  render(<Samples data={data} {...act} />);
  return act;
}

const withRule = (over: Partial<AnalysisData> = {}) => analysis({
  scan: { state: "done", done: 5, total: 5, error: null,
          examples: [["L01_R1.fq.gz", "L01", "1"], ["L01_R2.fq.gz", "L01", "2"], ["L02_R1.fq.gz", "L02", "1"]] },
  rule_result: { samples: 2, unfit: 1, examples: [] }, ...over });

it("reading rule shows three examples and the sample and unfit counts", () => {
  samples(withRule());
  const rule = screen.getByRole("region", { name: "How the samples were read" });
  expect(within(rule).getAllByTestId("rule-example")).toHaveLength(3);
  expect(within(rule).getByText(/2 samples/)).toBeTruthy();
  expect(within(rule).getByText(/1 file did not fit/)).toBeTruthy();
});

it("looks right confirms; change the rule submits a pattern", () => {
  const act = samples(withRule());
  fireEvent.click(screen.getByRole("button", { name: "Looks right" }));
  expect(act.confirmRule).toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Change the rule" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Reading rule" }), { target: { value: "{sample}_R{read}.fq.gz" } });
  fireEvent.click(screen.getByRole("button", { name: "Use this rule" }));
  expect(act.setRule).toHaveBeenCalledWith("{sample}_R{read}.fq.gz");
});

it("an AI rule is tagged AI until confirmed", () => {
  samples(withRule({ rule: { pattern: "{sample}_{read}.fq", origin: "ai", confirmed: false, reason: "names" } }));
  expect(within(screen.getByRole("region", { name: "How the samples were read" })).getByText("AI")).toBeTruthy();
});

it("columns follow the data: paired reads get read 1 and read 2, assemblies one file", () => {
  samples();
  expect(screen.getByRole("columnheader", { name: "Read 1" })).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "Read 2" })).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: "Read length" })).toBeTruthy();
  const one = analysis({ samples: [{ name: "a", files: ["/d/a.fasta"], outcome: "measured", type_id: null,
                                     left_out: false, facts: [] }] } as Partial<AnalysisData>);
  document.body.innerHTML = "";
  samples(one);
  expect(screen.getByRole("columnheader", { name: "File" })).toBeTruthy();
  expect(screen.queryByRole("columnheader", { name: "Read 2" })).toBeNull();
});

it("to check filter shows only flagged samples", () => {
  const data = analysis({ checks: [{ sample: "L02", kind: "odd_fact", detail: "Read length is 50",
                                     fixes: [{ kind: "leave_out", sample: "L02", file: null, by: "you", reason: null }] }] });
  samples(data);
  fireEvent.click(screen.getByRole("button", { name: /To check/ }));
  const names = screen.getAllByRole("row").slice(1).map((r) => r.querySelector("[role=cell]")?.textContent);
  expect(names).toEqual(["L02"]);
});

it("a left-out sample says so and can be brought back", () => {
  const data = analysis({
    samples: [{ ...analysis().samples[0], left_out: true }, analysis().samples[1]],
    fixes: [{ kind: "leave_out", sample: "L01", file: null, by: "you", reason: null }],
  });
  const act = samples(data);
  fireEvent.click(screen.getByRole("button", { name: "Bring L01 back" }));
  expect(act.undoFix).toHaveBeenCalledWith(0);
});

it("add column prompts for a name and stores values", () => {
  const act = samples(analysis({ columns: { condition: { L01: "treated" } } }));
  expect(screen.getByRole("columnheader", { name: "condition" })).toBeTruthy();
  fireEvent.change(screen.getByRole("textbox", { name: "condition for L02" }), { target: { value: "control" } });
  fireEvent.blur(screen.getByRole("textbox", { name: "condition for L02" }));
  expect(act.setColumn).toHaveBeenCalledWith("condition", { L01: "treated", L02: "control" });
  fireEvent.click(screen.getByRole("button", { name: "+ Add column" }));
  fireEvent.change(screen.getByRole("textbox", { name: "New column" }), { target: { value: "batch" } });
  fireEvent.click(screen.getByRole("button", { name: "Add" }));
  expect(act.setColumn).toHaveBeenCalledWith("batch", {});
});
