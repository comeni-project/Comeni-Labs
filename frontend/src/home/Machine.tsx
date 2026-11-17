import { useQuery } from "@tanstack/react-query";

import { get } from "../api/client";
import type { components } from "../api/schema";

type Machine = components["schemas"]["Machine"];

/** *This machine*: what a run here has to work with. Absent when the server does not say. */
export function ThisMachine() {
  const machine = useQuery({
    queryKey: ["machine"],
    queryFn: () => get<Machine>("/data/machine"),
    refetchInterval: 15_000,
    retry: false,
  });
  const m = machine.data;
  if (!m) return null;
  const used = Math.max(0, Math.round(m.memory_gb - m.memory_free_gb));
  return (
    <section aria-label="This machine"
             className="flex flex-wrap items-center gap-x-7 gap-y-3 px-5 py-3 rounded-panel border border-line bg-surface">
      <h2 className="m-0 text-[13.5px] font-semibold text-ink">This machine</h2>
      <Meter label="CPU" share={m.load / m.cpus} value={`${Math.round(m.load)}/${m.cpus}`} />
      <Meter label="Memory" share={used / (m.memory_gb || 1)} value={`${used}/${Math.round(m.memory_gb)} GB`} />
      <div className="flex items-center gap-3 text-[12.5px] text-ink-2">
        Disk free <span className="font-data text-ink">{`${Math.round(m.disk_free_gb)} GB`}</span>
      </div>
    </section>
  );
}

function Meter({ label, share, value }: { label: string; share: number; value: string }) {
  const pct = Math.round(Math.min(1, Math.max(0, share)) * 100);
  return (
    <div className="flex items-center gap-3 text-[12.5px] text-ink-2 min-w-[200px] grow">
      {label}
      <div role="meter" aria-label={label} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
           className="grow h-[6px] rounded-full bg-line-soft overflow-hidden">
        <div className="h-full bg-now-mid" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-data text-ink">{value}</span>
    </div>
  );
}
