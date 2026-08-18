import type { components } from "../api/schema";
import { useUrlState } from "../app/useUrlState";

type Excerpt = components["schemas"]["Excerpt"];

/** Collapsed to one line, opened by click or `E`.
 *
 * **This is the change that removes the overwhelm** (design §5): on a confirmable question you
 * never open it, and the screen is a question, three options and a button. Open state is in
 * the URL because a curator sending a link to a confusing question is sending it *because* of
 * the evidence.
 */
export function Evidence({ excerpts }: { excerpts: Excerpt[] }) {
  const [open, setOpen] = useUrlState("evidence", "");
  const shown = open === "open";
  const n = excerpts.length;
  if (n === 0) return null;

  return (
    <div className="mt-6">
      <button
        onClick={() => setOpen(shown ? "" : "open")}
        className="text-secondary text-ink-2 bg-transparent border-0 p-0 cursor-pointer"
      >
        Evidence — {n} {n === 1 ? "line" : "lines"} from the module{" "}
        <span className="font-data text-ink-3">E</span>
      </button>
      {shown && (
        <div className="mt-3 border-l-2 border-line-2 pl-4">
          {excerpts.map((e) => (
            <div key={e.locator} className="py-1">
              <div className="text-label text-ink-3 font-data">{e.locator}</div>
              <div className="text-body text-ink">{e.text}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
