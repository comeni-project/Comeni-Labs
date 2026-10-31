import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router";

import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { useStartForge } from "./forging/useForgeActions";
import { RegistryTabs } from "./RegistryTabs";
import { colourOf, labelOf, StateIcon } from "./states";

type ModulePage = components["schemas"]["ModulePage"];

/** A read that keeps the API's coded refusal (`MF0504: …`) as the error, so `Failed` can show
 *  it; the shared `get` reduces every failure to its status. */
async function read<T>(path: string): Promise<T> {
  const r = await fetch(`/api${path}`);
  const body = await r.json().catch(() => null);
  if (!r.ok) throw new Error(body?.detail ?? `${path} → ${r.status}`);
  return body as T;
}

const panel = "bg-surface border border-line rounded-panel overflow-hidden";
const heading = "m-0 px-5 py-4 text-[15px] font-semibold border-b border-line";

/** `/registry/tools/<contract id>`: an imported tool as the registry holds it (board 2, forge MVP
 *  part 1). Every value and reason is the registry's own; nothing it does not hold is drawn. */
export function Tool() {
  const id = useParams()["*"] ?? "";
  const page = useQuery({
    queryKey: ["tool", id],
    queryFn: () => read<ModulePage>(`/registry/tools/${id}`),
    // A coded refusal is the server's answer, not a hiccup: asking again changes nothing.
    retry: (count, error) => !/^[A-Z]{2}\d{4}:/.test(error.message) && count < 3,
  });
  const tool = page.data;
  const path = tool?.upstream?.path.replace(/^modules\/nf-core\//, "") ?? id;
  useTitle(path);

  return (
    <div className="min-h-full bg-paper">
      <RegistryTabs registryAt={tool?.registry_at} />
      <main className="frame gutter pt-6 pb-12">
        <nav aria-label="Breadcrumb" className="text-[13px] text-ink-3 mb-[14px]">
          <Link to="/registry">Catalogue</Link> / <span className="font-data">{path}</span>
        </nav>
        {page.isPending && <Loading what="the tool" />}
        {page.isError && <Failed error={page.error} padded={false} />}
        {tool && <Body tool={tool} path={path} />}
      </main>
    </div>
  );
}

function Body({ tool, path }: { tool: ModulePage; path: string }) {
  const state = tool.catalogue?.row.state ?? "imported";
  return (
    <>
      <div className="flex flex-wrap items-start gap-4 mb-[22px]">
        <div className="flex-[1_1_480px]">
          <h1 className="m-0 font-data text-[26px] font-medium">{path}</h1>
          {tool.description && <p className="mt-[6px] mb-0 text-ink-2 text-[15px]">{tool.name}: {tool.description}</p>}
        </div>
        <span className={`inline-flex items-center gap-[7px] px-3 py-[6px] rounded-full bg-surface border border-line text-[13px] font-medium ${colourOf(state)}`}>
          <StateIcon state={state} />{labelOf(state)}
        </span>
      </div>
      <div className="flex flex-wrap gap-6 items-start">
        <div className="flex-[999_1_600px] min-w-0 flex flex-col gap-5">
          <Ports tool={tool} />
          <Settings tool={tool} />
          <Rules tool={tool} />
          <section aria-labelledby="tool-tests" className={panel}>
            <h2 id="tool-tests" className={heading}>Tests</h2>
            {tool.tests.length > 0 ? (
              <ul className="m-0 p-0 list-none">
                {tool.tests.map((test) => (
                  <li key={test.name} className="px-5 py-3 border-t border-line-soft flex flex-wrap gap-x-4">
                    <span className="font-data font-medium">{test.name}</span>
                    <span className="font-data text-[13px] text-ink-2">{test.feeds.join(", ")} → {test.expects.join(", ")}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="m-0 px-5 py-4 text-ink-2">
                No tests yet. Tools added before the forge have none; re-forge the tool to add them.
              </p>
            )}
          </section>
        </div>
        <aside aria-label="Where it comes from" className="flex-[1_1_280px] max-w-[340px] flex flex-col gap-4">
          <Origin tool={tool} />
          <NfCore tool={tool} />
          <div className="bg-surface border border-line rounded-panel px-5 py-[18px]">
            <h2 className="m-0 mb-2 text-[14px] font-semibold">Change it</h2>
            <p className="m-0 mb-[14px] text-[13px] text-ink-2 leading-[1.5]">
              Re-forging opens a pull request that replaces this tool.
            </p>
            <Reforge tool={tool} />
          </div>
        </aside>
      </div>
    </>
  );
}

function Reforge({ tool }: { tool: ModulePage }) {
  const start = useStartForge();
  const navigate = useNavigate();
  const path = tool.upstream?.path.replace(/^modules\/nf-core\//, "");
  if (!path) return <p className="m-0 text-[12px] text-ink-3">Not from nf-core, so it cannot be re-forged here.</p>;
  return (
    <>
      <button type="button" disabled={start.isPending}
              onClick={() => start.mutate({ source: "nf-core", path, reforge: tool.id },
                                          { onSuccess: (view) => navigate(`/registry/forging/${view.id}`) })}
              className="px-4 py-[9px] rounded-control border border-line-2 bg-surface font-medium">
        Re-forge
      </button>
      {start.isError && <Failed error={start.error} padded={false} />}
    </>
  );
}

function Ports({ tool }: { tool: ModulePage }) {
  const rows = [
    ...tool.consumes.map((port) => ({ side: "reads", port })),
    ...tool.produces.map((port) => ({ side: "makes", port })),
  ];
  return (
    <section aria-labelledby="tool-io" className={panel}>
      <h2 id="tool-io" className={heading}>Reads and makes</h2>
      <div className="overflow-x-auto [contain:inline-size]">
        <table className="w-full border-collapse text-[13.5px]">
          <thead>
            <tr className="text-left text-ink-3 text-[12px]">
              <th scope="col" className="px-5 py-[10px] font-medium"><span className="sr-only">Direction</span></th>
              <th scope="col" className="px-5 py-[10px] font-medium">Port</th>
              <th scope="col" className="px-5 py-[10px] font-medium">Type</th>
              <th scope="col" className="px-5 py-[10px] font-medium">States</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ side, port }) => (
              <tr key={`${side}-${port.name}`} className="border-t border-line-soft">
                <td className="px-5 py-[10px] text-ink-3">{side}</td>
                <td className="px-5 py-[10px] font-data">{port.name}</td>
                <td className="px-5 py-[10px] font-data">{port.type_id}</td>
                <td className="px-5 py-[10px] text-ink-2">{states(port)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function states(port: ModulePage["consumes"][number]) {
  const required = port.states_required ?? [];
  const conventional = port.states_conventional ?? [];
  const made = port.states_made ?? [];
  if (!required.length && !conventional.length && !made.length) return <span className="text-ink-3">—</span>;
  return (
    <>
      {required.length > 0 && <span className="font-data">{required.join(", ")}</span>}
      {made.length > 0 && <span className="font-data">{made.join(", ")}</span>}
      {conventional.length > 0 && (
        <span title={port.conventional_because ?? undefined}>
          <span className="font-data">{conventional.join(", ")}</span> by convention, not required
        </span>
      )}
    </>
  );
}

function Settings({ tool }: { tool: ModulePage }) {
  const params = tool.params ?? [];
  return (
    <section aria-labelledby="tool-settings" className={panel}>
      <h2 id="tool-settings" className={heading}>Settings</h2>
      {params.map((param) => (
        <div key={param.name} className="px-5 py-[14px] grid grid-cols-[minmax(0,220px)_minmax(0,1fr)] gap-[14px] border-b border-line-soft">
          <div>
            <div className="font-data">{param.name}</div>
            {param.asks_person
              ? <div className="mt-[6px] inline-flex px-2 py-[2px] rounded-full bg-needs-you-soft text-needs-you-ink text-[12px]">asks the person</div>
              : <div className="mt-[6px] font-data text-[12.5px] text-ink-2">default {JSON.stringify(param.default)}</div>}
          </div>
          <p className="m-0 text-ink-2 leading-[1.55]">
            {param.because ?? <span className="text-ink-3">No reason recorded.</span>}
            {param.template && <> Sent as <span className="font-data text-[12.5px]">{param.template}</span>.</>}
          </p>
        </div>
      ))}
      {tool.ext_args && (
        <div className="px-5 py-[14px] grid grid-cols-[minmax(0,220px)_minmax(0,1fr)] gap-[14px]">
          <div>
            <div className="font-data">{tool.ext_args}</div>
            <div className="mt-[6px] text-[12px] text-ink-3">always passed</div>
          </div>
          <p className="m-0 text-ink-2 leading-[1.55]">{tool.ext_args_because ?? ""}</p>
        </div>
      )}
      {params.length === 0 && !tool.ext_args && <p className="m-0 px-5 py-4 text-ink-3">No settings.</p>}
    </section>
  );
}

function Rules({ tool }: { tool: ModulePage }) {
  const rules = tool.rules ?? [];
  return (
    <section aria-labelledby="tool-rules" className={panel}>
      <h2 id="tool-rules" className={heading}>When the builder chooses it</h2>
      <div className="px-5 py-4 flex flex-col gap-3">
        {rules.map((rule, n) => (
          <div key={`${rule.role}-${n}`} className="flex flex-col gap-2">
            <p className="m-0 text-ink-2">
              Rule <span className="font-data text-[12.5px]">{rule.role}</span>
              {rule.because && <>: {rule.because}</>}{rule.cite && <>. {rule.cite}</>}.
            </p>
            <div className="grid grid-cols-[minmax(0,160px)_minmax(0,1fr)] gap-x-[14px] gap-y-[10px] text-[13.5px]">
              {rule.rows.map((row, m) => (
                <Row key={m} row={row} self={row.then === tool.id} />
              ))}
            </div>
          </div>
        ))}
        {rules.length === 0 && <p className="m-0 text-ink-3">No rule decides between this tool and another.</p>}
        {tool.priority_because && (
          <p className="m-0 text-[13px] text-ink-3">
            With nothing measured, priority {tool.priority}: {tool.priority_because}
          </p>
        )}
      </div>
    </section>
  );
}

function Row({ row, self }: { row: NonNullable<ModulePage["rules"]>[number]["rows"][number]; self: boolean }) {
  const when = Object.entries(row.when).map(([k, v]) => `${k} ${v}`).join(", ") || "otherwise";
  return (
    <>
      <span className="font-data text-measured-ink">{when}</span>
      <span className={self ? "" : "text-ink-2"}>
        <span className={self ? "font-semibold font-data" : "font-data"}>{row.then}</span>
        {row.because && <> — {row.because}</>}
      </span>
    </>
  );
}

function Origin({ tool }: { tool: ModulePage }) {
  const up = tool.upstream;
  return (
    <div className="bg-surface border border-line rounded-panel px-5 py-[18px]">
      <h2 className="m-0 mb-3 text-[14px] font-semibold">Where it comes from</h2>
      <dl className="m-0 grid grid-cols-[92px_minmax(0,1fr)] gap-x-[10px] gap-y-[10px] text-[13px]">
        <dt className="text-ink-3">Contract</dt>
        <dd className="m-0 font-data text-[12.5px] break-all">{tool.id}</dd>
        {up && (<>
          <dt className="text-ink-3">Upstream</dt>
          <dd className="m-0">
            <a className="font-data text-[12.5px]" target="_blank" rel="noreferrer"
               href={`${up.repo.replace(/\.git$/, "")}/tree/${up.sha}/${up.path}`}>
              nf-core/modules @ {up.sha.slice(0, 7)}
            </a>
          </dd>
        </>)}
        {tool.container && (<>
          <dt className="text-ink-3">Container</dt>
          <dd className="m-0 font-data text-[12px] text-ink-2 break-all">{tool.container}</dd>
        </>)}
        <dt className="text-ink-3">Approved</dt>
        <dd className="m-0">{tool.approved_by} · {tool.approved_at}</dd>
        <dt className="text-ink-3">Registry</dt>
        <dd className="m-0 font-data text-[12.5px] break-all">{tool.registry_at}</dd>
        {tool.licence && (<>
          <dt className="text-ink-3">Licence</dt>
          <dd className="m-0">{tool.licence}</dd>
        </>)}
      </dl>
    </div>
  );
}

function NfCore({ tool }: { tool: ModulePage }) {
  const entry = tool.catalogue;
  return (
    <section aria-labelledby="tool-nfcore" className="bg-surface border border-line rounded-panel px-5 py-[18px]">
      <h2 id="tool-nfcore" className="m-0 mb-3 text-[14px] font-semibold">From nf-core</h2>
      {!entry && <p className="m-0 text-[13px] text-ink-3">Not synced yet: the catalogue has not read this module.</p>}
      {entry && (
        <dl className="m-0 grid grid-cols-[92px_minmax(0,1fr)] gap-x-[10px] gap-y-[10px] text-[13px]">
          {entry.module.description && (<>
            <dt className="text-ink-3">Says</dt><dd className="m-0">{entry.module.description}</dd>
          </>)}
          <dt className="text-ink-3">Version</dt>
          <dd className="m-0 font-data">
            {entry.row.tool_version ?? "unknown"}
            {entry.row.state === "update_available" && <span className="text-ink-3"> (registry has {entry.row.registry_version})</span>}
          </dd>
          <dt className="text-ink-3">Formats</dt>
          <dd className="m-0 font-data">{entry.row.formats_in.join(", ") || "—"} → {entry.row.formats_out.join(", ") || "—"}</dd>
          {(entry.module.authors ?? []).length > 0 && (<>
            <dt className="text-ink-3">Authors</dt><dd className="m-0">{(entry.module.authors ?? []).join(", ")}</dd>
          </>)}
        </dl>
      )}
    </section>
  );
}
