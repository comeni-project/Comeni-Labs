# Settings 3 — the menu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A gear in the top bar opens `/settings/<section>`, which draws whatever the API serves: each setting with its control, its source, a lock or *not built* mark when greyed, and a ⓘ that says what it is and why it is greyed. Appearance (the theme) is the first section that works.

**Architecture:** `frontend/src/preferences/` holds a generic menu: `useMenu`/`useWrite` over `GET`/`PUT /api/settings`, one `SettingRow` that picks its control by `kind`, a `Help` toggletip, and `Preferences`, the page. Nothing in it names a particular setting. A setting with `where: "browser"` is kept in `localStorage` through `useBrowserSetting`, which `useTheme` (used by the shell) shares, so changing the theme in the menu repaints at once.

**Tech Stack:** React 19, TypeScript, react-router 7, TanStack Query 5, Tailwind 4, Vitest + Testing Library (happy-dom).

**Spec:** `docs/superpowers/specs/2026-10-01-settings-design.md` (§1, §5, §7, §8, §9). Issue #213, part 14.7.5.3 of #181. Needs parts 1 and 2 (#211, #212), including the regenerated `frontend/src/api/schema.d.ts`.

## Global Constraints

- `frontend/src/api/` is generated; the one hand-written file there is `client.ts`. Never edit `schema.d.ts`.
- Type-check with `npx tsc -b`, never `tsc --noEmit`. Tests: `cd frontend && npx vitest run <path>`.
- Colours are Tailwind tokens from `main.css` (`ink`, `ink-3`, `line`, `fault`, `surface`, `measured`, `undecided`…); an unmapped colour generates no CSS.
- Cite issues in UI copy as *issue 110*, never `#110`.
- The words a person reads about a setting (label, help, reasons) come from the API. The menu writes only its own chrome: section navigation, source badges, button labels.
- Wrap every `localStorage` read and write in `try`/`catch`; a private window can throw.
- The menu's code is named `preferences/` so it never collides with `build/Settings.tsx`, the card for a step's parameters.

## Review Focus

1. **The API is down or answers 500:** the page shows the shared `Failed` state, not a blank page. Pinned in Task 4.
2. **A 409 (locked between loading and saving, e.g. `.env` edited):** the row shows the coded refusal and the menu reloads, so the field greys. Pinned in Task 1 (client) and Task 4.
3. **`/settings/nonsense`:** an unknown section shows `Empty` with a way back, never a crash. Pinned in Task 4.
4. **A kind the frontend does not know** (a future kind served before the frontend is updated): rendered read-only with its value as text. Pinned in Task 3.
5. **`localStorage` throwing** (private window): the theme still works for the session and nothing crashes. Pinned in Task 2.

---

## File structure

| File | Responsibility |
|---|---|
| Modify `frontend/src/api/client.ts` | a 409 is a `Refused` with the coded detail, like a 422 |
| Create `frontend/src/api/client.test.ts` | that |
| Create `frontend/src/preferences/useBrowserSetting.ts` | a per-browser value, shared across components |
| Create `frontend/src/app/useTheme.ts` | the theme, applied; reads the old `comeni-theme` once |
| Create `frontend/src/preferences/usePreferences.ts` | `useMenu`, `useWrite`, the types |
| Create `frontend/src/preferences/Help.tsx` | the ⓘ toggletip |
| Create `frontend/src/preferences/SettingRow.tsx` | one row, any kind |
| Create `frontend/src/preferences/Preferences.tsx` | the page |
| Create tests beside each: `useBrowserSetting.test.tsx`, `Help.test.tsx`, `SettingRow.test.tsx`, `Preferences.test.tsx`, `frontend/src/app/useTheme.test.tsx` | |
| Modify `frontend/src/app/Shell.tsx` | use `useTheme`; the toggle becomes a gear link |
| Modify `frontend/src/app/router.tsx` | `/settings/:section?` |

---

### Task 1: A 409 is a refusal with its reason

**Files:**
- Modify: `frontend/src/api/client.ts` (`send`)
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces: `put`/`post` throw `Refused(detail)` on 409 as on 422.

- [ ] **Step 1: Write the failing test**

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

import { put, Refused } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("the client", () => {
  it("turns a 409 into a Refused carrying the coded detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 409,
      json: async () => ({ detail: "MI0300: building.pacing is locked: Pinned by .env" }),
    }));
    await expect(put("/settings/building.pacing", { value: "ask" }))
      .rejects.toEqual(new Refused("MI0300: building.pacing is locked: Pinned by .env"));
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: FAIL, rejected with `Error: /settings/building.pacing → 409`

- [ ] **Step 3: Change `send`**

In `client.ts`, replace `if (r.status === 422) {` with:

```ts
  // **409 as well as 422**: a setting locked between reading and saving answers 409 with a
  // coded reason (`MI0300`), and the person needs that sentence, not a status code.
  if (r.status === 422 || r.status === 409) {
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/client.test.ts
git commit -m "feat(client): a 409 is a refusal with its coded reason (#213)"
```

---

### Task 2: A per-browser setting, and the theme on it

**Files:**
- Create: `frontend/src/preferences/useBrowserSetting.ts`
- Create: `frontend/src/app/useTheme.ts`
- Modify: `frontend/src/app/Shell.tsx`
- Test: `frontend/src/preferences/useBrowserSetting.test.tsx`, `frontend/src/app/useTheme.test.tsx`

**Interfaces:**
- Produces: `useBrowserSetting(key: string, fallback: string): [string, (value: string) => void]`; `storageName(key: string): string` (`comeni.<key>`); `type Theme = "system" | "light" | "dark"`; `useTheme(): [Theme, (t: Theme) => void]`; `painted(theme: Theme): "light" | "dark"`.

- [ ] **Step 1: Write the failing tests**

`useBrowserSetting.test.tsx`:

```tsx
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { storageName, useBrowserSetting } from "./useBrowserSetting";

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("a per-browser setting", () => {
  it("starts at the fallback and keeps what is set", () => {
    const { result } = renderHook(() => useBrowserSetting("appearance.theme", "system"));
    expect(result.current[0]).toBe("system");
    act(() => result.current[1]("dark"));
    expect(result.current[0]).toBe("dark");
    expect(localStorage.getItem(storageName("appearance.theme"))).toBe("dark");
  });

  it("is shared: a second component sees the change at once", () => {
    const a = renderHook(() => useBrowserSetting("appearance.theme", "system"));
    const b = renderHook(() => useBrowserSetting("appearance.theme", "system"));
    act(() => a.result.current[1]("light"));
    expect(b.result.current[0]).toBe("light");
  });

  it("survives a browser that refuses storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    const { result } = renderHook(() => useBrowserSetting("appearance.theme", "system"));
    expect(result.current[0]).toBe("system");
    act(() => result.current[1]("dark"));
    expect(result.current[0]).toBe("dark");
  });
});
```

`useTheme.test.tsx`:

```tsx
import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { painted, useTheme } from "./useTheme";

afterEach(() => localStorage.clear());

describe("the theme", () => {
  it("keeps a choice made with the old toggle", () => {
    localStorage.setItem("comeni-theme", "light");
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("light");
  });

  it("paints an explicit choice as itself", () => {
    expect(painted("dark")).toBe("dark");
    expect(painted("light")).toBe("light");
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/preferences/useBrowserSetting.test.tsx src/app/useTheme.test.tsx`
Expected: FAIL, cannot resolve `./useBrowserSetting` and `./useTheme`

- [ ] **Step 3: Write the implementation**

`useBrowserSetting.ts`:

```ts
import { useSyncExternalStore } from "react";

/** A setting kept by this browser rather than the server — the theme is one (spec §7).
 *
 * **Shared through one event**, so the menu and the shell agree the moment either changes it;
 * the `storage` event covers another tab. **A browser that refuses storage** (a private window)
 * still gets the value for this session: `memory` holds what could not be written.
 */
const EVENT = "comeni-browser-setting";
const memory = new Map<string, string>();

export function storageName(key: string): string {
  return `comeni.${key}`;
}

function read(name: string): string | null {
  try {
    return localStorage.getItem(name) ?? memory.get(name) ?? null;
  } catch {
    return memory.get(name) ?? null;
  }
}

function subscribe(changed: () => void): () => void {
  window.addEventListener(EVENT, changed);
  window.addEventListener("storage", changed);
  return () => {
    window.removeEventListener(EVENT, changed);
    window.removeEventListener("storage", changed);
  };
}

export function useBrowserSetting(key: string, fallback: string): [string, (value: string) => void] {
  const name = storageName(key);
  const value = useSyncExternalStore(subscribe, () => read(name) ?? fallback);
  const set = (next: string) => {
    memory.set(name, next);
    try {
      localStorage.setItem(name, next);
    } catch {
      // kept in `memory` for this session
    }
    window.dispatchEvent(new Event(EVENT));
  };
  return [value, set];
}
```

`useTheme.ts`:

```ts
import { storageName, useBrowserSetting } from "../preferences/useBrowserSetting";

export type Theme = "system" | "light" | "dark";

/** The old toggle stored `light` or `dark` under `comeni-theme`; a choice made with it is kept.
 *
 * **Moved, not only read**, so the menu's row (which reads the new name) and the shell agree. */
function legacy(): Theme | null {
  try {
    const old = localStorage.getItem("comeni-theme");
    if (old !== "light" && old !== "dark") return null;
    if (localStorage.getItem(storageName("appearance.theme")) === null) {
      localStorage.setItem(storageName("appearance.theme"), old);
    }
    localStorage.removeItem("comeni-theme");
    return old;
  } catch {
    return null;
  }
}

export function painted(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [raw, set] = useBrowserSetting("appearance.theme", legacy() ?? "system");
  const theme: Theme = raw === "light" || raw === "dark" ? raw : "system";
  return [theme, set];
}
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd frontend && npx vitest run src/preferences/useBrowserSetting.test.tsx src/app/useTheme.test.tsx`
Expected: PASS, 5 passed

- [ ] **Step 5: The shell uses it, and the toggle becomes a gear**

In `Shell.tsx`, replace the `useState`/`useEffect` theme block with:

```tsx
  const [theme] = useTheme();
  useEffect(() => {
    document.documentElement.dataset.theme = painted(theme);
  }, [theme]);
```

Replace the theme `<button …>…</button>` at the end of the `<nav>` with:

```tsx
        {/* **Settings live behind a gear at the right**, where most applications put it. The
            theme toggle that sat here moved into Settings → Appearance (spec §7). */}
        <Link
          to="/settings"
          aria-label="Settings"
          title="Settings"
          className="ml-auto pb-[3px] border-b border-transparent text-[14px] text-ink-3
                     hover:text-ink no-underline"
        >
          ⚙
        </Link>
```

Fix the imports: add `import { painted, useTheme } from "./useTheme";`; drop `useState` from the React import if nothing else uses it (`noUnusedLocals` will say).

- [ ] **Step 6: Type-check and run the shell's tests**

Run: `cd frontend && npx tsc -b && npx vitest run src/app src/build/Shell.test.tsx`
Expected: no type errors; PASS. If a test looked for the *Switch to … mode* button, change it to look for the `Settings` link and record the ruling.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/preferences/useBrowserSetting.ts frontend/src/preferences/useBrowserSetting.test.tsx frontend/src/app/useTheme.ts frontend/src/app/useTheme.test.tsx frontend/src/app/Shell.tsx
git commit -m "feat(settings): the theme is a per-browser setting; the toggle becomes a gear (#213)"
```

---

### Task 3: The ⓘ and the row

**Files:**
- Create: `frontend/src/preferences/usePreferences.ts`
- Create: `frontend/src/preferences/Help.tsx`
- Create: `frontend/src/preferences/SettingRow.tsx`
- Test: `frontend/src/preferences/Help.test.tsx`, `frontend/src/preferences/SettingRow.test.tsx`

**Interfaces:**
- Consumes: `components["schemas"]["Menu" | "Entry" | "Shown"]` from the generated schema (confirm the names in `schema.d.ts`; a schema split into `-Input`/`-Output` names gets the `-Output` one, recorded as a ruling); `useBrowserSetting` (Task 2); `get`, `put` (`api/client`).
- Produces: `type Menu`, `type Entry`, `type Shown`; `useMenu()`; `useWrite()` (a mutation taking `{ key: string; value: unknown }`); `Help({ label, help, reason })`; `SettingRow({ entry, onWrite, refusal })`.

- [ ] **Step 1: Write the failing tests**

`Help.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Help } from "./Help";

const HELP = "How the build walks you through its steps.";

describe("the ⓘ", () => {
  it("opens on click and says what the setting is", async () => {
    render(<Help label="Pacing" help={HELP} />);
    expect(screen.queryByText(HELP)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "About Pacing" }));
    expect(screen.getByText(HELP)).toBeTruthy();
  });

  it("opens on Enter and closes on Escape", async () => {
    render(<Help label="Pacing" help={HELP} />);
    screen.getByRole("button", { name: "About Pacing" }).focus();
    await userEvent.keyboard("{Enter}");
    expect(screen.getByText(HELP)).toBeTruthy();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByText(HELP)).toBeNull();
  });

  it("says why when the setting is greyed out", async () => {
    render(<Help label="Pacing" help={HELP} reason="Pinned by .env (COMENI_BUILD_PACING)." />);
    await userEvent.click(screen.getByRole("button", { name: "About Pacing" }));
    expect(screen.getByText(/Why it is greyed out/)).toBeTruthy();
    expect(screen.getByText(/COMENI_BUILD_PACING/)).toBeTruthy();
  });
});
```

`SettingRow.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SettingRow } from "./SettingRow";
import type { Entry } from "./usePreferences";

const HELP = "How the build walks you through its steps, one at a time.";

function entry(over: Record<string, unknown> = {}, shown: Record<string, unknown> = {}): Entry {
  return {
    setting: {
      key: "building.pacing", label: "Pacing", help: HELP, kind: "choice", default: "ask",
      env: null, options: [{ value: "together", label: "Together" }, { value: "ask", label: "Ask" }],
      minimum: null, maximum: null, unavailable: null, where: "installation", ...over,
    },
    shown: { value: "ask", source: "default", locked: false, reason: null, set: null, last4: null, ...shown },
  } as unknown as Entry;
}

describe("a setting row", () => {
  it("draws a choice and writes the option picked", async () => {
    const onWrite = vi.fn();
    render(<SettingRow entry={entry()} onWrite={onWrite} />);
    await userEvent.click(screen.getByLabelText("Together"));
    expect(onWrite).toHaveBeenCalledWith("together");
    expect(screen.getByText("Default")).toBeTruthy();
  });

  it("greys a locked row, marks it, and says why in its ⓘ", async () => {
    const reason = { kind: "pinned", env: "COMENI_BUILD_PACING", says: "Pinned by .env (COMENI_BUILD_PACING). Change it there and restart." };
    render(<SettingRow entry={entry({}, { locked: true, source: "environment", reason })} onWrite={vi.fn()} />);
    expect((screen.getByLabelText("Together") as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByLabelText("Locked")).toBeTruthy();
    expect(screen.getByText("Pinned by .env")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "About Pacing" }));
    expect(screen.getByText(/Change it there and restart/)).toBeTruthy();
  });

  it("marks a designed setting as not built", () => {
    const reason = { kind: "designed", where: "arrives with the consultant build", says: "Designed, not built yet: arrives with the consultant build." };
    render(<SettingRow entry={entry({}, { locked: true, reason })} onWrite={vi.fn()} />);
    expect(screen.getByText("not built")).toBeTruthy();
  });

  it("draws a toggle", async () => {
    const onWrite = vi.fn();
    render(<SettingRow entry={entry({ kind: "toggle", options: [], default: false }, { value: false })} onWrite={onWrite} />);
    await userEvent.click(screen.getByRole("checkbox", { name: "Pacing" }));
    expect(onWrite).toHaveBeenCalledWith(true);
  });

  it("draws a number and writes it on blur", async () => {
    const onWrite = vi.fn();
    render(<SettingRow entry={entry({ kind: "number", options: [], default: 30 }, { value: 30 })} onWrite={onWrite} />);
    const box = screen.getByRole("spinbutton", { name: "Pacing" });
    await userEvent.clear(box);
    await userEvent.type(box, "45");
    await userEvent.tab();
    expect(onWrite).toHaveBeenCalledWith(45);
  });

  it("shows a set secret by its last four and never asks for it back", async () => {
    const onWrite = vi.fn();
    render(<SettingRow entry={entry({ kind: "secret", options: [], default: null }, { value: null, set: true, last4: "1234" })} onWrite={onWrite} />);
    expect(screen.getByText(/ending 1234/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Replace" }));
    await userEvent.type(screen.getByLabelText("Pacing"), "sk-new-5678");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onWrite).toHaveBeenCalledWith("sk-new-5678");
  });

  it("draws a kind it does not know as read-only text", () => {
    render(<SettingRow entry={entry({ kind: "hologram", options: [] }, { value: "shimmer" })} onWrite={vi.fn()} />);
    expect(screen.getByText("shimmer")).toBeTruthy();
    expect(screen.queryByRole("radio")).toBeNull();
  });

  it("shows a refusal under the row", () => {
    render(<SettingRow entry={entry()} onWrite={vi.fn()} refusal="MI0302: building.pacing: 'x' is not one of together, ask" />);
    expect(screen.getByText(/MI0302/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/preferences/Help.test.tsx src/preferences/SettingRow.test.tsx`
Expected: FAIL, cannot resolve `./Help`, `./SettingRow`, `./usePreferences`

- [ ] **Step 3: Write `usePreferences.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { get, put } from "../api/client";
import type { components } from "../api/schema";

export type Menu = components["schemas"]["Menu"];
export type Entry = components["schemas"]["Entry"];
export type Shown = components["schemas"]["Shown"];

/** Every section the API serves. **Never cached past a write**: the menu always shows what the
 *  server would resolve now, including a lock `.env` added since the page opened. */
export function useMenu() {
  return useQuery({ queryKey: ["settings"], queryFn: () => get<Menu>("/settings") });
}

export function useWrite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) =>
      put<Shown>(`/settings/${encodeURIComponent(key)}`, { value }),
    onSettled: () => client.invalidateQueries({ queryKey: ["settings"] }),
  });
}
```

- [ ] **Step 4: Write `Help.tsx`**

```tsx
import { useEffect, useId, useRef, useState } from "react";

/** The ⓘ beside a setting: what it is, and why it is greyed out (spec §5).
 *
 * **A toggletip, not a hover tooltip.** A touch screen has no hover and a keyboard cannot reach
 * one, so it opens on click, tap or Enter and closes on Escape or a click elsewhere. The words
 * are the API's: `help` from the declaration, `reason` from the closed list of reasons.
 */
export function Help({ label, help, reason }: { label: string; help: string; reason?: string | null }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const box = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <span ref={box} className="relative inline-block">
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className="bg-transparent text-ink-3 hover:text-ink cursor-pointer text-secondary px-1"
      >
        ⓘ
      </button>
      {open && (
        <span
          id={id}
          role="note"
          className="absolute left-0 top-full z-10 mt-1 w-[300px] max-w-[calc(100vw-32px)]
                     border border-line bg-surface p-3 text-secondary text-ink shadow-lg"
        >
          <span className="block">{help}</span>
          {reason && (
            <span className="block mt-2 text-ink-2">
              <strong>Why it is greyed out:</strong> {reason}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
```

- [ ] **Step 5: Write `SettingRow.tsx`**

```tsx
import { useState } from "react";

import { Refusal } from "../ui/Refusal";
import { Help } from "./Help";
import { useBrowserSetting } from "./useBrowserSetting";
import type { Entry } from "./usePreferences";

/** One setting, any kind (spec §4, §5).
 *
 * **Knows no particular setting.** It reads `kind` and draws the control for it; a kind it has
 * never heard of is drawn as read-only text, so a newer API never breaks an older page. The only
 * words it writes itself are the source badges and its buttons.
 */
const SOURCE: Record<string, string> = {
  default: "Default",
  installation: "Set here",
  environment: "Pinned by .env",
};

type Props = { entry: Entry; onWrite: (value: unknown) => void; refusal?: string | null };

export function SettingRow(props: Props) {
  return props.entry.setting.where === "browser" ? <InBrowser {...props} /> : <Row {...props} />;
}

function InBrowser({ entry }: Props) {
  const [value, set] = useBrowserSetting(entry.setting.key, String(entry.setting.default));
  return <Row entry={entry} value={value} onWrite={(next) => set(String(next))} badge="This browser" />;
}

function Row({
  entry, onWrite, refusal, value = entry.shown.value, badge,
}: Props & { value?: unknown; badge?: string }) {
  const { setting, shown } = entry;
  const reason = shown.reason ?? null;
  const designed = reason?.kind === "designed";
  return (
    <div data-testid="preference" className="py-3 border-b border-line-soft last:border-b-0">
      <div className="flex items-baseline gap-2">
        <label htmlFor={setting.key} className="text-body text-ink">{setting.label}</label>
        <Help label={setting.label} help={setting.help} reason={reason?.says} />
        {shown.locked && !designed && <span aria-label="Locked" title="Locked">🔒</span>}
        {designed && (
          <span className="text-secondary text-ink-3 border border-line px-1">not built</span>
        )}
        <span className="ml-auto text-secondary text-ink-3">{badge ?? SOURCE[shown.source]}</span>
      </div>
      <div className="mt-2">
        <Control entry={entry} value={value} disabled={shown.locked} onWrite={onWrite} />
      </div>
      {refusal && <div className="mt-2"><Refusal message={refusal} /></div>}
    </div>
  );
}

function Control({
  entry, value, disabled, onWrite,
}: { entry: Entry; value: unknown; disabled: boolean; onWrite: (value: unknown) => void }) {
  const { setting, shown } = entry;
  switch (setting.kind) {
    case "choice":
      return (
        <div role="radiogroup" aria-label={setting.label} className="flex flex-wrap gap-4">
          {(setting.options ?? []).map((option) => (
            <label key={option.value} className="flex items-center gap-1 text-secondary text-ink">
              <input
                type="radio"
                name={setting.key}
                value={option.value}
                checked={value === option.value}
                disabled={disabled}
                onChange={() => onWrite(option.value)}
              />
              {option.label}
            </label>
          ))}
        </div>
      );
    case "toggle":
      return (
        <input
          id={setting.key}
          type="checkbox"
          aria-label={setting.label}
          checked={value === true}
          disabled={disabled}
          onChange={(event) => onWrite(event.target.checked)}
        />
      );
    case "number":
      return <Typed entry={entry} value={value} disabled={disabled} onWrite={onWrite} numeric />;
    case "text":
      return <Typed entry={entry} value={value} disabled={disabled} onWrite={onWrite} />;
    case "secret":
      return <Secret entry={entry} disabled={disabled} onWrite={onWrite} set={shown.set === true} last4={shown.last4 ?? null} />;
    default:
      return <span className="font-data text-secondary text-ink-2">{value === null ? "—" : String(value)}</span>;
  }
}

function Typed({
  entry, value, disabled, onWrite, numeric = false,
}: { entry: Entry; value: unknown; disabled: boolean; onWrite: (v: unknown) => void; numeric?: boolean }) {
  const [draft, setDraft] = useState(value === null ? "" : String(value));
  const commit = () => {
    if (draft === String(value ?? "")) return;
    onWrite(numeric ? Number(draft) : draft);
  };
  return (
    <input
      id={entry.setting.key}
      type={numeric ? "number" : "text"}
      aria-label={entry.setting.label}
      value={draft}
      disabled={disabled}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => event.key === "Enter" && commit()}
      className="border border-line bg-transparent px-2 py-1 text-secondary text-ink w-[260px] max-w-full"
    />
  );
}

function Secret({
  entry, disabled, onWrite, set, last4,
}: { entry: Entry; disabled: boolean; onWrite: (v: unknown) => void; set: boolean; last4: string | null }) {
  const [editing, setEditing] = useState(!set);
  const [draft, setDraft] = useState("");
  if (!editing) {
    return (
      <span className="flex items-center gap-3 text-secondary text-ink-2">
        Set, ending {last4}
        <button type="button" disabled={disabled} onClick={() => setEditing(true)}
                className="bg-transparent text-link cursor-pointer">Replace</button>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <input
        id={entry.setting.key}
        type="password"
        autoComplete="off"
        aria-label={entry.setting.label}
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        className="border border-line bg-transparent px-2 py-1 text-secondary text-ink w-[260px] max-w-full"
      />
      <button type="button" disabled={disabled || !draft}
              onClick={() => { onWrite(draft); setDraft(""); setEditing(false); }}
              className="bg-transparent text-link cursor-pointer">Save</button>
    </span>
  );
}
```

- [ ] **Step 6: Run them to verify they pass, and type-check**

Run: `cd frontend && npx vitest run src/preferences/Help.test.tsx src/preferences/SettingRow.test.tsx && npx tsc -b`
Expected: PASS, 11 passed; no type errors. If `tsc` rejects `reason?.kind` because the generated union narrows differently, narrow with `"kind" in reason` and record it.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/preferences/
git commit -m "feat(settings): the setting row and its ⓘ — what it is, why it is greyed (#213)"
```

---

### Task 4: The page, the route and the gear

**Files:**
- Create: `frontend/src/preferences/Preferences.tsx`
- Modify: `frontend/src/app/router.tsx` (one child route)
- Test: `frontend/src/preferences/Preferences.test.tsx`

**Interfaces:**
- Consumes: `useMenu`, `useWrite`, `Entry`, `Menu` (Task 3); `SettingRow` (Task 3); `Loading`, `Empty`, `Failed` (`ui/States`); `Refused` (`api/client`).
- Produces: `Preferences` (default section is the first served); route `/settings/:section?`.

- [ ] **Step 1: Write the failing tests**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { routes } from "../app/router";

const HELP = "A setting this page has never seen, served by a newer API than it.";

/** **A setting the frontend has never seen.** The menu draws whatever the API serves; this is
 *  the proof that adding a setting needs no frontend change (spec §9). */
const MENU = {
  sections: [
    {
      key: "lab", title: "Laboratory", order: 1, served_by: "mendel",
      entries: [{
        setting: {
          key: "lab.flavour", label: "Flavour", help: HELP, kind: "choice", default: "plain",
          env: null, options: [{ value: "plain", label: "Plain" }, { value: "spiced", label: "Spiced" }],
          minimum: null, maximum: null, unavailable: null, where: "installation",
        },
        shown: { value: "plain", source: "default", locked: false, reason: null, set: null, last4: null },
      }],
    },
    {
      key: "other", title: "Other", order: 2, served_by: "mendel",
      entries: [{
        setting: {
          key: "other.on", label: "On", help: HELP, kind: "toggle", default: false, env: null,
          options: [], minimum: null, maximum: null, unavailable: null, where: "installation",
        },
        shown: { value: false, source: "default", locked: false, reason: null, set: null, last4: null },
      }],
    },
  ],
};

function at(path: string, fetch: ReturnType<typeof vi.fn>) {
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const serving = (menu = MENU) =>
  vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => menu });

afterEach(() => vi.unstubAllGlobals());

describe("the settings page", () => {
  it("opens on the first section and draws a setting it has never seen", async () => {
    const router = at("/settings", serving());
    await waitFor(() => expect(router.state.location.pathname).toBe("/settings/lab"));
    expect(await screen.findByText("Flavour")).toBeTruthy();
    expect(screen.getByLabelText("Spiced")).toBeTruthy();
  });

  it("lists every section and moves between them", async () => {
    at("/settings/lab", serving());
    await userEvent.click(await screen.findByRole("link", { name: "Other" }));
    expect(await screen.findByRole("checkbox", { name: "On" })).toBeTruthy();
  });

  it("writes a change and asks for the menu again", async () => {
    const fetch = serving();
    at("/settings/lab", fetch);
    await userEvent.click(await screen.findByLabelText("Spiced"));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith("/api/settings/lab.flavour", expect.objectContaining({
        method: "PUT", body: JSON.stringify({ value: "spiced" }),
      })));
    await waitFor(() =>
      expect(fetch.mock.calls.filter(([url]) => url === "/api/settings").length).toBeGreaterThan(1));
  });

  it("shows a 409's reason under the row", async () => {
    const fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) =>
      Promise.resolve(init?.method === "PUT"
        ? { ok: false, status: 409, json: async () => ({ detail: "MI0300: lab.flavour is locked: Pinned by .env (LAB_FLAVOUR)." }) }
        : { ok: true, status: 200, json: async () => MENU }));
    at("/settings/lab", fetch);
    await userEvent.click(await screen.findByLabelText("Spiced"));
    expect(await screen.findByText(/MI0300/)).toBeTruthy();
  });

  it("says so when the API cannot be reached", async () => {
    at("/settings", vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
    expect(await screen.findByText(/500/)).toBeTruthy();
  });

  it("does not crash on a section that does not exist", async () => {
    at("/settings/nonsense", serving());
    expect(await screen.findByText(/no section called nonsense/i)).toBeTruthy();
  });

  it("is reached from the gear in the top bar", async () => {
    // Asserted on the link rather than by clicking from `/`: the home page fetches its own data,
    // and a stub serving the menu to every request would make that page the thing under test.
    at("/settings/lab", serving());
    expect((await screen.findByRole("link", { name: "Settings" })).getAttribute("href"))
      .toBe("/settings");
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && npx vitest run src/preferences/Preferences.test.tsx`
Expected: FAIL — `/settings` matches no route (the ErrorBoundary renders), and `Flavour` is never found.

- [ ] **Step 3: Write `Preferences.tsx`**

```tsx
import { useState } from "react";
import { Link, Navigate, NavLink, useParams } from "react-router";

import { Refused } from "../api/client";
import { Empty, Failed, Loading } from "../ui/States";
import { SettingRow } from "./SettingRow";
import { useMenu, useWrite } from "./usePreferences";

/** Settings (spec §1, §7): sections down the left, the chosen one's settings on the right.
 *
 * **Drawn from what the API serves and nothing else.** No section or setting is named here, so
 * a new one appears when it is declared on the server. On a narrow screen the sections stack
 * above the settings.
 */
export function Preferences() {
  const { section } = useParams();
  const menu = useMenu();
  const write = useWrite();
  const [refused, setRefused] = useState<{ key: string; message: string } | null>(null);

  if (menu.isLoading) return <Loading what="settings" />;
  if (menu.error) return <Failed error={menu.error} />;
  const sections = menu.data?.sections ?? [];
  if (!sections.length) return <Empty title="There are no settings to show." />;
  if (!section) return <Navigate to={`/settings/${sections[0].key}`} replace />;
  const current = sections.find((s) => s.key === section);

  const save = (key: string, value: unknown) => {
    setRefused(null);
    write.mutate(
      { key, value },
      {
        onError: (error) =>
          setRefused({ key, message: error instanceof Refused ? error.message : String(error) }),
      },
    );
  };

  return (
    <main className="gutter grid gap-6 py-7 md:grid-cols-[180px_1fr] max-w-[960px]">
      <nav aria-label="Settings sections" className="flex md:flex-col gap-3 flex-wrap">
        {sections.map((s) => (
          <NavLink
            key={s.key}
            to={`/settings/${s.key}`}
            className={({ isActive }) =>
              `text-secondary no-underline ${isActive ? "text-ink" : "text-ink-3 hover:text-ink"}`}
          >
            {s.title}
          </NavLink>
        ))}
      </nav>
      <section>
        {current ? (
          <>
            <h1 className="text-title text-ink mb-3">{current.title}</h1>
            {current.entries.map((entry) => (
              <SettingRow
                key={entry.setting.key}
                entry={entry}
                onWrite={(value) => save(entry.setting.key, value)}
                refusal={refused?.key === entry.setting.key ? refused.message : null}
              />
            ))}
          </>
        ) : (
          <Empty
            title={`There is no section called ${section}.`}
            next="Choose one from the list."
          />
        )}
        {!current && <Link to="/settings" className="text-link text-secondary">All settings</Link>}
      </section>
    </main>
  );
}
```

- [ ] **Step 4: Add the route**

In `router.tsx`, import `import { Preferences } from "../preferences/Preferences";` and add to the main `children`, after `/runs/:id`:

```tsx
      // **Settings for the whole installation** (spec 2026-10-01). Optional section, so the
      // gear can link to `/settings` and the page picks the first section.
      { path: "/settings/:section?", element: <Preferences /> },
```

- [ ] **Step 5: Run the tests, the whole frontend suite and the type check**

Run: `cd frontend && npx vitest run src/preferences && npx vitest run && npx tsc -b`
Expected: PASS everywhere; no type errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/preferences/Preferences.tsx frontend/src/preferences/Preferences.test.tsx frontend/src/app/router.tsx
git commit -m "feat(settings): the settings page, drawn from whatever the API serves (#213)"
```

---

### Task 5: Walk it and look at it

**Files:** none changed unless the walk finds something; a finding becomes an issue under #210 unless it blocks the menu.

- [ ] **Step 1: Bring the stack up**

Run: `make dev` (the API reloads from `./packages`; the migration from part 2 must be applied: `make migrate`).
Expected: the app on the printed HMR address.

- [ ] **Step 2: Look at it at two widths**

Open `/settings` in the browser (Claude in Chrome: a new tab). Screenshot at 1280px and at 390px wide. Check by eye:
- the gear sits at the right of the top bar, baseline-aligned with the tabs;
- Appearance opens first; the theme's three choices change the page's colours at once;
- the ⓘ opens a popover that stays on screen at 390px;
- *This browser* shows as the theme's source.

- [ ] **Step 3: Show the operator**

Send both screenshots. Anything the operator wants changed is a finding: an issue first, then tuned in #210 unless it blocks.

- [ ] **Step 4: Close the part**

Run `make check`'s parts separately (lint; tests with the throwaway database; types; docs; links), then comment on #213 with the commits and close it.

---

## Execution record

(Filled in while executing: rulings, deviations, the walk's screenshots and findings, and the closing commit for #213.)
