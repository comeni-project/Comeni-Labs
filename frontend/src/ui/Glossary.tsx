import { TERMS } from "./glossary";

/** Every word at once, for the person who wants to read rather than hover.
 *
 * **Reached from `?` and from the shell, so it is never more than one keystroke away.** The
 * screens are dense and a person meeting them for the first time needs somewhere to stand;
 * `docs/reference/glossary.md` is the same content for somebody outside the app.
 */
export function Glossary({ onClose }: { onClose: () => void }) {
  return (
    <div
      role="dialog"
      aria-label="What the words mean"
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 px-6
                 bg-[color-mix(in_srgb,var(--ink)_35%,transparent)]"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[620px] max-h-[70vh] overflow-auto rounded-r border border-line
                   bg-surface shadow-e3"
      >
        <div className="flex items-baseline gap-4 px-5 py-3 border-b border-line bg-surface-2">
          <span className="text-label uppercase tracking-[.13em] font-semibold text-ink-3">
            What the words mean
          </span>
          <button
            onClick={onClose}
            className="ml-auto bg-transparent border-0 cursor-pointer text-secondary text-ink-3"
          >
            close <span className="font-data">esc</span>
          </button>
        </div>
        <dl className="m-0 px-5 py-2">
          {Object.entries(TERMS).map(([term, entry]) => (
            <div key={term} className="py-3 border-b border-line last:border-b-0">
              <dt className="font-data text-body text-ink">{term}</dt>
              <dd className="m-0 mt-1 text-body text-ink-2">{entry.what}</dd>
              {entry.more && (
                <dd className="m-0 mt-1 text-secondary text-ink-3">{entry.more}</dd>
              )}
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
