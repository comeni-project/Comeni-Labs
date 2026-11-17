import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";

import type { components } from "../api/schema";
import { Failed } from "../ui/States";
import { toneOf } from "./families";
import { useStartForge } from "../forge/useForgeActions";
import { labelOf, pillOf } from "./states";
import type { ModuleRow } from "./useCatalogue";
import { useFilters, useModuleDetail } from "./useCatalogue";

type ModulePage = components["schemas"]["ModulePage"];

/** A read that keeps the API's coded refusal as the error. */
async function read<T>(path: string): Promise<T> {
  const r = await fetch(`/api${path}`);
  const body = await r.json().catch(() => null);
  if (!r.ok) throw new Error(body?.detail ?? `${path} → ${r.status}`);
  return body as T;
}

const label = "text-[11.5px] font-semibold text-ink-3";
const named = (topic: string) => topic.charAt(0).toUpperCase() + topic.slice(1);
const shortOf = (id: string) => id.replace(/^nf-core\//, "").replace(/@/, " ");

function Chip({ format, mention }: { format: string; mention?: boolean }) {
  const tone = toneOf(format);
  return mention
    ? <span className="pill pill-mention" title="Mentioned in its description, not declared">{format}</span>
    : <span className="pill" style={{ background: tone.soft, color: tone.ink }}>{format}</span>;
}

/** **The selected tool** (board "7 · Registry", #511): its name and state, what it does and its
 *  one action; a takes → tool → makes diagram; where it stands (in your registry, upstream, topic);
 *  how it fits the tools you hold; and the rules by which the builder decides about it. */
export function Selected({ row }: { row: ModuleRow | undefined }) {
  const start = useStartForge();
  const navigate = useNavigate();
  const filters = useFilters();
  const fits = useModuleDetail(row).data?.fits;
  const held = !!row?.contract_id;
  const page = useQuery({
    queryKey: ["tool", row?.contract_id],
    queryFn: () => read<ModulePage>(`/registry/tools/${row!.contract_id}`),
    enabled: held,
    retry: false,
  });
  if (!row) {
    return (
      <section aria-label="Selected module" className="bg-surface border border-line rounded-panel p-[22px] text-ink-3">
        Pick a tool to see what it takes and makes.
      </section>
    );
  }
  const forge = () => start.mutate({ source: row.source, path: row.path },
                                   { onSuccess: (view) => navigate(`/forge/${view.id}`) });
  const primary = "inline-flex items-center h-[36px] px-4 rounded-control border-0 bg-action text-on-action shadow-raise text-[13px] font-semibold no-underline cursor-pointer";
  const action = row.preview
    ? <span className="text-[12.5px] text-ink-3">Forging from {row.source} is not built yet.</span>
    : row.state === "update_available"
    ? <button type="button" className={primary} disabled={start.isPending} onClick={forge}>Update to {row.tool_version}</button>
    : row.state === "not_imported"
      ? <button type="button" className={primary} disabled={start.isPending} onClick={forge}>Forge this</button>
      : row.state === "merged_not_released" || row.state === "in_review"
        ? <Link to="/forge" className={primary}>Open forging</Link>
        : <Link to="/" className={primary}>Use in a build</Link>;
  const takes = [...row.formats_in.map((f) => ({ f, m: false })), ...row.mentions_in.map((f) => ({ f, m: true }))];
  const makes = [...row.formats_out.map((f) => ({ f, m: false })), ...row.mentions_out.map((f) => ({ f, m: true }))];
  const undeclared = [...row.mentions_out.map((f) => `a ${f} output`), ...row.mentions_in.map((f) => `a ${f} input`)];
  const rules = page.data?.rules ?? [];

  return (
    <section aria-label="Selected module" className="bg-surface border border-line rounded-panel p-5 flex flex-col gap-4 min-w-0">
      <header className="flex flex-wrap items-start gap-3">
        <div className="flex flex-col gap-1 min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-[10px]">
            {held
              ? <Link to={`/registry/tools/${row.contract_id}`} className="font-data text-[20px] font-semibold text-ink no-underline hover:underline break-all">{row.path}</Link>
              : <span className="font-data text-[20px] font-semibold text-ink break-all">{row.path}</span>}
            <span className={`px-[9px] py-[2px] rounded-full text-[12px] font-semibold ${pillOf(row.state)}`}>{labelOf(row.state)}</span>
            {row.preview && <span className="px-[9px] py-[2px] rounded-full border border-line bg-surface-2 text-[12px] text-ink-2">{row.source} · preview</span>}
          </span>
          {row.description && <span className="text-[13.5px] text-ink-2">{row.description}</span>}
          {row.preview && <span className="text-[12.5px] text-ink-3">A sample of the {row.source} catalogue, shown for how it would look. It is not synced from {row.source}.</span>}
        </div>
        <span className="flex flex-wrap items-center gap-2">
          <a className="inline-flex items-center h-[36px] px-[14px] rounded-control border border-line-2 bg-surface text-[13px] text-ink no-underline"
             href={row.source === "pegi3s" ? `https://hub.docker.com/r/pegi3s/${row.path}` : `https://github.com/nf-core/modules/tree/master/modules/nf-core/${row.path}`}
             target="_blank" rel="noreferrer">{row.source === "pegi3s" ? "Docker Hub page" : "nf-core page"}</a>
          {action}
        </span>
      </header>
      {start.isError && <Failed error={start.error} padded={false} />}

      <div aria-label="Takes and makes" className="flex items-center justify-center px-4 py-6 rounded-panel bg-surface-2 border border-line-soft">
        <div className="flex flex-col items-end gap-[6px] min-w-0">
          <span className={label}>Takes</span>
          {takes.length ? takes.map(({ f, m }) => <Chip key={f} format={f} mention={m} />) : <span className="text-[11.5px] text-ink-3">not stated</span>}
        </div>
        <span aria-hidden="true" className="w-[32px] h-px bg-line-2 shrink-0" />
        <div className="flex flex-col items-center gap-[2px] min-w-[150px] px-5 py-4 rounded-panel border border-line-2 bg-surface text-center">
          <span className="text-[15px] font-semibold text-ink">{row.path.replace("/", " ")}</span>
          <span className="font-data text-[11.5px] text-ink-3">{row.registry_version ? `here ${row.registry_version}` : `upstream ${row.tool_version ?? "unknown"}`}</span>
        </div>
        <span aria-hidden="true" className="w-[32px] h-px bg-line-2 shrink-0" />
        <div className="flex flex-col items-start gap-[6px] min-w-0">
          <span className={label}>Makes</span>
          {makes.length ? makes.map(({ f, m }) => <Chip key={f} format={f} mention={m} />) : <span className="text-[11.5px] text-ink-3">not stated</span>}
        </div>
      </div>

      <dl className="m-0 grid grid-cols-3 gap-2">
        {([["In your registry", row.registry_version ?? "—", true], ["Upstream", row.tool_version ?? "unknown", true],
           ["Topic", row.topics?.length ? named(row.topics[0]) : "—", false]] as const).map(([k, v, mono]) => (
          <div key={k} className="flex flex-col gap-[3px] px-3 py-[10px] rounded-control border border-line">
            <dt className={label}>{k}</dt>
            <dd className={`m-0 text-[13.5px] font-semibold text-ink ${mono ? "font-data" : ""}`}>{v}</dd>
          </div>
        ))}
      </dl>

      {fits && (
        <div className="flex flex-col gap-2">
          <span className="flex items-baseline gap-2"><span className={label}>Fits with your registry</span>
            <span className="text-[12px] text-ink-3">by file format</span></span>
          {fits.takes_from.length + fits.feeds.length === 0 ? (
            <p className="m-0 text-[12.5px] text-ink-3">No tool in your registry shares a format with this one yet.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {([["Can take from", fits.takes_from], ["Can feed", fits.feeds]] as const).map(([title, list]) => (
                <div key={title} className="flex flex-col gap-[6px]">
                  <span className="text-[12px] font-semibold text-ink-2">{title}</span>
                  {list.length === 0 && <span className="text-[12.5px] text-ink-3">none yet</span>}
                  {list.slice(0, 6).map((fit) => (
                    <button key={fit.path} type="button" onClick={() => filters.set("module", [fit.path])}
                            className="flex items-center gap-2 h-[32px] px-3 rounded-control border border-line bg-surface text-left cursor-pointer hover:bg-hover">
                      <span aria-hidden="true" className="w-[6px] h-[6px] rounded-full bg-done shrink-0" />
                      <span className="truncate font-data text-[12.5px] text-ink">{fit.path}</span>
                      <span className="ml-auto font-data text-[11.5px] text-ink-3">{fit.via}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <span className="flex items-baseline gap-2"><span className={label}>Rules</span>
          <span className="text-[12px] text-ink-3">how the builder decides about this tool</span></span>
        {!held && <p className="m-0 px-3 py-[10px] rounded-control border border-line text-[12.5px] text-ink-2">Forging drafts its rules.</p>}
        {held && page.isError && <p className="m-0 text-[12.5px] text-needs-you-ink">The tool's rules could not be read.</p>}
        {held && page.data && rules.length === 0 && (
          <p className="m-0 px-3 py-[10px] rounded-control border border-line text-[12.5px] text-ink-2">
            No rule needed: nothing else in your registry does this job, so the builder always uses it.
          </p>
        )}
        {rules.map((rule, n) => (
          <div key={`${rule.role}-${n}`} className="rounded-control border border-line overflow-hidden">
            <div className="flex flex-wrap items-baseline gap-2 px-3 py-[10px]">
              <span className="text-[13.5px] font-semibold">Which {rule.role.replace(/_/g, " ")}</span>
              {rule.because && <span className="text-[12px] text-ink-3">{rule.because}</span>}
            </div>
            <table className="w-full border-collapse text-[12.5px]">
              <thead>
                <tr className="bg-surface-2 text-left text-[11.5px] text-ink-3">
                  <th className="px-3 py-[6px] font-semibold w-[28%]">When</th>
                  <th className="px-3 py-[6px] font-semibold w-[24%]">Choose</th>
                  <th className="px-3 py-[6px] font-semibold">Because</th>
                </tr>
              </thead>
              <tbody>
                {rule.rows.map((r, m) => {
                  const me = r.then === row.contract_id;
                  const when = Object.entries(r.when).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(", ") || "otherwise";
                  return (
                    <tr key={m} className={`border-t border-line-soft ${me ? "bg-now-soft" : "text-ink-3"}`}>
                      <td className="px-3 py-2 font-data align-top">{when}</td>
                      <td className="px-3 py-2 align-top">
                        <span className={me ? "font-semibold text-ink" : ""}>{shortOf(r.then)}</span>
                        {me && <span className="ml-2 px-[6px] py-[1px] rounded-xs bg-now text-on-action text-[10.5px] font-semibold whitespace-nowrap">this tool</span>}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <span className={me ? "text-ink-2" : ""}>{r.because}</span>
                        {rule.cite && <span className="block mt-[2px] italic text-[11.5px] text-ink-3">{rule.cite}</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {undeclared.length > 0 && (
        <p className="m-0 px-3 py-[10px] rounded-control bg-measured-soft text-[12.5px] text-measured-ink">
          nf-core describes {undeclared.join(" and ")} too, but does not declare {undeclared.length > 1 ? "their formats" : "its format"}.
        </p>
      )}
      {row.problems.length > 0 && (
        <ul className="m-0 pl-4 text-[12.5px] text-ink-3">
          {row.problems.map((p) => <li key={p.code}><span className="font-data">{p.code}</span> {p.says}</li>)}
        </ul>
      )}
    </section>
  );
}
