export type TrackedPiece = { name: string; state: "done" | "now" | "later"; note: string };

/** The six pieces as one line: what is done, where you are, how much is left. Every piece can
 *  be opened, so a later one can be read before its turn. */
export function Tracker({ pieces, current, onPick }: {
  pieces: TrackedPiece[];
  current: string;
  onPick: (piece: string) => void;
}) {
  const at = pieces.findIndex((p) => p.name === current);
  return (
    <nav aria-label="Pieces">
      <p className="tracker-now">{current.charAt(0).toUpperCase() + current.slice(1)}, {at + 1} of {pieces.length}</p>
      <ol className="tracker">
        {pieces.map((p, n) => (
          <li key={p.name} data-state={p.state}>
            <button type="button" onClick={() => onPick(p.name)}
                    aria-current={p.name === current ? "step" : undefined}>
              <span className="tracker-dot" aria-hidden="true">{p.state === "done" ? "✓" : n + 1}</span>
              <span className="tracker-label capitalize font-medium">{p.name}</span>
              <span className="tracker-label text-[12px] text-ink-3">{p.note}</span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
