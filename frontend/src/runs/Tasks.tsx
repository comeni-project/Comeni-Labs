import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef, useState } from "react";

import { Failed, Loading } from "../ui/States";
import { get } from "../wiener/api/client";
import { TaskHeader, TaskRow, type TaskView } from "./TaskRow";

type TasksPage = { tasks: TaskView[]; total: number };

/** One page. The server caps at 500 and the footer says so — §10.1, and A191 is why it can:
 *  the three resource columns are indexed, so this is an `ORDER BY`, not a fold. */
const LIMIT = 500;

const SORTS = [
  { key: "task_id", label: "task" },
  { key: "-peak_rss_bytes", label: "memory" },
  { key: "-realtime_ms", label: "time" },
] as const;

const STATUSES = ["", "COMPLETED", "FAILED", "CACHED", "RUNNING", "ABORTED"];

/** §6's second question — *what across the whole run retried* — which the expanded row cannot
 * answer because it is one process at a time.
 *
 * **Filtered, sorted and paged server-side**, never here. 5,000 rows is not an overview, and
 * sorting them in the browser would mean holding all 5,000 to sort 50.
 */
export function Tasks({ runId, processes = [] }: { runId: string; processes?: string[] }) {
  const [process, setProcess] = useState("");
  const [status, setStatus] = useState("");
  const [retriedOnly, setRetriedOnly] = useState(false);
  const [attempt, setAttempt] = useState("");
  const [tag, setTag] = useState("");
  const [sort, setSort] = useState<string>("task_id");

  const query = new URLSearchParams({ sort, limit: String(LIMIT) });
  if (process) query.set("process", process);
  if (status) query.set("status", status);
  if (retriedOnly) query.set("retried_only", "true");
  if (attempt) query.set("attempt", attempt);
  if (tag) query.set("tag", tag);

  const { data, isPending, isError, error } = useQuery({
    queryKey: ["tasks-tab", runId, query.toString()],
    queryFn: () => get<TasksPage>(`/api/runs/${runId}/tasks?${query}`),
    refetchInterval: 5_000,
  });

  const scroller = useRef<HTMLDivElement>(null);
  const rows = data?.tasks ?? [];
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => 30,
    overscan: 12,
    // **The first-paint estimate, before the scroller has been measured.** A real browser
    // replaces it on the first `ResizeObserver` callback. It is here because without it the
    // window is zero-height until measurement — which in a browser is one frame, and in a
    // test environment with no layout is forever: the virtualiser would render no rows and
    // the test asserting a BOUNDED number of rows would pass by rendering none.
    initialRect: { width: 1200, height: 600 },
  });

  const control = "text-secondary bg-surface border border-line rounded-[var(--r)] px-2 py-1";

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-line bg-surface-2">
        <label className="flex items-center gap-1.5 text-label text-ink-3">
          process
          <select aria-label="process" className={control}
                  value={process} onChange={(e) => setProcess(e.target.value)}>
            <option value="">all</option>
            {[...new Set([...processes, ...rows.map((row) => row.process)])].sort()
              .map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>

        <label className="flex items-center gap-1.5 text-label text-ink-3">
          status
          <select aria-label="status" className={control}
                  value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((name) => (
              <option key={name} value={name}>{name || "all"}</option>
            ))}
          </select>
        </label>

        {/* **`attempt`, the artboard's third control.** `retried only` answers *did anything
            retry*; this answers *which try am I looking at*, which is the question when a
            process fails on 1 and passes on 2. `3+` is a floor, not an equality — a task on
            its fifth is what somebody picking it wants. */}
        <label className="flex items-center gap-1.5 text-label text-ink-3">
          attempt
          <select aria-label="attempt" className={control}
                  value={attempt} onChange={(e) => setAttempt(e.target.value)}>
            <option value="">any</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3+</option>
          </select>
        </label>

        {/* **`tag`, and it says tag rather than sample on purpose.** `meta.id` is the sample
            for a per-sample process and something else entirely for a reference one — the
            spine tags `STAR_GENOMEGENERATE` with its FASTA, not with a sample. A control
            labelled *sample* would be lying on exactly the rows nobody thought about.

            **A free field rather than a menu, and that is the A200 line.** A menu needs a
            distinct-tags query, which is a search over lab strings across a run; the filter
            needs none, because every tag on the page is already in the table below. You pick
            one from what is in front of you. */}
        <label className="flex items-center gap-1.5 text-label text-ink-3">
          tag
          <input aria-label="tag" className={control} value={tag} placeholder="any"
                 onChange={(e) => setTag(e.target.value.trim())} />
        </label>

        <label className="flex items-center gap-1.5 text-label text-ink-3">
          <input type="checkbox" checked={retriedOnly}
                 onChange={(e) => setRetriedOnly(e.target.checked)} />
          retried only
        </label>

        {/* `412 tasks · sorted by memory` — what you are looking at and how it is ordered,
            which the artboard puts here rather than leaving the sort to be inferred. */}
        <span data-testid="tasks-count" className="ml-auto text-label text-ink-3">
          {(data?.total ?? 0).toLocaleString()} tasks · sorted by{" "}
          {SORTS.find((option) => option.key === sort)?.label ?? "task"}
        </span>
        <span className="flex items-center gap-2 text-label text-ink-3">
          sort
          {SORTS.map((option) => (
            <button
              key={option.key}
              type="button"
              data-testid={`sort-${option.key}`}
              aria-pressed={sort === option.key}
              onClick={() => setSort(option.key)}
              className={`bg-transparent border-0 cursor-pointer px-1
                          ${sort === option.key ? "text-ink font-semibold" : "hover:text-ink"}`}
              style={{ transition: `color var(--t)` }}
            >
              {option.label}
            </button>
          ))}
        </span>
      </div>

      {isPending ? (
        <Loading what="the tasks" />
      ) : isError ? (
        <Failed error={error ?? "the tasks could not be read"} />
      ) : (
        <>
          <TaskHeader showProcess />
          <div ref={scroller} className="overflow-auto max-h-[60vh]">
            <div style={{ height: virtual.getTotalSize(), position: "relative" }}>
              {virtual.getVirtualItems().map((item) => (
                <div
                  key={item.key}
                  style={{ position: "absolute", top: 0, left: 0, width: "100%",
                           transform: `translateY(${item.start}px)` }}
                >
                  <TaskRow task={rows[item.index]} showProcess />
                </div>
              ))}
            </div>
          </div>

          {/* **An empty table has to say which kind of empty it is.** `labels` arrived on
              2026-08-24 and nothing back-fills it (`TaskRow` says so on its `tag` field), so a
              run ingested before that carries no tag at all and matches nothing whatever you
              type. Rendering zero rows lets that read as *no such sample*, which is a
              different and much more alarming statement. */}
          {rows.length === 0 && (
            <p data-testid="no-tasks" className="px-4 py-3 text-secondary text-ink-3">
              {tag
                ? `no task in this run is tagged ${tag} — and a run ingested before tags were `
                  + `projected carries none at all, so an older run matches nothing here.`
                : "no task matches these filters"}
            </p>
          )}

          {/* **Never a silent truncation.** The server caps a page at 500; a table that showed
              500 of 5,000 without saying so reads as a complete answer to the filter above it. */}
          {data.total > rows.length && (
            <p data-testid="not-drawn" className="px-4 py-2 text-label text-ink-3 border-t
                                                  border-line">
              showing {rows.length.toLocaleString()} of {data.total.toLocaleString()} — narrow
              the filters to see the rest
            </p>
          )}
        </>
      )}
    </div>
  );
}
