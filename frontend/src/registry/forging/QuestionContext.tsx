import { useQuery } from "@tanstack/react-query";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { Failed } from "../../ui/States";

type Context = components["schemas"]["QuestionContext"];

/** Read only while the question is open; source evidence does not belong in the polling view. */
export function QuestionContext({ id, item, revision }: { id: string; item: string; revision: number }) {
  const context = useQuery({
    queryKey: ["forge-context", id, item, revision],
    queryFn: () => get<Context>(`/forge/adaptations/${id}/context?item=${encodeURIComponent(item)}`),
  });
  if (context.isError) return <Failed error={context.error} padded={false} />;
  if (!context.data) return <p role="status">Reading the question’s context…</p>;
  const data = context.data;
  return <aside aria-label="Question context" className="flex flex-col gap-3 min-w-0 mb-3">
    <div><span className="text-[12px] text-ink-3">Engine · what your answer decides</span>
      <p className="m-0">{data.decides}</p>
      {data.optional && <p className="m-0 text-[12.5px]">Declaring this output is optional. Include it when a pipeline should be able to use it.</p>}
    </div>
    {data.upstream && <div><span className="text-[12px] text-ink-3">Upstream · module description</span>
      <p className="m-0 whitespace-pre-wrap">{data.upstream}</p></div>}
    {!data.source_available ? <p className="m-0">Module source is unavailable.</p>
      : data.lines.length > 0 && <details>
        <summary className="cursor-pointer">From main.nf</summary>
        <pre className="font-data text-[12px] whitespace-pre-wrap break-words max-w-full overflow-auto">{data.lines.map((line) => `${line.number}  ${line.text}`).join("\n")}</pre>
      </details>}
    {data.choices.map((choice) => <div key={choice.id} className="border-l-2 border-line pl-3">
      <span className="text-[12px] text-ink-3">{choice.proposed ? "Proposed vocabulary · needs review" : "Curated · registry"}</span>
      <p className="m-0 font-medium">{choice.name ?? choice.id}</p>
      {choice.name && <span className="font-data text-[12px]">{choice.id}</span>}
      {choice.explain && <p className="m-0">{choice.explain}</p>}
      {choice.scope && <p className="m-0 text-[12.5px]">Scope: {choice.scope}</p>}
      <p className="m-0 text-[12.5px]">{choice.tools.length ? `Used by ${choice.tools.join(", ")}` : "No tool uses this yet."}</p>
    </div>)}
  </aside>;
}
