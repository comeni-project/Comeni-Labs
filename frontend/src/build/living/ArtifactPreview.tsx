import { useEffect, useRef, useState } from "react";

import type { AuthoringPreview } from "../../api/types";

/** `pipeline.yml` as it would read now — **a preview, and it says so.**
 *
 * The server is the serializer; this only draws its text. What changed since the last revision is
 * highlighted, for presentation only, and settles back to ordinary text once it has been seen. A
 * draft that is empty, illegal or cannot be materialised shows why, never half a document.
 */
export function ArtifactPreview({ preview }: { preview: AuthoringPreview | null }) {
  const previous = useRef<string[]>([]);
  const [changed, setChanged] = useState<Set<number>>(new Set());
  const lines = preview?.state === "ready" ? preview.text.split("\n") : [];

  useEffect(() => {
    if (preview?.state !== "ready") return;
    const before = previous.current;
    const fresh = new Set<number>();
    if (before.length > 0) {
      // A line is new when the old text did not hold it at all. **Presentation, never a diff the
      // pipeline depends on** — the browser compares lines, and the file is the server's.
      const had = new Map<string, number>();
      for (const line of before) had.set(line, (had.get(line) ?? 0) + 1);
      lines.forEach((line, index) => {
        const left = had.get(line) ?? 0;
        if (left > 0) had.set(line, left - 1);
        else fresh.add(index);
      });
    }
    previous.current = lines;
    setChanged(fresh);
    if (fresh.size === 0) return;
    const settle = setTimeout(() => setChanged(new Set()), 1600);
    return () => clearTimeout(settle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview?.revision, preview?.state]);

  if (!preview) {
    return <p className="m-0 text-[12.5px] text-ink-3" data-testid="preview-loading">Reading the draft…</p>;
  }
  if (preview.state !== "ready") {
    const say: Record<string, string> = {
      empty: "Nothing has been added yet, so there is no pipeline to show.",
      illegal: "The draft is not a legal pipeline right now, so there is no pipeline.yml to show.",
      unavailable: "This draft cannot be written as a pipeline.yml yet.",
    };
    return (
      <div data-testid={`preview-${preview.state}`}>
        <p className="m-0 text-[12.5px] text-ink-2">{say[preview.state]}</p>
        {preview.findings.length > 0 && (
          <ul className="m-0 mt-2 p-0">
            {preview.findings.map((finding) => (
              <li key={finding} className="list-none font-data text-[11px] text-ink-3">{finding}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div>
      <p className="m-0 mb-3 font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3" data-testid="preview-label">
        Preview · revision {preview.revision} · not kept
      </p>
      <pre data-testid="artifact-text" className="m-0 font-data text-[11px] leading-[1.6] text-ink-2 whitespace-pre">
        {lines.map((line, index) => (
          <span
            key={index}
            data-changed={changed.has(index) || undefined}
            className="block"
            style={changed.has(index) ? { background: "var(--link-soft)", color: "var(--ink)" } : undefined}
          >
            {line || " "}
          </span>
        ))}
      </pre>
    </div>
  );
}
