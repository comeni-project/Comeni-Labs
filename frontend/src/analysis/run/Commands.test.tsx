import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { makeClient } from "../../app/queryClient";
import { Commands } from "./Commands";

/** The Console's Commands (#511): found by what they do, Run only for one that only reads. */
const LIST = { commands: [
  { name: "How each step went", does: "Every task's step and status.", command: "nextflow log wiener-{run}", group: "This run", read_only: true },
  { name: "Resume the run", does: "Starts again from where it stopped.", command: "nextflow run . -resume", group: "This run", read_only: false },
  { name: "Memory free on this machine", does: "How much memory is left.", command: "free -h", group: "Disk and machine", read_only: true },
] };

afterEach(() => vi.unstubAllGlobals());

function open() {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, json: async () => LIST })));
  const onInsert = vi.fn(), onRun = vi.fn(), onClose = vi.fn();
  render(<QueryClientProvider client={makeClient()}>
    <Commands runId="r42" onInsert={onInsert} onRun={onRun} onClose={onClose} />
  </QueryClientProvider>);
  return { onInsert, onRun, onClose };
}

it("finds a command by what it does, with this run's id in it", async () => {
  const { onRun } = open();
  fireEvent.change(await screen.findByRole("textbox", { name: "Search commands" }), { target: { value: "status" } });
  const row = await screen.findByTestId("command-How each step went");
  expect(screen.queryByTestId("command-Memory free on this machine")).toBeNull();
  fireEvent.click(within(row).getByRole("button", { name: "Run" }));
  expect(onRun).toHaveBeenCalledWith("nextflow log wiener-r42");
});

it("a command that changes something can only be inserted", async () => {
  const { onInsert } = open();
  const row = await screen.findByTestId("command-Resume the run");
  expect(within(row).queryByRole("button", { name: "Run" })).toBeNull();
  fireEvent.click(within(row).getByRole("button", { name: "Insert" }));
  expect(onInsert).toHaveBeenCalledWith("nextflow run . -resume");
});
