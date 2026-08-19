import { TERMS } from "./glossary";

/** A word the interface uses, defined where a person is reading it.
 *
 * **Not a tooltip on everything.** Wrap a word the *first* time a screen says it and leave the
 * rest bare: a page where every noun is dotted is a page that has taught you nothing and made
 * itself harder to read. The dotted underline is the affordance and `title` is the whole
 * mechanism — no portal, no positioning, no library, and it works on a keyboard and a screen
 * reader without any of that.
 *
 * An unknown word renders as plain text rather than throwing. `Glossary.test.tsx` is what makes
 * that safe: a word with no entry fails the suite, so the fallback is for the moment between
 * writing a screen and writing its definition, never a permanent state.
 */
export function Term({ children, of }: { children: string; of?: string }) {
  // **`of` because the word on screen is rarely the dictionary form.** A figure says `drifted`
  // and a status says `unverifiable`; the entry is `drift`. Forcing the screen to say the
  // dictionary form would be a glossary dictating copy, which is the wrong way round.
  const entry = TERMS[(of ?? children).toLowerCase()];
  if (!entry) return <>{children}</>;
  return (
    <abbr
      title={entry.more ? `${entry.what}. ${entry.more}` : entry.what}
      className="no-underline border-b border-dotted border-ink-3 cursor-help"
    >
      {children}
    </abbr>
  );
}
