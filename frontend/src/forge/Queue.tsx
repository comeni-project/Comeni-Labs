import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { get } from "../api/client";
import { Empty, Failed, Loading } from "../ui/States";
import { Controls } from "./Controls";
import { useRowKeys } from "./useRowKeys";
import type { components } from "../api/schema";
import { QueueRow } from "./QueueRow";

type QueueResponse = components["schemas"]["QueueResponse"];
type Strip = components["schemas"]["Strip"];

/** The health strip. O(1) — it never grows with the registry, which is why it can sit
 *  above everything without becoming a list. */
function Health() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: () => get<Strip>("/health/registry") });
  if (!data) return <div className="h-[34px] border-b border-line bg-surface-2" />;
  // Until a check has run, `matching` and `unverifiable` are 0 because nothing was
  // measured — not because nothing matches. Rendering "0 match their source" on a fresh
  // database reads as catastrophe when the truth is "unknown", so those two are withheld
  // rather than shown as zeroes. Found by running against an empty database.
  const checked = data.checked_at !== null;
  return (
    <div className="flex items-center gap-6 px-6 h-[34px] bg-surface-2 border-b border-line
                    text-secondary text-ink-2">
      <span><b className="font-data text-ink">{data.contracts}</b> contracts</span>
      {checked && <span><b className="font-data text-ink">{data.matching}</b> match their source</span>}
      {checked && data.unverifiable > 0 && (
        // Reported rather than folded into `matching`: a contract nothing checks looks
        // exactly like a contract that agrees.
        <span><b className="font-data text-ink">{data.unverifiable}</b> unverifiable</span>
      )}
      <span><b className="font-data text-ink">{data.types}</b> declared types</span>
      <span className="ml-auto text-ink-3">
        {data.checked_at
          ? <>sources checked <span className="font-data">{new Date(data.checked_at).toLocaleString()}</span>
              {" · next 03:00"}</>
          // **The unchecked branch does not gain it.** Phase 4 withheld "next nightly" because
          // nothing scheduled anything; phase 8 scheduled it, so the CHECKED branch can say
          // when the next one is. A fresh database has still never been checked, and saying
          // when the next one falls does not make the last one exist.
          : "sources not checked yet"}
      </span>
    </div>
  );
}

/** The facet rail. SIX kinds of work, fixed — this is the part that must not grow with
 *  the registry, and it is why one page is enough. */
function Facets({ questions }: { questions: QueueResponse["questions"] }) {
  const count = (band: string) => questions.filter((q) => q.band === band).length;
  const rows: [string, number, string][] = [
    ["Needs you", count("routing"), "text-ink"],
    ["Cosmetic", count("cosmetic"), "text-ink-2"],
    ["Prose", count("prose"), "text-ink-2"],
  ];
  return (
    <div className="border-r border-line p-6 flex flex-col">
      <div className="text-label uppercase tracking-[.13em] font-semibold text-ink-3 mb-3">
        Needs a human
      </div>
      {rows.map(([label, n, tone]) => (
        <div key={label} className="flex items-baseline gap-4 py-2 text-body">
          <span className={tone}>{label}</span>
          <b className="ml-auto font-data text-secondary font-semibold">{n}</b>
        </div>
      ))}
      <div className="mt-auto text-label text-ink-3 leading-7">
        <div><span className="font-data">J</span> / <span className="font-data">K</span> move</div>
        <div><span className="font-data">A</span> accept · <span className="font-data">E</span> evidence</div>
      </div>
    </div>
  );
}

export { Health };

export function Queue() {
  const [params] = useSearchParams();
  const search = params.toString();
  const { data, isLoading, error } = useQuery({
    // The URL is part of the key, so changing a control refetches rather than showing the
    // previous answer under new controls. `useAnswer` invalidates `["questions"]`, which is
    // a PREFIX of this — TanStack invalidates by prefix, so answering still refreshes every
    // filtered view. Do not narrow that key.
    queryKey: ["questions", search],
    queryFn: () => get<QueueResponse>(`/questions${search ? `?${search}` : ""}`),
  });

  const questions = data?.questions ?? [];
  const { index } = useRowKeys(questions.map((q) => q.subject));
  const grouped = params.get("group") === "module";

  return (
    <div className="grid grid-rows-[34px_1fr] overflow-hidden">
      <Health />
      <div className="grid grid-cols-[216px_1fr] overflow-hidden">
        <Facets questions={questions} />
        <div className="overflow-auto">
          <Controls rows={data?.questions.length} total={data?.total} />

          {isLoading && <Loading what="the workspace" />}
          {error && <Failed error={error} />}
          {questions.length === 0 && !isLoading && (
            <Empty title="Nothing open." next="Draft a module to give the queue work." />
          )}
          {questions.map((q, i) => (
            // The key carries `asked_by` because under `group=module` the same subject
            // appears once per draft, and a duplicate React key renders one row and drops
            // the rest.
            <QueueRow
              key={`${q.subject}:${q.suggested}:${q.asked_by.join(",")}`}
              q={q}
              selected={i === index}
              // Only on the first row of each module, so a run of rows reads as one block
              // rather than repeating its own title.
              heading={
                grouped && q.asked_by[0] !== questions[i - 1]?.asked_by[0]
                  ? q.asked_by[0]
                  : undefined
              }
            />
          ))}
        </div>
      </div>
    </div>
  );
}
