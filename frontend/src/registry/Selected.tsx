import { Link, useNavigate } from "react-router";

import { Failed } from "../ui/States";
import { useStartForge } from "./forging/useForgeActions";

import { colourOf, labelOf } from "./states";
import type { ModuleRow } from "./useCatalogue";

const NEXT: Record<string, (row: ModuleRow) => string> = {
  imported: () => "In the registry the builder loads. The builder can choose it.",
  update_available: (row) =>
    `The registry has ${row.registry_version}; nf-core now packages ${row.tool_version}. ` +
    "Updating re-forges the tool and opens a pull request that replaces it.",
  unknown: () =>
    "In the registry, but nf-core's tool version for it could not be read, so it cannot be " +
    "compared.",
  gone_upstream: () =>
    "In the registry, but nf-core no longer has a module at this path: it was renamed or " +
    "removed upstream.",
  not_imported: () =>
    "Not in the registry yet. Forging it: you answer a few questions, the AI drafts the " +
    "contract, parameters, vocabulary, rules and tests, and you approve each.",
};

/** Board 1's right column: the selected module, what comes next, and its one action. A tool the
 *  registry holds opens its page; anything else starts forging it (forge MVP 3). */
export function Selected({ row }: { row: ModuleRow | undefined }) {
  const start = useStartForge();
  const navigate = useNavigate();
  if (!row) {
    return (
      <aside aria-label="Selected module" className="bg-surface border border-line rounded-panel p-[22px] text-ink-3">
        Pick a module to see what it reads and makes.
      </aside>
    );
  }
  const held = row.contract_id !== null && row.contract_id !== undefined;
  return (
    <aside aria-label="Selected module"
           className="bg-surface border border-line rounded-panel p-[22px] flex flex-col gap-[18px]">
      <div>
        <div className="font-data text-[17px] font-medium">{row.name}</div>
        {row.description && <p className="mt-[6px] mb-0 text-ink-2 leading-[1.5]">{row.description}</p>}
      </div>
      <dl className="m-0 grid grid-cols-[96px_minmax(0,1fr)] gap-x-3 gap-y-[10px] text-[13px]">
        <dt className="text-ink-3">Reads</dt>
        <dd className="m-0 font-data">{row.formats_in.join(", ") || "—"}</dd>
        <dt className="text-ink-3">Makes</dt>
        <dd className="m-0 font-data">{row.formats_out.join(", ") || "—"}</dd>
        <dt className="text-ink-3">Tool version</dt>
        <dd className="m-0 font-data">{row.tool_version ?? "unknown"}</dd>
        <dt className="text-ink-3">Registry</dt>
        <dd className={`m-0 ${colourOf(row.state)}`}>{labelOf(row.state)}</dd>
        <dt className="text-ink-3">Upstream</dt>
        <dd className="m-0">
          <a href={`https://github.com/nf-core/modules/tree/master/modules/nf-core/${row.path}`}
             target="_blank" rel="noreferrer">nf-core/modules · {row.path}</a>
        </dd>
      </dl>
      {row.problems.length > 0 && (
        <ul className="m-0 pl-4 text-[12.5px] text-ink-3">
          {row.problems.map((p) => <li key={p.code}><span className="font-data">{p.code}</span> {p.says}</li>)}
        </ul>
      )}
      <div className="p-[14px] rounded-control bg-paper-2 border border-line text-[13px] text-ink-2 leading-[1.5]">
        {(NEXT[row.state] ?? NEXT.not_imported)(row)}
      </div>
      {held ? (
        <Link to={`/registry/tools/${row.contract_id}`}
              className="self-start px-6 py-[11px] rounded-button bg-action text-on-action font-semibold no-underline shadow-raise">
          Open the tool
        </Link>
      ) : (
        <div className="flex flex-col gap-1">
          <button type="button" disabled={start.isPending}
                  onClick={() => start.mutate({ source: row.source, path: row.path },
                                              { onSuccess: (view) => navigate(`/registry/forging/${view.id}`) })}
                  className="self-start px-6 py-[11px] rounded-button bg-action text-on-action font-semibold shadow-raise">
            Forge {row.name}
          </button>
          {start.isError && <Failed error={start.error} padded={false} />}
        </div>
      )}
    </aside>
  );
}
