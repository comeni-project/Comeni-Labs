import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get } from "../../api/client";
import type { AuthoringCall as Call } from "../../api/types";
import { purposeWords } from "./format";

/** The session's model calls, each with what it returned (issues 182 and 191).
 *
 * **Asks the server only when open, and again only when the count moves** — the key carries
 * `calls`, which the session poll already brings. A closed panel costs nothing, and an open one
 * does not poll on its own (the operator's rule for 14.7.4: nothing chatty).
 */
export function CallPanel({ sessionId, calls, open }: {
  sessionId: string;
  calls: number;
  open: boolean;
}) {
  const listed = useQuery({
    queryKey: ["authoring", sessionId, "calls", calls],
    queryFn: () => get<Call[]>(`/pipeline/authoring/${sessionId}/calls`),
    enabled: open,
    staleTime: Infinity,
  });
  if (!open) return null;
  return (
    <section aria-label="model calls" className="basis-full border px-3 py-2"
             style={{ borderColor: "var(--line-2)", background: "var(--paper-2)" }}>
      {listed.isPending ? (
        <p className="m-0 font-data text-[11px] text-ink-3">reading the calls…</p>
      ) : (
        <ol className="m-0 p-0">
          {(listed.data ?? []).map((call) => <CallRow key={call.id} call={call} />)}
        </ol>
      )}
    </section>
  );
}

function CallRow({ call }: { call: Call }) {
  const [shown, setShown] = useState(false);
  const n = (value: number | null) => (value ?? 0).toLocaleString("en-US");
  return (
    <li className="list-none py-[6px]" style={{ borderBottom: "1px solid var(--line)" }}>
      <div className="flex items-baseline gap-3 font-data text-[11px]">
        <span className="text-ink">{purposeWords(call.purpose)}</span>
        <span className="text-ink-3">
          {n(call.input)} in · {n(call.output)} out{call.cached ? ` · ${n(call.cached)} cached` : ""}
        </span>
        <span className="text-ink-4">{call.model}</span>
        {call.duration_ms !== null && (
          <span className="text-ink-4">{(call.duration_ms / 1000).toFixed(1)}s</span>
        )}
        <span className="text-ink-4">{call.state}</span>
        {call.response && (
          <button type="button" onClick={() => setShown(!shown)}
                  className="ml-auto bg-transparent border-0 p-0 text-link cursor-pointer
                             font-data text-[11px] focus-visible:shadow-[var(--ring)]">
            {shown ? "hide reply" : "show reply"}
          </button>
        )}
      </div>
      {shown && call.response && (
        <pre className="m-0 mt-1 whitespace-pre-wrap break-words font-data text-[10.5px] text-ink-2">
          {call.response}
        </pre>
      )}
    </li>
  );
}
