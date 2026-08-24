import type { components } from "../api/schema";

type Finding = components["schemas"]["Finding"];
type Level = Finding["level"];

/** What each level is called and what it costs you.
 *
 * **Three levels, because `InputPort` has three kinds of requirement.** `state_required` is a
 * refusal; `state_required_conventional` and `state_preferred` are not. A boolean verdict would
 * collapse the last two into silence, and the difference between "illegal" and "not what we
 * would have done" is the difference between a compiler and a colleague.
 */
const WORDS: Record<Level, { label: string; what: string; colour: string }> = {
  illegal: {
    label: "Illegal",
    what: "cannot be emitted",
    colour: "var(--undecided)",
  },
  unmet: {
    label: "Unmet",
    what: "nothing feeds this yet — legal to hold, not to run",
    colour: "var(--measured)",
  },
  advisory: {
    label: "Advisory",
    what: "legal, and not what convention would choose",
    colour: "var(--measured)",
  },
};

const ORDER: Level[] = ["illegal", "unmet", "advisory"];

/** What is wrong with the graph you drew, worst first.
 *
 * **Every finding carries its code**, so `mendel explain MD0504` expands it exactly as it would
 * from the CLI. A message without its code is a sentence a runbook cannot cite.
 */
export function Findings({
  findings,
  onSelect,
}: {
  findings: Finding[];
  onSelect: (nodeId: string) => void;
}) {
  if (findings.length === 0) {
    return (
      <p data-testid="findings-clear" className="p-4 text-secondary text-ink-3">
        Nothing wrong with this graph.
      </p>
    );
  }

  const sorted = [...findings].sort(
    (a, b) => ORDER.indexOf(a.level) - ORDER.indexOf(b.level),
  );

  return (
    <ul data-testid="findings" className="flex flex-col gap-1 p-3 list-none m-0">
      {sorted.map((finding, i) => {
        const words = WORDS[finding.level];
        // A finding names either a node or the two ends of a wire. Clicking it should select
        // the thing it is about — a finding you cannot navigate to is a log line.
        const anchor = finding.node ?? finding.target?.split(".")[0] ?? null;
        return (
          <li key={`${finding.code}-${i}`} data-testid="finding" data-level={finding.level}>
            <button
              onClick={() => anchor && onSelect(anchor)}
              disabled={anchor === null}
              className="w-full text-left rounded-r border border-line bg-surface p-2
                         hover:bg-[var(--hover)] disabled:cursor-default"
            >
              <span className="flex items-baseline gap-2">
                <span
                  className="text-label uppercase tracking-[.1em] font-semibold"
                  style={{ color: words.colour }}
                >
                  {words.label}
                </span>
                <code className="font-data text-label text-ink-3">{finding.code}</code>
              </span>
              <span className="block mt-1 text-secondary text-ink">
                {/* The message already carries its code on the front, from `coded()`. Stripping
                    it here would mean two spellings of one string. */}
                {finding.message.replace(/^MD\d{4}: /, "")}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
