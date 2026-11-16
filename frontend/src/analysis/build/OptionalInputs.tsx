import { useState } from "react";

import type { AnsweredStep } from "../../build/useBuilder";
import { useTypeNames } from "../../build/living/useTypeNames";

type Port = AnsweredStep["ports"][number];
export type InputState = "off" | "optional" | "required";

const STATES: { value: InputState; label: string; title: string }[] = [
  { value: "off", label: "Off", title: "The tool runs without it" },
  { value: "optional", label: "If given", title: "Each run may give it or leave it empty" },
  { value: "required", label: "Always", title: "Every run gives it" },
];

const inUse = (p: Port) => p.met || p.state === "optional" || p.state === "required";
const GROUP_WORDS: Record<string, string> = {
  one_of: "Pick exactly one", any_of: "Pick at least one", all_or_none: "Both or neither",
};

/** **Optional inputs, laid out by the tool's rules** (#460, #511): each says what it adds, what it
 *  needs, what it cannot be used with, and why a switch is off; a group is drawn as what it means
 *  — a choice of one, a checklist that needs one, or a pair that goes together. Rules only the run
 *  can settle say so. The engine evaluates every rule (`StepView.rules`); this only lays them out. */
export function OptionalInputs({ step, onSwitch }: {
  step: AnsweredStep;
  onSwitch?: (port: string, state: InputState) => void;
}) {
  const typeName = useTypeNames();
  const [find, setFind] = useState("");
  const optional = step.ports.filter((p) => p.side === "in" && p.optional);
  const rules = step.rules ?? [];
  const byName = new Map(optional.map((p) => [p.name, p]));
  const groups = rules.filter((r) => r.kind in GROUP_WORDS);
  const grouped = new Set(groups.flatMap((g) => g.names));
  const loose = optional.filter((p) => !grouped.has(p.name)
    && p.name.toLowerCase().includes(find.trim().toLowerCase()));
  if (optional.length === 0 && groups.length === 0) return null;
  const used = optional.filter(inUse).length;

  /** What blocks switching `port` on: a rule forbidding it beside an input in use. */
  const blockedBy = (port: string): string | null => {
    for (const r of rules.filter((x) => x.kind === "forbids")) {
      const other = r.when.includes(port) ? r.names.find((n) => byName.get(n) && inUse(byName.get(n)!))
        : r.names.includes(port) ? r.when.find((n) => byName.get(n) && inUse(byName.get(n)!)) : undefined;
      if (other) return other;
    }
    return null;
  };
  const switchTo = (port: string, state: InputState) => {
    onSwitch?.(port, state);
    // Switching one on that needs another switches that one on too, as the rule says.
    if (state !== "off") {
      for (const r of rules.filter((x) => x.kind === "requires" && x.when.includes(port))) {
        for (const needed of r.names) {
          const p = byName.get(needed);
          if (p && !inUse(p)) onSwitch?.(needed, state);
        }
      }
    }
  };

  const row = (p: Port, control?: React.ReactNode) => {
    const blocked = !inUse(p) ? blockedBy(p.name) : null;
    const needs = rules.filter((r) => r.kind === "requires" && r.when.includes(p.name));
    const neededBy = rules.filter((r) => r.kind === "requires" && r.names.includes(p.name) && r.when.length > 0);
    const notWith = rules.filter((r) => r.kind === "forbids" && (r.when.includes(p.name) || r.names.includes(p.name)));
    // A group says its own broken rule, once, on the group.
    const broken = rules.filter((r) => r.broken && !(r.kind in GROUP_WORDS)
      && (r.when.includes(p.name) || r.names.includes(p.name)));
    const atRun = rules.some((r) => r.at_run && (r.when.includes(p.name) || r.names.includes(p.name)));
    const state = (p.state ?? (p.met ? "required" : "off")) as InputState;
    return (
      <li key={p.name} data-testid={`optional-${p.name}`} className="flex flex-col gap-[6px] px-5 py-[10px] border-t border-line-soft first:border-t-0">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="font-data text-[12.5px] text-ink">{p.name}</span>
          <span className="text-[12px] text-ink-3">{typeName(p.type_id || p.accepts[0] || "")}</span>
          <span className="ml-auto">{control ?? (
            <span role="radiogroup" aria-label={`${p.name}: off, if given or always`} className="inline-flex rounded-control border border-line-2 overflow-hidden">
              {STATES.map(({ value, label, title }) => {
                const on = state === value;
                const disabled = !onSwitch || (value !== "off" && !!blocked);
                return (
                  <button key={value} type="button" role="radio" aria-checked={on} title={title} disabled={disabled}
                          onClick={() => switchTo(p.name, value)}
                          className={`h-[26px] px-[9px] border-0 text-[11.5px] font-semibold cursor-pointer disabled:cursor-not-allowed disabled:opacity-40
                                      ${on ? "bg-now-soft text-now-ink" : "bg-surface text-ink-2 hover:text-ink"}`}>
                    {label}
                  </button>
                );
              })}
            </span>
          )}</span>
        </div>
        {(p.adds ?? []).length > 0 && <span className="text-[12px] text-ink-2">Adds {(p.adds ?? []).join(", ")}.</span>}
        {needs.map((r) => (
          <span key={`needs-${r.says}`} className="text-[12px] text-ink-2">Needs {r.names.join(", ")}: switching it on switches {r.names.length > 1 ? "them" : "it"} on too.</span>
        ))}
        {neededBy.map((r) => (
          <span key={`by-${r.says}`} className="text-[12px] text-ink-2">Needed when {r.when.join(", ")} is used.</span>
        ))}
        {notWith.map((r) => (
          <span key={`not-${r.says}`} className="text-[12px] text-ink-2">Cannot be used with {(r.when.includes(p.name) ? r.names : r.when).join(", ")}.</span>
        ))}
        {blocked && <span className="text-[12px] text-measured-ink">Off because {blocked} is on. Switch {blocked} off to use this.</span>}
        {broken.map((r) => <span key={`broken-${r.says}`} role="alert" className="text-[12px] text-needs-you-ink">{r.says}</span>)}
        {atRun && <span className="text-[11.5px] text-ink-3">Checked when the run starts, since each run may leave an input empty.</span>}
        {p.reason && <span className="text-[11.5px] text-ink-3">{p.reason}</span>}
      </li>
    );
  };

  return (
    <div role="group" aria-label="Optional inputs" className="flex flex-col border-t border-line-soft pb-2">
      <div className="flex items-center gap-2 px-5 pt-3 pb-1">
        <span className="text-[12.5px] font-semibold text-ink-2">Optional inputs</span>
        <span className="text-[12px] text-ink-3">{used} of {optional.length} in use</span>
      </div>
      {optional.length > 8 && (
        <div className="px-5 pb-2">
          <input aria-label="Find an optional input" placeholder="Find an input" value={find} onChange={(e) => setFind(e.target.value)}
                 className="w-full h-[30px] px-2 rounded-control border border-line-2 bg-surface text-[12.5px] text-ink" />
        </div>
      )}
      {groups.map((g) => {
        const members = g.names.map((n) => byName.get(n)).filter(Boolean) as Port[];
        const others = g.names.filter((n) => !byName.has(n));
        return (
          <section key={g.says} aria-label={GROUP_WORDS[g.kind]} data-testid={`group-${g.kind}`}
                   className={`mx-5 my-2 rounded-control border ${g.broken ? "border-needs-you-line" : "border-line"}`}>
            <header className="flex flex-wrap items-baseline gap-2 px-3 pt-2">
              <span className="text-[12px] font-semibold text-ink">{GROUP_WORDS[g.kind]}</span>
              {g.when.length > 0 && <span className="text-[11.5px] text-ink-3">when {g.when.join(", ")} is used</span>}
            </header>
            <ul className="list-none m-0 p-0">
              {members.map((p) => row(p, g.kind === "one_of" ? (
                <input type="radio" name={`group-${g.says}`} aria-label={`Use ${p.name}`} checked={inUse(p)} disabled={!onSwitch}
                       onChange={() => { for (const m of members) switchTo(m.name, m === p ? "required" : "off"); }}
                       className="accent-[var(--now)] w-[15px] h-[15px]" />
              ) : g.kind === "any_of" ? (
                <input type="checkbox" aria-label={`Use ${p.name}`} checked={inUse(p)} disabled={!onSwitch}
                       onChange={(e) => switchTo(p.name, e.target.checked ? "required" : "off")}
                       className="accent-[var(--now)] w-[15px] h-[15px]" />
              ) : undefined))}
            </ul>
            {g.kind === "all_or_none" && members.length > 0 && onSwitch && (
              <div className="flex gap-2 px-3 pb-2">
                <button type="button" onClick={() => members.forEach((m) => switchTo(m.name, "required"))}
                        className="h-[26px] px-[10px] rounded-control border border-line-2 bg-surface text-[11.5px] font-semibold text-ink cursor-pointer">Use both</button>
                <button type="button" onClick={() => members.forEach((m) => switchTo(m.name, "off"))}
                        className="h-[26px] px-[10px] rounded-control border border-line-2 bg-surface text-[11.5px] font-semibold text-ink-2 cursor-pointer">Use neither</button>
              </div>
            )}
            {others.length > 0 && <p className="m-0 px-3 pb-2 text-[11.5px] text-ink-3">Also counts: {others.join(", ")} (a setting).</p>}
            {g.broken && <p role="alert" className="m-0 px-3 pb-2 text-[12px] text-needs-you-ink">{g.says}</p>}
          </section>
        );
      })}
      <ul className="list-none m-0 p-0">{loose.map((p) => row(p))}</ul>
    </div>
  );
}
