import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

/** Every mutation in the app can be reported, and every caller of one reports it.
 *
 * **What actually failed on 2026-08-29**, because the shape of the defect decides the shape of
 * the guard. *Keep* answered 500 and the page did not change: nothing on screen, nothing in the
 * console, `docker logs` the only way to find out. The first guess was that mutation hooks were
 * swallowing errors. **They were not, and none of them ever have been.** `useKeep` returned
 * `error` with a comment reading *"Shown, not swallowed"*; every other hook returns the
 * `useMutation` result whole, which carries `.error` to its caller. Every consumer references
 * one.
 *
 * The single break was `Builder.tsx` handing `Walk` a `keep` prop with no error in it — one
 * call site, one dropped field. So the real fix is a **required prop** in `Walk.tsx`, which
 * `tsc` enforces and no scan can; this file guards the two properties that made that break a
 * one-line one rather than a systemic one, so they cannot rot.
 */
const SRC = join(import.meta.dirname, ".");

const rel = (path: string) => path.slice(SRC.length + 1);

function walk(): [string, string][] {
  const out: [string, string][] = [];
  const go = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== "node_modules") go(path);
      } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
        out.push([path, readFileSync(path, "utf8")]);
      }
    }
  };
  go(SRC);
  return out;
}

/** Source with comments removed.
 *
 * **The third scan in this codebase to need this, on the same day.** `tokens.test.ts` tripped on
 * a comment quoting the curve it had just replaced, `test_emit.py` on a comment quoting the
 * broken `enabled:` form, and this one on `home/Work.tsx` citing `useSubmit.ts` by name in a
 * sentence about the courier.
 *
 * The pattern is worth stating once: **a scan that cannot tell code from prose punishes writing
 * down why**, and this repository asks for that everywhere. Strip first, then match.
 */
const code = (text: string) =>
  text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

const hooks = () => walk().filter(([, text]) => code(text).includes("useMutation("));

/** A hook hands its caller an error either by returning the mutation result whole — which
 *  carries `.error` — or by mapping it onto a field of its own return. Both are reporting. */
const handsBackAnError = (text: string) =>
  /return\s+useMutation\(/.test(code(text)) || /\berror:\s*\w/.test(code(text));

/** The names of the mutation hooks, so a consumer can be found by what it imports. */
function hookNames(): string[] {
  return hooks().flatMap(([, text]) =>
    [...code(text).matchAll(/export function (use\w+)/g)].map((m) => m[1]),
  );
}

it("hands an error back from every mutation hook", () => {
  const silent = hooks()
    .filter(([, text]) => !handsBackAnError(text))
    .map(([path]) => rel(path));
  expect(silent).toEqual([]);
});

it("references that error in every component that calls one", () => {
  // **The half that broke.** A hook cannot make its caller look, so this is the scan and
  // `Walk.tsx`'s required prop is the type. Neither is sufficient: the scan sees the file
  // mention an error and cannot see it reach the screen, and the prop only covers one
  // component. Together they cover the shape of the actual defect.
  const names = hookNames();
  const deaf = walk()
    .filter(([path]) => !path.includes("/api/") && !path.endsWith("queryClient.ts"))
    .filter(([, text]) => names.some((name) => new RegExp(`\\b${name}\\b`).test(code(text))))
    .filter(([, text]) => !/\.error\b|\berror\b|isError/.test(code(text)))
    .map(([path]) => rel(path));
  expect(deaf).toEqual([]);
});

it("reaches both halves, so neither can pass by finding nothing", () => {
  // A67, and this file earned the reminder the hard way — see the guard ledger, 2026-08-30.
  // The first version of this test was reverted against a hook that does not have the shape
  // the revert edited, so it passed having proved nothing about the guard at all.
  expect(hooks().map(([path]) => rel(path))).toContain("build/useKeep.ts");
  expect(hookNames()).toContain("useKeep");
  expect(hookNames().length).toBeGreaterThan(5);
});
