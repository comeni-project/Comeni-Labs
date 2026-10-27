/** **What was asked for and is not offered here** (Part I.2): the person's words, said where the
 *  goal is checked, so a narrowing is never silent. The conversation said it once when it was
 *  heard; this is its record. */
export function NotOffered({ phrases }: { phrases: string[] }) {
  if (phrases.length === 0) return null;
  return (
    <div data-testid="not-offered" className="py-[10px] text-[13px]" style={{ borderTop: "1px solid var(--line)" }}>
      <p className="m-0 text-ink">
        <span className="font-semibold">Not offered here:</span> {phrases.join(", ")}
      </p>
      <p className="m-0 mt-[2px] text-[12.5px] text-ink-2">This pipeline stops before it; the rest is yours.</p>
    </div>
  );
}
