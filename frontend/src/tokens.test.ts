import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

const SRC = join(import.meta.dirname, ".");

/** Every `var(--name)` the app references, fallback chains included. */
function referenced(): Map<string, string[]> {
  const found = new Map<string, string[]>();
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        // `api/` is generated and `wiener/api/` with it — neither carries CSS.
        if (entry.name !== "api" && entry.name !== "node_modules") walk(path);
      } else if (/\.(tsx|ts|css)$/.test(entry.name) && !entry.name.endsWith(".test.ts")) {
        const text = readFileSync(path, "utf8");
        // `var(--x)` and `var(--x, fallback)` both — the comma form is how `--advisory`
        // hid: a fallback chain where BOTH names were undefined renders as inherited.
        for (const match of text.matchAll(/var\(\s*--([a-z0-9-]+)/g)) {
          const name = match[1];
          found.set(name, [...(found.get(name) ?? []), path]);
        }
      }
    }
  };
  walk(SRC);
  return found;
}

it("defines every custom property the app references", () => {
  // Five hover states in the builder were dead CSS from Plan 3C until 2026-08-24, because
  // `hover:bg-[var(--hover)]` referenced a property nobody had defined — and two more,
  // `--profiled` and `--settled`, were names for tiers that never existed in the palette.
  // A grep is the only thing that can catch this: an undefined var() is not an error, it is
  // silence. It renders as inherited and looks deliberate.
  const defined = readFileSync(join(SRC, "tokens.css"), "utf8")
    + readFileSync(join(SRC, "main.css"), "utf8");

  const missing = [...referenced()]
    .filter(([name]) => !defined.includes(`--${name}:`))
    .map(([name, where]) => `--${name} (${[...new Set(where)].join(", ")})`);

  expect(missing).toEqual([]);
});

it("finds something, so it cannot pass by reaching nothing", () => {
  // A67's lesson: a scan that reaches nothing reports nothing. If the walk breaks, the test
  // above goes vacuously green rather than red.
  expect(referenced().size).toBeGreaterThan(15);
  expect(referenced().has("hover")).toBe(true);
});
