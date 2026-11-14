import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { RegistryTabs } from "./RegistryTabs";
import { useLearnedRules, useRuleVerb, type InUseView, type ProposalView, type ProposalsView } from "./useLearnedRules";

const panel = "bg-surface border border-line rounded-panel";
const heading = "m-0 px-5 py-4 border-b border-line text-[15px] font-semibold";
const NO_MODEL = "No model is set (Settings → Models → Adapting tools)";

type Row = { when?: Record<string, unknown>; then?: unknown; because?: unknown; cite?: unknown };

function fact(name: string) {
  return name.replace(/_/g, " ");
}

function value(v: unknown): string {
  if (v === true) return "yes";
  if (v === false) return "no";
  return String(v);
}

/** A test as words: `">= 100"` is "≥ 100", `"absent"` is "is not known". */
function test(name: string, expected: unknown): string {
  if (expected === "absent") return `${fact(name)} is not known`;
  if (expected === "present") return `${fact(name)} is known`;
  if (typeof expected === "string") {
    const [symbol, literal] = expected.split(" ");
    const signs: Record<string, string> = { ">=": "≥", "<=": "≤", ">": ">", "<": "<", "==": "=", "!=": "≠" };
    if (symbol in signs && literal !== undefined) return `${fact(name)} ${signs[symbol]} ${literal}`;
  }
  if (expected && typeof expected === "object") {
    const shaped = expected as { in?: unknown[]; not?: unknown };
    if (shaped.in) return `${fact(name)} is one of ${shaped.in.map(value).join(", ")}`;
    if ("not" in shaped) return `${fact(name)} is not ${value(shaped.not)}`;
  }
  return `${fact(name)} is ${value(expected)}`;
}

export function rowWords(row: Row): string {
  const tests = Object.entries(row.when ?? {}).map(([k, v]) => test(k, v));
  return `${tests.length ? `When ${tests.join(" and ")}` : "Always"} → ${value(row.then)}`;
}

/** `/registry/learned`: rules a model proposed from people's answers, checked by the engine. */
export function LearnedRules() {
  useTitle("Learned rules");
  const page = useLearnedRules();
  if (page.isPending) return <><RegistryTabs /><Loading what="the learned rules" /></>;
  if (page.isError || !page.data) return <><RegistryTabs /><Failed error={page.error} /></>;
  const view = page.data;
  return (
    <div className="min-h-full bg-paper">
      <RegistryTabs />
      <div className="frame gutter py-[18px] flex flex-wrap gap-5 items-start">
        <div className="flex-[999_1_520px] min-w-0 flex flex-col gap-5">
          <Header view={view} />
          {view.proposals.length === 0
            ? <p className={`m-0 px-5 py-4 text-ink-2 ${panel}`}>No proposals yet. When people answer the same question in three kept pipelines, choose Propose.</p>
            : view.proposals.map((p) => <Proposal key={p.id} proposal={p} />)}
          {view.refused.length > 0 && (
            <section aria-labelledby="not-proposed" className={panel}>
              <h2 id="not-proposed" className={heading}>Not proposed</h2>
              <ul className="m-0 p-0 list-none">
                {view.refused.map((r) => (
                  <li key={r.id} className="px-5 py-3 border-t border-line-soft first:border-t-0 text-[13px] flex flex-col gap-1">
                    <span className="font-semibold">{r.target}</span>
                    {r.status === "no_rule"
                      ? <span className="text-ink-2">The model found no rule: {r.why}</span>
                      : r.problems.map((p) => <span key={p} className="text-needs-you-ink break-words">{p}</span>)}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
        <InUse rules={view.in_use} />
      </div>
    </div>
  );
}

function Header({ view }: { view: ProposalsView }) {
  const verb = useRuleVerb();
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="m-0 text-[22px] font-semibold">Learned rules</h1>
        <button type="button" className="control-primary ml-auto"
                disabled={!view.model || view.running || verb.isPending}
                onClick={() => verb.mutate("/rules/proposals/run")}>
          Propose
        </button>
      </div>
      <p className="m-0 text-[13.5px] text-ink-2">
        When people keep answering a question the same way, a model proposes the rule and the engine checks it against every answer. Nothing is used until you approve it.
      </p>
      {!view.model && <p className="m-0 text-[13px] text-needs-you-ink">{NO_MODEL}</p>}
      {view.running && <p className="m-0 text-[13px] text-ink-2">asking…</p>}
      {verb.isError && <Failed error={verb.error} padded={false} />}
    </div>
  );
}

function Proposal({ proposal }: { proposal: ProposalView }) {
  const verb = useRuleVerb();
  const changed = proposal.replay.filter((r) => !r.agrees);
  const same = proposal.replay.length - changed.length;
  const blocked = proposal.check.length > 0 || proposal.stale;
  return (
    <section aria-label={proposal.target} className={panel}>
      <h2 className={heading}>{proposal.target}</h2>
      <div className="px-5 py-4 flex flex-col gap-3 text-[13px]">
        <ul className="m-0 p-0 list-none flex flex-col gap-2">
          {(proposal.rows as Row[]).map((row, n) => (
            <li key={n} className="flex flex-col gap-1">
              <span className="font-data break-words">{rowWords(row)}</span>
              <span className="text-ink-2"><span className="text-[12px] text-ink-3">the model's reason: </span><span>{String(row.because ?? "")}</span></span>
            </li>
          ))}
        </ul>
        <p className="m-0 text-ink-2"><span className="text-[12px] text-ink-3">the model's reason for the whole: </span>{proposal.why}</p>
        <div>
          <h3 className="m-0 text-[12.5px] font-semibold text-ink-2">Learned from</h3>
          <ul className="m-0 p-0 list-none">
            {proposal.evidence.map((e) => (
              <li key={`${e.pipeline}-${e.decision}`} className="break-words">
                <span className="font-data">{e.pipeline}</span>: a person chose <span className="font-data">{value(e.answer)}</span>
                {e.reason && <span className="text-ink-2"> ({e.reason})</span>}
              </li>
            ))}
          </ul>
        </div>
        {proposal.check.length === 0
          ? <p className="m-0 text-done-ink">Checks pass</p>
          : proposal.check.map((c) => <p key={c} className="m-0 text-needs-you-ink break-words whitespace-pre-wrap">{c}</p>)}
        {proposal.stale && <p className="m-0 text-needs-you-ink">People have answered since this was proposed. Choose Propose to ask again.</p>}
        <div>
          {changed.length > 0 && (
            <>
              <p className="m-0 text-needs-you-ink">It would change {changed.length} past decision{changed.length === 1 ? "" : "s"}:</p>
              <ul className="m-0 p-0 list-none">
                {changed.map((r) => (
                  <li key={`${r.pipeline}-${r.decision}`} className="break-words">
                    <span className="font-data">{r.pipeline}</span>: {r.by_person ? "a person" : "the build"} chose <span className="font-data">{value(r.recorded)}</span>; the rule would choose <span className="font-data">{value(r.would)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <p className="m-0 text-ink-2">It would settle {same} past decision{same === 1 ? "" : "s"} the same way.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="control-primary" disabled={blocked || verb.isPending}
                  onClick={() => verb.mutate(`/rules/proposals/${proposal.id}/approve`)}>
            Approve
          </button>
          <button type="button" className="control" disabled={verb.isPending}
                  onClick={() => verb.mutate(`/rules/proposals/${proposal.id}/reject`)}>
            Reject
          </button>
        </div>
        {verb.isError && <Failed error={verb.error} padded={false} />}
      </div>
    </section>
  );
}

function InUse({ rules }: { rules: InUseView[] }) {
  const verb = useRuleVerb();
  return (
    <aside aria-label="In use" className={`flex-[1_1_280px] max-w-[400px] ${panel}`}>
      <h2 className={heading}>In use</h2>
      {rules.length === 0
        ? <p className="m-0 px-5 py-4 text-ink-2">No learned rule is in use.</p>
        : (
          <ul className="m-0 p-0 list-none">
            {rules.map((r) => (
              <li key={r.slug} className="px-5 py-3 border-t border-line-soft first:border-t-0 text-[13px] flex flex-col gap-1">
                <span className="font-semibold">{r.target}</span>
                {(r.rows as Row[]).map((row, n) => <span key={n} className="font-data break-words">{rowWords(row)}</span>)}
                {r.approved_by && <span className="text-ink-3">approved by {r.approved_by}</span>}
                <button type="button" className="control self-start" disabled={verb.isPending}
                        onClick={() => verb.mutate(`/rules/learned/${r.slug}/withdraw`)}>
                  Withdraw
                </button>
              </li>
            ))}
          </ul>
        )}
      {verb.isError && <Failed error={verb.error} padded={false} />}
    </aside>
  );
}
