import { useQuery } from "@tanstack/react-query";

import { get } from "../wiener/api/client";

type ProcessStats = {
  process: string; tasks: number;
  memory_asked_bytes: number | null; memory_peak_bytes: number | null;
  cpus_asked: number | null; cpu_used_pct: number | null;
  realtime_ms: number | null; queue_wait_ms: number | null;
  read_bytes: number | null; write_bytes: number | null;
};

function bytes(value: number | null): string {
  if (value === null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value, unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
  return `${size < 10 && unit > 0 ? size.toFixed(1) : Math.round(size)} ${units[unit]}`;
}

function seconds(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  const total = Math.round(ms / 1000);
  return total < 60 ? `${total}s` : `${Math.floor(total / 60)}m ${String(total % 60).padStart(2, "0")}s`;
}

/** One comparison: what was asked for, what was used, and how close that came.
 *
 * **The bar is the used half against the asked half**, so a nearly-full bar is the next exit
 * 137 and an almost-empty one is capacity nobody needed. A row with no `asked` draws no bar —
 * §9.3's own note that a pipeline requesting nothing cannot be over-provisioned. */
function Pair({ label, asked, used, ratio }: {
  label: string; asked: string; used: string; ratio: number | null;
}) {
  const tight = ratio !== null && ratio > 0.8;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-label text-ink-3">{label}</span>
      <span className="font-data text-secondary text-ink">
        {used} <span className="text-ink-3">of {asked}</span>
      </span>
      {ratio !== null && (
        <span className="h-1 rounded-full overflow-hidden" style={{ background: "var(--line)" }}>
          <span
            className="block h-full"
            style={{
              width: `${Math.min(100, Math.max(1, ratio * 100))}%`,
              background: tight ? "var(--undecided)" : "var(--pea)",
            }}
          />
        </span>
      )}
    </div>
  );
}

function Row({ row }: { row: ProcessStats }) {
  const reported = row.memory_peak_bytes !== null || row.cpu_used_pct !== null;
  const memoryRatio = row.memory_asked_bytes && row.memory_peak_bytes
    ? row.memory_peak_bytes / row.memory_asked_bytes : null;
  const cpuRatio = row.cpus_asked && row.cpu_used_pct
    ? row.cpu_used_pct / 100 / row.cpus_asked : null;

  return (
    <div data-testid={`stats-${row.process}`}
         className="px-4 py-3 border-b border-line last:border-b-0 flex flex-col gap-2">
      <span className="flex items-baseline gap-3">
        <span className="font-data text-body text-ink">{row.process}</span>
        <span className="text-label text-ink-3">
          {row.tasks} {row.tasks === 1 ? "task" : "tasks"} · worst case
        </span>
      </span>

      {reported ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Pair label="memory" asked={bytes(row.memory_asked_bytes)}
                used={bytes(row.memory_peak_bytes)} ratio={memoryRatio} />
          <Pair label="cpu" asked={row.cpus_asked === null ? "—" : `${row.cpus_asked} cores`}
                used={row.cpu_used_pct === null ? "—" : `${(row.cpu_used_pct / 100).toFixed(1)} cores`}
                ratio={cpuRatio} />
          <Pair label="time" asked={seconds(row.realtime_ms)}
                used={`${seconds(row.queue_wait_ms)} queued`} ratio={null} />
          <Pair label="i/o" asked={bytes(row.write_bytes)}
                used={`${bytes(row.read_bytes)} read`} ratio={null} />
        </div>
      ) : (
        // **Absent is not zero.** Four bars against nothing would read as a process that used
        // no memory — §4.3 finding 6: the resource fields are opt-in, and this run's launcher
        // did not turn them on.
        <p className="text-secondary text-ink-3">
          No resource metrics were recorded for this run.
        </p>
      )}
    </div>
  );
}

export function Stats({ runId }: { runId: string }) {
  const rows = useQuery({
    queryKey: ["run-stats", runId],
    queryFn: () => get<ProcessStats[]>(`/api/runs/${runId}/stats`),
    refetchInterval: 10_000,
  });

  if (!rows.data?.length) return null;

  return (
    <section data-testid="stats" className="bg-surface border border-line rounded-[var(--r)]">
      <p className="px-4 py-2 text-label text-ink-3 border-b border-line bg-surface-2">
        Asked against used — per process, worst case kept
      </p>
      {rows.data.map((row) => <Row key={row.process} row={row} />)}
    </section>
  );
}
