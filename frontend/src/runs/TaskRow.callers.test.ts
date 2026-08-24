import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

const SRC = join(import.meta.dirname, "..");

/** Every file that imports `TaskRow`, as a repo-relative path. */
function callers(): string[] {
  const found: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (/\.tsx?$/.test(entry.name) && !entry.name.includes(".test.")) {
        if (/from ["'][^"']*\/TaskRow["']/.test(readFileSync(path, "utf8"))) {
          found.push(path.slice(path.indexOf("src/")));
        }
      }
    }
  };
  walk(SRC);
  return found.sort();
}

const ALLOWED = ["src/runs/Overview.tsx", "src/runs/Tasks.tsx"];

it("has at most two callers, so the two renderings cannot drift", () => {
  // §6: expanding a process row asks *what did this process do*; the Tasks tab asks *what
  // across the whole run retried*. Two questions, ONE row component — the same shape as
  // `dag-core` serving both canvases, and for the same reason: two renderings of one row is
  // how they stop agreeing.
  //
  // Written as a subset rather than an equality so it holds at every point in W2 — Overview
  // arrives in Task 6 and Tasks in Task 9 — while still failing the moment a THIRD screen
  // renders a task, which is the drift it exists to catch.
  const extra = callers().filter((path) => !ALLOWED.includes(path));
  expect(extra).toEqual([]);
  expect(callers().length).toBeLessThanOrEqual(2);
});
