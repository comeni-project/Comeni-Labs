import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { Failed, Loading } from "../ui/States";

type ModuleView = components["schemas"]["ModuleView"];

/** Find a tool, over the canvas, without a mouse.
 *
 * ═══ IT REPLACES THE LEFT PALETTE ═════════════════════════════════════════════════════════
 *
 * `n-bbrowse`. The palette was a permanent third column listing every contract by `roles[0]`,
 * reachable only by drag and double-click. This is the rare case given the space it deserves —
 * *creation is monthly; checking a run is daily* — and the same surface a command palette will
 * later be.
 *
 * ═══ THREE RULES FROM THE CANVAS, EACH ANSWERING A DEFECT ═════════════════════════════════
 *
 * **A tool appears under EVERY role it declares, not `roles[0]`.** `Modules.tsx` grouped by the
 * first, so a tool that both trims and QCs was invisible under one of its two jobs. `ModuleView
 * .roles` has always been a list.
 *
 * **A tool that cannot fit here is SHOWN and MARKED, with the reason** — never hidden. Hiding it
 * answers *why is SALMON_QUANT not in this list* with silence, and the honest answer is short.
 *
 * **There is no description, and inventing one is forbidden.** `impl-reuse` and issue #78:
 * `ModuleContract` has no prose field, so *the type signature is the description that ships
 * today* and the slot is left empty. The artboard draws a sentence per tool; that sentence would
 * have to be written by somebody, and a plausible invented one is worse than none on a screen
 * whose whole claim is that nothing was guessed.
 */
export function Browse({ accepts, onAdd, onClose }: {
  /** When opened from a port, what a candidate must connect to — `{type_id, contract_ids}`.
   *  `undefined` when opened from empty canvas, and then nothing is marked as not fitting:
   *  without a port there is nothing for a tool to fail to fit. */
  accepts?: { label: string; ids: Set<string> };
  onAdd: (contractId: string) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [only, setOnly] = useState(Boolean(accepts));
  const [cursor, setCursor] = useState(0);
  const box = useRef<HTMLDivElement>(null);

  const modules = useQuery({
    queryKey: ["modules"],
    queryFn: () => get<ModuleView[]>("/pipeline/modules"),
  });

  // **Memoised, or the `useMemo`s below never memoise.** `modules.data ?? []` is a NEW array
  // on every render, so every dependent computation re-ran on every keystroke — the hook was
  // there and did nothing. `oxlint`'s `exhaustive-deps` caught it, which is the one place this
  // session a linter found something the tests could not.
  const all = useMemo(() => modules.data ?? [], [modules.data]);

  const matching = useMemo(() => {
    const want = query.trim().toLowerCase();
    return all.filter((m) =>
      want === ""
      || m.tool.toLowerCase().includes(want)
      || m.process.toLowerCase().includes(want)
      || m.roles.some((role) => role.toLowerCase().includes(want)));
  }, [all, query]);

  const fits = (m: ModuleView) => accepts === undefined || accepts.ids.has(m.contract_id);
  const shown = only ? matching.filter(fits) : matching;

  /** **Every role, not the first.** A tool with two jobs appears twice, on purpose. */
  const byRole = useMemo(() => {
    const groups = new Map<string, ModuleView[]>();
    for (const m of shown) {
      for (const role of m.roles.length ? m.roles : ["uncategorised"]) {
        groups.set(role, [...(groups.get(role) ?? []), m]);
      }
    }
    return [...groups].sort(([a], [b]) => a.localeCompare(b));
  }, [shown]);

  /** The flat order the keyboard walks, which must match what the eye reads. */
  const order = useMemo(() => byRole.flatMap(([role, ms]) => ms.map((m) => ({ role, m }))), [byRole]);

  useEffect(() => setCursor(0), [query, only, modules.data]);
  useEffect(() => { box.current?.querySelector("input")?.focus(); }, []);

  return (
    <div
      className="absolute inset-0 z-40 grid place-items-start justify-center pt-[8vh]
                 bg-[color-mix(in_oklab,var(--paper)_72%,transparent)]"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        ref={box}
        data-testid="browse"
        role="dialog"
        aria-label="find a tool"
        className="w-[min(900px,92vw)] max-h-[76vh] flex flex-col bg-surface border border-line-2
                   rounded-r shadow-e3 overflow-hidden settle"
        onKeyDown={(e) => {
          if (e.key === "Escape") { onClose(); return; }
          if (e.key === "ArrowDown") {
            e.preventDefault(); setCursor((n) => Math.min(n + 1, order.length - 1));
          }
          if (e.key === "ArrowUp") { e.preventDefault(); setCursor((n) => Math.max(n - 1, 0)); }
          if (e.key === "Enter" && order[cursor]) {
            e.preventDefault(); onAdd(order[cursor].m.contract_id);
          }
        }}
      >
        <div className="flex items-baseline gap-3 px-5 py-4 border-b border-line">
          <span aria-hidden className="text-ink-3 font-data">›</span>
          <input
            aria-label="search tools"
            value={query}
            placeholder="search"
            onChange={(e) => setQuery(e.target.value)}
            className="grow bg-transparent border-0 outline-none text-object text-ink
                       placeholder:text-ink-3"
          />
          <span className="text-secondary text-ink-3 shrink-0">esc to close</span>
        </div>

        <div className="flex items-center gap-2 px-5 py-2 border-b border-line flex-wrap">
          <span className="text-label uppercase tracking-[.13em] text-ink-3">Filter</span>
          {accepts && (
            <button
              type="button"
              data-testid="filter-accepts"
              onClick={() => setOnly((v) => !v)}
              aria-pressed={only}
              className={`px-2 py-1 rounded-r text-secondary font-data cursor-pointer border
                          ${only
                            ? "border-[var(--link)] text-[var(--link)] bg-transparent"
                            : "border-line text-ink-3 bg-transparent"}`}
            >
              accepts {accepts.label} {only ? "×" : "+"}
            </button>
          )}
          {/* **The registry's own count**, not a catalogue's — #77 means a catalogue total is
              aspirational, and the filtered number is the useful one either way. */}
          <span className="ml-auto text-secondary text-ink-3 tnum">
            {shown.length} of {all.length}
          </span>
        </div>

        <div className="flex-1 min-h-0 overflow-auto px-5 py-4">
          {modules.isLoading && <Loading what="the tools" />}
          {modules.error && <Failed error={modules.error} />}
          {modules.data && order.length === 0 && (
            <p className="text-secondary text-ink-3 m-0">nothing here matches that.</p>
          )}

          {byRole.map(([role, ms]) => (
            <div key={role} className="mb-6">
              <p className="text-label uppercase tracking-[.13em] text-ink-3 m-0 mb-2">
                {role.replace(/_/g, " ")} · {ms.length}
              </p>
              <div className="band">
                {ms.map((m) => {
                  const n = order.findIndex((o) => o.role === role && o.m.contract_id === m.contract_id);
                  const able = fits(m);
                  return (
                    <button
                      key={role + m.contract_id}
                      type="button"
                      data-testid="browse-card"
                      data-active={n === cursor || undefined}
                      data-fits={able || undefined}
                      onMouseEnter={() => setCursor(n)}
                      onClick={() => onAdd(m.contract_id)}
                      className="text-left p-3 rounded-r border border-line bg-transparent
                                 cursor-pointer data-[active]:border-line-2
                                 data-[active]:bg-surface-2"
                    >
                      <span className="flex items-baseline gap-2">
                        <span className="font-data text-body text-ink">{m.process}</span>
                        {!able && (
                          <span className="ml-auto text-label uppercase tracking-[.1em]
                                           text-[var(--measured)]">
                            won't fit here
                          </span>
                        )}
                      </span>
                      {/* **The type signature IS the description** — #78. No prose slot. */}
                      <span className="block font-data text-secondary text-[var(--link)] mt-1">
                        {m.needs.join(", ") || "—"} → {m.makes.join(", ") || "—"}
                      </span>
                      <span className="block font-data text-label text-ink-3 mt-1 truncate">
                        {m.contract_id} · {m.roles.join(", ")}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="px-5 py-2 border-t border-line flex items-baseline gap-4">
          <span className="text-label text-ink-3">↑↓ move · ↵ add · esc to close</span>
          <span className="ml-auto text-label text-ink-3">
            a tool appears under <b className="font-normal text-ink-2">every</b> role it declares
          </span>
        </div>
      </div>
    </div>
  );
}
