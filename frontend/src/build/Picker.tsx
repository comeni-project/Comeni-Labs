import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { Failed, Loading } from "../ui/States";

type Candidates = components["schemas"]["Candidates"];
type PortView = components["schemas"]["PortView"];

/** Click a port, get only what fits — and a reason for the order.
 *
 * ═══ WHY THIS IS AN ANSWER AND NOT A FILTERED LIST ════════════════════════════════════════
 *
 * `n-bport`: *click an output, get only what accepts it: 6 of 1,604.* The filtering is the easy
 * half — the compatibility index has always been able to say what fits. What makes it worth
 * opening is the **order**, and the order is `producers_of`'s: `(surplus, -priority, id)`,
 * computed by `GET /pipeline/candidates`.
 *
 * So the row's reason is arithmetic. *The only producer of `alignment.bam[coordinate_sorted]`*
 * is a fact the registry produced, not a sentence somebody wrote beside a list they sorted
 * alphabetically — which would be a `why:`-less value wearing a UI costume, the exact failure
 * this product exists to prevent.
 *
 * ═══ NO RULE LIVES HERE ═══════════════════════════════════════════════════════════════════
 *
 * **Nothing in this file parses a signature.** No `split("[")`, no type-id comparison, no state
 * arithmetic. `useCompatibility.ts`'s header names that as drift this repository has already
 * paid for twice — the tier vocabulary hardcoded in a React file, the `Standing` union declared
 * in two places — and a `type_id` plus a `states` array go to the server as they came.
 *
 * ═══ IT IS KEYBOARD-FIRST ═════════════════════════════════════════════════════════════════
 *
 * The 2026-08-29 walk found the module palette absent from the accessibility tree, so drag and
 * double-click were the only two ways to add a step. A popover that opens under the cursor and
 * can only be used with it would be that defect, rebuilt.
 *
 * **Search sits inside**, for when six becomes sixty. It is not how the list comes to exist.
 */
export function Picker({ port, node, at, onPick, onClose }: {
  port: PortView;
  node: string;
  /** Where to draw it, in SCREEN coordinates — `Builder`'s `onScreen` has already applied the
   *  view transform and the canvas's offset in the page. */
  at: { x: number; y: number };
  /** Take this candidate: add the step and draw the wire. */
  onPick: (contractId: string, theirPort: string) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const box = useRef<HTMLDivElement>(null);

  // **An output asks what would ACCEPT it; an input asks what PRODUCES what it needs.** The
  // two are different questions and only the second has the resolver's ordering behind it,
  // which `services/candidates.py` states rather than glossing.
  const side = port.side === "out" ? "consuming" : "producing";
  const states = (port.states ?? []).join(",");

  const found = useQuery({
    queryKey: ["candidates", port.type_id, states, side],
    queryFn: () =>
      get<Candidates>(
        `/pipeline/candidates?type_id=${encodeURIComponent(port.type_id)}`
        + `&states=${encodeURIComponent(states)}&side=${side}`,
      ),
  });

  const rows = (found.data?.candidates ?? []).filter((row) =>
    query.trim() === "" || row.tool.toLowerCase().includes(query.trim().toLowerCase()));

  useEffect(() => setCursor(0), [query, found.data]);

  // Focus on open, so the first keystroke goes somewhere useful.
  useEffect(() => {
    box.current?.querySelector("input")?.focus();
  }, []);

  return (
    <div
      ref={box}
      data-testid="picker"
      role="dialog"
      aria-label={`what can connect to ${port.name}`}
      style={{ left: at.x, top: at.y }}
      className="fixed z-30 w-[340px] bg-surface border border-line-2 rounded-r shadow-e3
                 overflow-hidden settle"
      onKeyDown={(e) => {
        if (e.key === "Escape") { e.stopPropagation(); onClose(); return; }
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setCursor((n) => Math.min(n + 1, rows.length - 1));
        }
        if (e.key === "ArrowUp") { e.preventDefault(); setCursor((n) => Math.max(n - 1, 0)); }
        if (e.key === "Enter" && rows[cursor]) {
          e.preventDefault();
          onPick(rows[cursor].contract_id, rows[cursor].port);
        }
      }}
    >
      <div className="px-3 py-2 border-b border-line flex items-baseline gap-2">
        <span className="text-label uppercase tracking-[.13em] text-ink-3">
          {port.side === "out" ? "accepts" : "produces"}
        </span>
        <span className="font-data text-secondary text-ink truncate">
          {port.type_id}
          {(port.states ?? []).length > 0 && (
            <span className="text-ink-3">[{(port.states ?? []).join(", ")}]</span>
          )}
        </span>
        {/* **The filtered count is the useful number either way.** #77 means a catalogue total
            is aspirational — discovery reads vendored modules only — so this is the registry's
            own count, which is the honest denominator for a filtered list. */}
        {found.data && (
          <span className="ml-auto text-secondary text-ink-3 tnum shrink-0">
            {rows.length} of {found.data.total}
          </span>
        )}
      </div>

      <input
        aria-label="search"
        value={query}
        placeholder="search"
        onChange={(e) => setQuery(e.target.value)}
        className="w-full px-3 py-2 bg-transparent border-0 border-b border-line outline-none
                   text-body text-ink placeholder:text-ink-3"
      />

      <div className="max-h-[280px] overflow-auto">
        {found.isLoading && <Loading what="what fits" />}
        {found.error && <Failed error={found.error} />}
        {found.data && rows.length === 0 && (
          // **Absence is absence, and it is informative here.** Nothing in this registry can
          // feed this port — which is a fact about the registry, not an empty search result.
          <p className="px-3 py-4 text-secondary text-ink-3 m-0">
            {query
              ? "nothing here matches that."
              : "nothing in this registry can connect here."}
          </p>
        )}
        {rows.map((row, n) => (
          <button
            key={row.contract_id + row.port}
            type="button"
            data-testid="candidate"
            data-active={n === cursor || undefined}
            onMouseEnter={() => setCursor(n)}
            onClick={() => onPick(row.contract_id, row.port)}
            className="w-full text-left px-3 py-2 bg-transparent border-0 cursor-pointer
                       flex flex-col gap-0.5 data-[active]:bg-surface-2"
          >
            <span className="flex items-baseline gap-2">
              <span className="font-data text-body text-ink">{row.tool}</span>
              {/* Two contracts can declare the same process — `comeni/profile/fastqc` and
                  `nf-core/fastqc` both say FASTQC — so a row is identified by its contract. */}
              <span className="ml-auto font-data text-label text-ink-3 truncate">
                {row.contract_id}
              </span>
            </span>
            <span className="text-secondary text-ink-3">{row.why}</span>
          </button>
        ))}
      </div>

      <div className="px-3 py-1.5 border-t border-line text-label text-ink-3">
        {node} · ↑↓ to move · enter to add · esc to close
      </div>
    </div>
  );
}
