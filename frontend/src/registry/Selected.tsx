import { Link, useNavigate } from "react-router";

import { Failed } from "../ui/States";
import { FormatPills } from "./FormatPills";
import { useStartForge } from "./forging/useForgeActions";
import { colourOf, labelOf, StateIcon } from "./states";
import type { ModuleRow } from "./useCatalogue";
import { useFilters, useModuleDetail } from "./useCatalogue";

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
  const filters = useFilters();
  const fits = useModuleDetail(row).data?.fits;
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
           className="bg-surface border border-line rounded-panel p-[16px] flex flex-col gap-[12px]">
      <div>
        <div className="font-data text-[16px] font-medium break-all">{row.path}</div>
        {row.description && <p className="mt-[3px] mb-0 text-[13px] text-ink-2 leading-[1.5]">{row.description}</p>}
      </div>
      <div className="flex flex-col">
        <p className="m-0 mb-[3px] text-[11.5px] text-ink-3">Reads</p>
        <div className="flex flex-wrap gap-1 items-center min-h-[21px]">
          <FormatPills declared={row.formats_in} mentioned={row.mentions_in} all />
        </div>
        <div className="my-[7px] px-[11px] py-2 rounded-control border border-now bg-now-soft font-data">
          <span className="block text-[13px]">{row.name}</span>
          <span className="block text-[11.5px] text-ink-3">
            {row.state === "update_available" ? `${row.registry_version} here, ${row.tool_version} upstream` : row.tool_version ?? "unknown"}
          </span>
        </div>
        <p className="m-0 mb-[3px] text-[11.5px] text-ink-3">Makes</p>
        <div className="flex flex-wrap gap-1 items-center min-h-[21px]">
          <FormatPills declared={row.formats_out} mentioned={row.mentions_out} tone="makes" all />
        </div>
        {row.mentions_in.length + row.mentions_out.length > 0 && (
          <p className="mt-[6px] mb-0 text-[11.5px] text-ink-3">Outlined: mentioned in its description, not declared.</p>
        )}
      </div>
      {fits && (
        <div className="flex flex-col gap-1 pt-[10px] border-t border-line-soft">
          <p className="m-0 text-[11.5px] text-ink-3">Fits with your registry, by file format</p>
          {[...fits.feeds_it.map((path) => ({ path, how: "feeds it" })),
            ...fits.reads_it.map((path) => ({ path, how: "reads it" }))].slice(0, 5).map(({ path, how }) => (
            <button key={`${how}:${path}`} type="button" className="fit" onClick={() => filters.set("module", [path])}>
              <span className="text-ink-3 shrink-0">{how}</span><span className="truncate">{path}</span>
            </button>
          ))}
          {fits.feeds_it.length + fits.reads_it.length === 0 && (
            <p className="m-0 text-[12.5px] text-ink-3">No registry tool shares a format with this one yet.</p>
          )}
        </div>
      )}
      <p className={`m-0 flex items-center gap-[7px] text-[12.5px] ${colourOf(row.state)}`}>
        <StateIcon state={row.state} />{labelOf(row.state)}
      </p>
      <a className="text-[12.5px] text-ink-2" href={`https://github.com/nf-core/modules/tree/master/modules/nf-core/${row.path}`}
         target="_blank" rel="noreferrer">nf-core/modules · {row.path}</a>
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
              className="control-primary text-center no-underline">
          Open the tool
        </Link>
      ) : (
        <div className="flex flex-col gap-1">
          <button type="button" disabled={start.isPending} aria-busy={start.isPending}
                  onClick={() => start.mutate({ source: row.source, path: row.path },
                                              { onSuccess: (view) => navigate(`/registry/forging/${view.id}`) })}
                  className="control-primary">
            Forge {row.name}
          </button>
          {start.isError && <Failed error={start.error} padded={false} />}
        </div>
      )}
    </aside>
  );
}
