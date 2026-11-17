import { expect, it } from "vitest";

import { autoRuns } from "./ConsolePage";

const command = (id: string, read_only: boolean) => ({ id, kind: "command", read_only, command: `cat ${id}` });

it("runs read-only suggestions only in a reply to the person, at most three (Checkpoint D)", () => {
  const blocks = [command("a", true), command("b", false), command("c", true), command("d", true), command("e", true)];
  expect(autoRuns(blocks, new Set(), true).map((b) => b.id)).toEqual(["a", "c", "d"]);
  expect(autoRuns(blocks, new Set(["a"]), true).map((b) => b.id)).toEqual(["c", "d", "e"]);
  // A reply to the output the page sent back itself runs nothing: no chain of model calls.
  expect(autoRuns(blocks, new Set(), false)).toEqual([]);
});
