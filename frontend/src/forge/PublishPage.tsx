import type { ReactNode } from "react";
import { Link } from "react-router";

import { Failed } from "../ui/States";
import { live, valueOf, waiting } from "./items";
import type { AdaptationView } from "./useAdaptation";
import { useForgeActions } from "./useForgeActions";

const ASSEMBLED = new Set(["assembled", "testing", "tested", "publishing", "in_review", "merged"]);
const TESTED = new Set(["tested", "publishing", "in_review", "merged"]);

type StepState = "done" | "now" | "failed" | "later";
interface Step { title: string; detail: string; state: StepState; action?: ReactNode; blocker?: string }

const loud = "inline-flex items-center h-[30px] px-3 rounded-control border-0 bg-action text-on-action shadow-raise text-[12.5px] font-semibold no-underline cursor-pointer disabled:opacity-50";
const quiet = "inline-flex items-center h-[30px] px-3 rounded-control border border-line-2 bg-surface text-[12.5px] text-ink no-underline cursor-pointer";

/** What the pull request carries, from which pieces have items: the registry's own layout. */
export function filesOf(view: AdaptationView): { tag: "NEW" | "CHANGED"; path: string }[] {
  const items = live(view.items);
  const tool = `tools/${view.source}/${view.path}`;
  const out: { tag: "NEW" | "CHANGED"; path: string }[] = [
    { tag: view.reforge ? "CHANGED" : "NEW", path: `${tool}/contract.yml` },
    { tag: view.reforge ? "CHANGED" : "NEW", path: `${tool}/module/ (vendored)` },
  ];
  const tests = items.filter((i) => i.key.startsWith("tests:test:")).length;
  if (tests) out.push({ tag: "NEW", path: `${tool}/tests/ · ${tests} case${tests === 1 ? "" : "s"}` });
  for (const i of items) {
    const v = valueOf(i);
    if (i.key.startsWith("vocabulary:type:")) {
      const id = i.key.slice("vocabulary:type:".length);
      const states = Array.isArray(v.add_states) ? (v.add_states as string[]) : [];
      out.push(states.length ? { tag: "CHANGED", path: `vocabulary/types/${id}.yml · + ${states.join(", ")}` }
        : { tag: "NEW", path: `vocabulary/types/${id}.yml` });
    }
    if (i.key.startsWith("vocabulary:family:")) out.push({ tag: "NEW", path: `vocabulary/families/${i.key.slice("vocabulary:family:".length)}.yml` });
    if (i.key.startsWith("measurers:") && i.key !== "measurers:none") out.push({ tag: "NEW", path: `measurers/measures/${i.key.slice("measurers:".length)}/` });
  }
  const rules = items.filter((i) => i.key.startsWith("rules:") && i.key !== "rules:none").length;
  if (rules) out.push({ tag: "CHANGED", path: `rules/ · ${rules} rule${rules === 1 ? "" : "s"}` });
  out.push({ tag: "NEW", path: `changelog.d/${view.path.replace(/\//g, "-")}.md` });
  return out;
}

/** `/forge/:id/publish` · **Publish** (board "6 · Forging", Publish): drafted → tests passed →
 *  pull request → merged → released, the action for the step that is next, every blocker with
 *  what fixes it; beside it, what the pull request carries. */
export function PublishPage({ view }: { view: AdaptationView }) {
  const actions = useForgeActions(view.id);
  const items = live(view.items);
  const toReview = items.filter(waiting).length;
  const assembled = ASSEMBLED.has(view.phase);
  const tested = TESTED.has(view.phase);
  const failed = view.tests.filter((t) => t.state === "failed").length;
  const pull = view.pull_request && view.pull_request.state !== "closed" ? view.pull_request : null;
  const merged = view.phase === "merged";
  const base = `/forge/${encodeURIComponent(view.id)}`;
  const states = items.filter((i) => i.key.startsWith("vocabulary:type:") && Array.isArray(valueOf(i).add_states)).length;
  const types = items.filter((i) => i.key.startsWith("vocabulary:type:")).length - states;

  const steps: Step[] = [
    {
      title: assembled ? "Drafted" : "Draft",
      detail: ["tool", types ? `${types} new data type${types === 1 ? "" : "s"}` : "", states ? `${states} new state${states === 1 ? "" : "s"}` : ""].filter(Boolean).join(", "),
      state: assembled ? "done" : "now",
      action: assembled ? undefined : view.ready
        ? <button type="button" className={loud} disabled={actions.assemble.isPending} onClick={() => actions.assemble.mutate()}>Assemble</button>
        : <Link to={base} className={quiet}>{toReview ? `${toReview} to review` : "Open the tool"}</Link>,
    },
    {
      title: tested ? "Tests passed" : failed ? "Tests failed" : "Tests",
      detail: view.tests.length ? `${view.tests.filter((t) => t.state === "passed").length} of ${view.tests.length}` : "run in Wiener",
      state: failed ? "failed" : tested ? "done" : assembled ? "now" : "later",
      blocker: view.tests_unavailable ?? undefined,
      action: assembled && !tested ? <Link to={`${base}/tests`} className={failed ? quiet : loud}>{failed ? "See test" : "Run the tests"}</Link> : undefined,
    },
    {
      title: pull ? `Pull request #${pull.number} opened` : "Pull request",
      detail: pull ? "on comeni-registry, with the AI’s summary and your approvals" : "on comeni-registry",
      state: pull ? "done" : view.phase === "publishing" ? "now" : tested ? "now" : "later",
      blocker: tested && !pull ? view.publish_unavailable ?? undefined : undefined,
      action: view.phase === "tested" && !view.publish_unavailable
        ? <button type="button" className={loud} disabled={actions.publish.isPending} onClick={() => actions.publish.mutate()}>Open pull request</button>
        : view.phase === "publishing" ? <span className="text-[12.5px] text-now-ink">Running the registry’s checks…</span> : undefined,
    },
    {
      title: "Merged",
      detail: merged ? "in comeni-registry, not yet in a release" : pull ? (pull.checks === "green" ? "registry CI is green" : pull.checks === "red" ? "registry CI failed" : "waiting for registry CI") : "after review",
      state: merged ? "done" : pull?.checks === "red" ? "failed" : pull ? "now" : "later",
      blocker: pull && !merged && pull.says ? pull.says : undefined,
      action: view.phase === "in_review" && pull
        ? <button type="button" className={loud} disabled={pull.checks !== "green" || pull.merging || actions.approve.isPending}
                  onClick={() => actions.approve.mutate()}>{pull.merging ? "Merging…" : "Approve and merge"}</button>
        : undefined,
    },
    {
      title: "Released",
      detail: "reaches the builder with the next release",
      state: merged ? "now" : "later",
      action: merged ? <Link to="/registry/releases" className={quiet}>Cut a release</Link> : undefined,
    },
  ];

  return (
    <div className="grid gap-[14px] items-start lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
      <section aria-label="Track" className="bg-surface border border-line rounded-panel overflow-hidden">
        {steps.map((s, n) => (
          <div key={s.title} className="flex gap-3 px-4 py-[14px] border-t border-line-soft first:border-t-0">
            <span className={`w-[22px] h-[22px] shrink-0 rounded-full grid place-items-center text-[11px] font-bold
                              ${s.state === "done" ? "bg-done-soft text-done-ink" : s.state === "failed" ? "bg-needs-you-soft text-needs-you-ink"
                                : s.state === "now" ? "bg-now-soft text-now-ink" : "bg-surface-2 text-ink-3"}`}>
              {s.state === "done" ? "✓" : s.state === "failed" ? "✕" : n + 1}
            </span>
            <span className="flex flex-col gap-1 min-w-0 flex-1">
              <span className="text-[13.5px] font-semibold text-ink">{s.title}</span>
              <span className="text-[12px] text-ink-3">{s.detail}</span>
              {s.blocker && (
                <span className="mt-1 px-3 py-2 rounded-control border border-line bg-surface-2 text-[12.5px]">
                  <b className="font-semibold">Blocker</b> · {s.blocker}
                </span>
              )}
            </span>
            <span className="flex flex-col items-end gap-2 shrink-0">
              {s.state === "now" && s.title === "Released" && <span className="font-data text-[11.5px] text-ink-3">waiting</span>}
              {s.action}
            </span>
          </div>
        ))}
        {[actions.assemble, actions.publish, actions.approve].map((m, n) =>
          m.isError ? <div key={n} className="px-4 pb-3"><Failed error={m.error} padded={false} /></div> : null)}
      </section>
      <section aria-label="What the pull request carries" className="bg-surface border border-line rounded-panel p-4 flex flex-col gap-2">
        <span className="text-[11.5px] font-semibold text-ink-3">{pull ? `In pull request #${pull.number}` : "In the pull request"}</span>
        {filesOf(view).map((f) => (
          <span key={f.path} className="flex items-center gap-2 text-[12.5px]">
            <span className={`px-[6px] rounded-xs text-[10.5px] font-bold ${f.tag === "NEW" ? "bg-done-soft text-done-ink" : "bg-measured-soft text-measured-ink"}`}>{f.tag}</span>
            <span className="font-data text-ink-2 break-all">{f.path}</span>
          </span>
        ))}
        {pull && <a href={pull.url} className={`${quiet} self-start mt-2`}>Open on GitHub</a>}
      </section>
    </div>
  );
}
