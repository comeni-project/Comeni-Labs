import { useEffect, useState } from "react";
import { Link } from "react-router";

import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { RegistryTabs } from "./RegistryTabs";
import { useCutRelease, useReleases, type ReleasesPage } from "./useReleases";

const panel = "bg-surface border border-line rounded-panel";

/** A cut release's state in words (#535: "v0.8.1 · done · unknown"). */
const CUT: Record<string, string> = { cutting: "being cut…", done: "released", failed: "could not be cut" };
const heading = "m-0 px-5 py-4 border-b border-line text-[15px] font-semibold";

/** `/registry/releases`: what is merged and unreleased, and cutting a release. */
export function Releases() {
  useTitle("Releases");
  const page = useReleases();
  if (page.isPending) return <><RegistryTabs /><Loading what="the releases" /></>;
  if (page.isError || !page.data) return <><RegistryTabs /><Failed error={page.error} /></>;
  const view = page.data;
  return (
    <div className="overflow-y-auto h-full">
      <RegistryTabs />
      <div className="page">
      <div className="grid gap-[14px] items-start lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 flex flex-col gap-[14px]">
          <h1 className="m-0 text-[22px] font-semibold">Releases</h1>
          <p className="m-0 text-[13.5px] text-ink-2">{view.in_use}</p>
          {view.problem && <p className="m-0 text-[13px] text-needs-you-ink">{view.problem}</p>}
          <Unreleased view={view} />
          <Cut view={view} />
        </div>
        <div className="flex flex-col gap-[14px] min-w-0">
        <aside aria-label="Releases" className={panel}>
          <h2 className={heading}>Published</h2>
          {view.published.length === 0
            ? <p className="m-0 px-5 py-4 text-ink-2">No release has been published yet.</p>
            : (
              <ul className="m-0 p-0 list-none">
                {view.published.map((r) => (
                  <li key={r.tag} className="px-5 py-3 border-t border-line-soft first:border-t-0 font-data text-[13px]">{r.tag}</li>
                ))}
              </ul>
            )}
          {view.recent.length > 0 && (
            <ul aria-label="Cut here" className="m-0 p-0 list-none border-t border-line">
              {view.recent.map((r) => (
                <li key={r.version} className="px-5 py-3 border-t border-line-soft first:border-t-0 text-[13px] flex flex-col gap-1">
                  <span><span className="font-data">{r.version}</span> · {CUT[r.state] ?? r.state}
                    {r.cut_by && r.cut_by !== "unknown" ? ` · by ${r.cut_by}` : ""}</span>
                  {r.says && <span className="text-needs-you-ink break-words">{r.says}</span>}
                </li>
              ))}
            </ul>
          )}
        </aside>
        <section aria-label="Learned rules" className={`${panel} px-5 py-4 flex flex-col gap-2`}>
          <h2 className="m-0 text-[15px] font-semibold">Learned rules</h2>
          <p className="m-0 text-[12.5px] text-ink-2">Rules proposed from answers people keep giving, waiting for your approval before a release carries them.</p>
          <Link to="/registry/learned" className="text-[12.5px] font-semibold text-now-ink no-underline">Review learned rules</Link>
        </section>
        </div>
      </div>
      </div>
    </div>
  );
}

function Unreleased({ view }: { view: ReleasesPage }) {
  const unreleased = view.unreleased;
  return (
    <section aria-labelledby="unreleased" className={panel}>
      <h2 id="unreleased" className={heading}>Merged, not released</h2>
      {view.merged.length === 0 && !unreleased?.fragments.length && (
        <p className="m-0 px-5 py-4 text-ink-2">
          {unreleased?.ahead ? `${unreleased.ahead} commit(s) on main since ${unreleased.last ?? "the start"}.` : "Nothing is waiting for a release."}
        </p>
      )}
      <ul className="m-0 p-0 list-none">
        {view.merged.map((m) => (
          <li key={m.number} className="px-5 py-3 border-t border-line-soft first:border-t-0 text-[13px]">
            <a href={m.url} className="font-data">{m.module}</a> {m.version}
          </li>
        ))}
        {unreleased?.fragments.map((f) => (
          <li key={f.path} className="px-5 py-3 border-t border-line-soft first:border-t-0 text-[13px] text-ink-2 break-words">{f.text}</li>
        ))}
      </ul>
    </section>
  );
}

function Cut({ view }: { view: ReleasesPage }) {
  const cut = useCutRelease();
  const [version, setVersion] = useState(view.suggested);
  const [notes, setNotes] = useState(view.notes);
  useEffect(() => { setVersion(view.suggested); setNotes(view.notes); }, [view.suggested, view.notes]);
  const unreleased = view.unreleased;
  const cutting = view.recent.some((r) => r.state === "cutting");
  const green = unreleased?.checks === "green";
  const why = !unreleased ? null
    : unreleased.ahead === 0 ? "Nothing to release: main has not moved."
      : !green ? `CI on main is not green${unreleased.says ? `: ${unreleased.says}` : ""}.` : null;
  return (
    <section aria-labelledby="cut" className={panel}>
      <h2 id="cut" className={heading}>Cut a release</h2>
      {view.unavailable ? <p className="m-0 px-5 py-4 text-[13px] text-needs-you-ink">{view.unavailable}</p> : (
        <form className="px-5 py-4 flex flex-col gap-2" onSubmit={(e) => {
          e.preventDefault();
          cut.mutate({ version, notes });
        }}>
          <label htmlFor="release-version" className="text-[12.5px] text-ink-2">Version</label>
          <input id="release-version" value={version} onChange={(e) => setVersion(e.target.value)}
                 required className="font-data text-[13px] p-2 border border-line-2 rounded-control" />
          <label htmlFor="release-notes" className="text-[12.5px] text-ink-2">Notes</label>
          <textarea id="release-notes" rows={6} value={notes} onChange={(e) => setNotes(e.target.value)}
                    className="text-[13px] p-2 border border-line-2 rounded-control" />
          {why && <p className="m-0 text-[13px] text-needs-you-ink">{why}</p>}
          {unreleased?.commit && !why && (
            <p className="m-0 text-[13px] text-ink-2">
              Tags <span className="font-data">{version}</span> at commit <span className="font-data">{unreleased.commit.slice(0, 12)}</span> and publishes it. Installations following latest move to it, and a release cannot be taken back here.
            </p>
          )}
          <button type="submit" disabled={!!why || !unreleased || cutting || cut.isPending || !version.trim()}
                  className="control-primary self-start">
            {cutting || cut.isPending ? "Being cut…" : "Cut release"}
          </button>
          {cut.isError && <Failed error={cut.error} padded={false} />}
        </form>
      )}
    </section>
  );
}
