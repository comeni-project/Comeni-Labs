import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

const SRC = join(import.meta.dirname, ".");

/** Every source file the app ships, as `[path, text]`. */
function sources(): [string, string][] {
  const out: [string, string][] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        // `api/` is generated and `wiener/api/` with it — neither carries CSS.
        if (entry.name !== "api" && entry.name !== "node_modules") walk(path);
      } else if (/\.(tsx|ts|css)$/.test(entry.name) && !entry.name.endsWith(".test.ts")) {
        out.push([path, readFileSync(path, "utf8")]);
      }
    }
  };
  walk(SRC);
  return out;
}

/** Every `var(--name)` the app references, fallback chains included. */
function referenced(): Map<string, string[]> {
  const found = new Map<string, string[]>();
  for (const [path, text] of sources()) {
    // `var(--x)` and `var(--x, fallback)` both — the comma form is how `--advisory`
    // hid: a fallback chain where BOTH names were undefined renders as inherited.
    for (const match of text.matchAll(/var\(\s*--([a-z0-9-]+)/g)) {
      const name = match[1];
      found.set(name, [...(found.get(name) ?? []), path]);
    }
  }
  return found;
}

/** The five movements, plus the two utilities that travel with them.
 *
 *  Listed rather than discovered, because the point of the list is that adding a sixth is a
 *  design decision — `dashboard.md` §8. A name that is not here cannot be caught by this guard,
 *  which is the trade: a closed list catches a deleted rule and misses an invented class, and
 *  the invented one is what code review is for.
 */
const MOVEMENTS = ["settle", "stagger", "grow-x", "flow", "live", "blink", "lift", "tnum"];

/** The layout utilities, which fail the same silent way: `className="band"` with no rule is a
 *  one-column grid that looks like a deliberate one-column grid. */
const LAYOUT = ["band", "tbl", "withRail"];

const SYSTEM = [...MOVEMENTS, ...LAYOUT];

/** Where each design-system class is worn, by file. */
function wearing(): Map<string, string[]> {
  const found = new Map<string, string[]>();
  for (const [path, text] of sources()) {
    if (path.endsWith("main.css")) continue; // where they are DEFINED, not worn
    for (const name of SYSTEM) {
      // In a `className` string a class is bounded by whitespace or the quote; the escape is
      // because `grow-x` carries a `-`, which is not a regex metacharacter but reads as one.
      const worn = new RegExp(`(^|[\\s"'\`])${name.replace("-", "\\-")}([\\s"'\`]|$)`, "m");
      if (worn.test(text)) found.set(name, [...(found.get(name) ?? []), path]);
    }
  }
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

it("names no colour outside the token file", () => {
  // **This is what made swapping the whole palette cheap**, and until 2026-08-30 it held by
  // convention alone. Migrating the product to Observatory touched `tokens.css` and one
  // `@theme` mirror and nothing else, because not one component names a colour: no hex, no
  // `rgba(`, no `bg-slate-700`. A single `#fff` would have been invisible on a light ground
  // and a hole in a dark one.
  //
  // Three spellings, because a palette leaks in three ways and blocking two of them just moves
  // the leak. `test_egress.py` learned the same thing — the rule became an allowlist because a
  // blocklist can only forbid what somebody already thought of.
  const TAILWIND_HUES =
    "white|black|slate|gray|grey|zinc|neutral|stone|red|orange|amber|yellow|lime|green|" +
    "emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
  const leaks = sources()
    .filter(([path]) => !path.endsWith("tokens.css"))
    .flatMap(([path, text]) => {
      const code = text
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/(^|[^:])\/\/.*$/gm, "$1");
      return [
        ...[...code.matchAll(/#[0-9A-Fa-f]{3,8}\b/g)].map((m) => `${m[0]} in ${path}`),
        ...[...code.matchAll(/\b(?:rgba?|hsla?)\(/g)].map((m) => `${m[0]} in ${path}`),
        ...[...code.matchAll(
          new RegExp(`\\b(?:bg|text|border|fill|stroke)-(?:${TAILWIND_HUES})\\b`, "g"),
        )].map((m) => `${m[0]} in ${path}`),
      ];
    });

  expect(leaks).toEqual([]);
});

it("declares one easing curve, in the source", () => {
  // **This is the half a source scan can prove, and it is not the whole claim.** The shipped
  // stylesheet is where "one curve" is true or false, and it was FALSE the first time it was
  // checked: `transition-colors` (eleven callers) and `animate-pulse` (one) each emitted
  // Tailwind's own easing, so `dist/` carried three curves while `tokens.css` claimed one.
  // Fixed by overriding `--default-transition-timing-function` and `--animate-pulse` in
  // `@theme` rather than by rewriting twelve call sites.
  //
  // The compiled check is `grep -o 'cubic-bezier([^)]*)' dist/assets/*.css | sort -u`, which
  // needs a production build and so does not belong in the unit suite. It is written down in
  // `dashboard.md` §8 so the next person can run it, and this guard holds the source half.
  // **Comments are stripped first, and the guard needed it immediately.** Both of this file's
  // sibling comments quote the curves they replaced — a value named in prose is documentation,
  // not a declaration, and a scan that cannot tell them apart makes the honest habit of writing
  // down what you changed into a test failure.
  const code = (text: string) =>
    text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

  const curves = sources()
    .filter(([path]) => path.endsWith(".css") || path.endsWith(".tsx"))
    .flatMap(([path, text]) =>
      [...code(text).matchAll(/cubic-bezier\([^)]*\)/g)].map((m) => `${m[0]} (${path})`),
    )
    // The one occurrence allowed to name a curve is `--ease`, the token that defines it.
    .filter((found) => !found.startsWith("cubic-bezier(.32, .72, 0, 1)"));

  expect(curves).toEqual([]);
});

it("keeps sideways scrolling inside the one container allowed to have it", () => {
  // **`.tbl` is the only horizontal scrolling the design system declares.** The page body never
  // scrolls sideways — `dashboard.md` §4 rule 2 — and the way that guarantee is lost is a
  // well-meant `overflow-x` on a page shell, added to stop one wide table from clipping.
  //
  // **What this does NOT police, deliberately:** a component putting `overflow-x-auto` on its
  // own `<pre>`. Three do — a drift excerpt, gate output, an artifact excerpt — and that is the
  // same rule working, not a breach of it: wide content scrolls in its own container.
  //
  // **And what it CANNOT check**, stated rather than implied: whether the rendered page actually
  // overflows. happy-dom has no layout engine, so there is no honest assertion about real
  // widths here, and a test that pretended otherwise would be the green tick over an open hole
  // this file's other guard exists to warn about. This checks the declarations it can see.
  const css = readFileSync(join(SRC, "main.css"), "utf8");
  const rules = [...css.matchAll(/([^{}]+)\{([^}]*overflow-x[^}]*)\}/g)]
    .map(([, selector]) => selector.trim().split("\n").pop()!.trim());
  expect(rules).toEqual([".tbl"]);

  // The Shell is the frame every route renders inside; an `overflow-x` here is a page-level one.
  const shell = readFileSync(join(SRC, "app", "Shell.tsx"), "utf8");
  expect(shell).not.toMatch(/overflow-x/);
});

it("defines every motion class the app wears", () => {
  // **The same silence, one layer up.** An undefined `var()` renders as inherited and looks
  // deliberate; a `className="settle"` whose rule nobody wrote renders as *nothing moves*,
  // which looks exactly like the reduced-motion path working correctly. Neither is an error.
  //
  // This was the actual gap on 2026-08-30. The token guard above was already general — it
  // walks every file and every `var()` — so what was missing was never a broader version of
  // it, it was this.
  const defined = readFileSync(join(SRC, "main.css"), "utf8");

  const missing = [...wearing()]
    .filter(([name]) => !new RegExp(`^\\.${name.replace("-", "\\-")}[\\s,{:]`, "m").test(defined))
    .map(([name, where]) => `.${name} (${[...new Set(where)].join(", ")})`);

  expect(missing).toEqual([]);
});

it("sets every face in the family the artboards use, and bundles it", () => {
  // **The defect this exists for.** The app declared `--font-display: Georgia, … serif` and
  // loaded no webfont at all, so the front door's headline — the first thing anybody sees —
  // rendered in a serif that appears nowhere in the design, and every other screen fell back to
  // the system sans. **314 tests passed throughout**: a typeface is invisible to a suite that
  // only ever reads text content, which is why this reads the stylesheet instead.
  const tokens = readFileSync(join(SRC, "tokens.css"), "utf8");
  const main = readFileSync(join(SRC, "main.css"), "utf8");

  for (const role of ["--font-ui", "--font-display", "--font-data"]) {
    const line = tokens.split("\n").find((l) => l.trimStart().startsWith(`${role}:`));
    expect(line, `${role} is not declared`).toBeTruthy();
    expect(line, `${role} names a face the artboards do not use`).toMatch(/Geist/);
  }

  // No serif anywhere: the artboards are one family in two cuts. **`sans-serif` is not a
  // serif**, and the first version of this line matched it — a scan whose own trailing fallback
  // trips it is a scan that gets deleted rather than obeyed, which is the third time that shape
  // has turned up in two days. Named families and a `serif` that stands on its own.
  expect(tokens).not.toMatch(/--font-[a-z-]+:[^;]*(?:Georgia|Times|Iowan|ui-serif|[ ,]serif)/);

  // **Bundled, not fetched** — invariant 13. A Google Fonts `<link>` would render the design on
  // the hosted instance and the fallback stack in an air-gapped laboratory, which is
  // "self-hosted is a degraded tier" arriving as a stylesheet.
  expect(main).toMatch(/@import "@fontsource-variable\/geist"/);
  expect(main).toMatch(/@import "@fontsource-variable\/geist-mono"/);
  expect(main).not.toMatch(/fonts\.googleapis\.com/);
});

it("draws the ground the artboards sit on", () => {
  // The field was deferred through all of Plan 4 as "the three-layer arc field — decorative
  // ambience". It is the page's **ground**: without it `body` is a flat black rectangle and
  // every panel reads as a grey box floating on nothing, which is most of why the built screens
  // did not look like the drawings they came from.
  const shell = readFileSync(join(SRC, "app/Shell.tsx"), "utf8");
  const main = readFileSync(join(SRC, "main.css"), "utf8");

  expect(shell, "the shell mounts no field").toMatch(/<Field\s/);
  for (const layer of ["field-breathe", "field-spin", "field-scan", "field-vignette"]) {
    expect(main, `${layer} is used and never defined`).toMatch(new RegExp(`\\.${layer}[\\s,{:]`));
  }
});

it("watches classes that are actually worn, so it cannot pass by finding none", () => {
  // A67 again, and it matters more here than above: `wearing()` returns only the classes it
  // FOUND, so a broken walk yields an empty map and the test above passes with nothing checked.
  const worn = wearing();
  expect(worn.size).toBeGreaterThan(0);
  // `live` and `breathe` predate the system and have known callers — `runs/Graph.tsx` and
  // `runs/Console.tsx`. If `live` stops being found, the walk broke rather than the code.
  expect(worn.has("live")).toBe(true);
});
