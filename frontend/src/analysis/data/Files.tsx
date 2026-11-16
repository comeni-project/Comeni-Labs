import { useQuery } from "@tanstack/react-query";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { DataTable } from "../../ui/DataTable";
import { Panel } from "../../ui/Panel";

type FilesPage = components["schemas"]["FilesPage"];
type File = FilesPage["files"][number];

function size(bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let n = bytes;
  let unit = 0;
  while (n >= 1024 && unit < units.length - 1) { n /= 1024; unit += 1; }
  return unit === 0 ? `${n} B` : `${n.toFixed(1)} ${units[unit]}`;
}

/** Data · Files (#511): every file in the ticked folders and what it was recognised as. */
export function Files({ draftId }: { draftId: string }) {
  const files = useQuery({
    queryKey: ["analysis-files", draftId],
    queryFn: () => get<FilesPage>(`/data/${encodeURIComponent(draftId)}/files?limit=1000`),
  });
  const rows = files.data?.files ?? [];
  return (
    <Panel title="Every file in the ticked folders" hint={`${files.data?.total ?? 0} files · what each was recognised as`}>
      <DataTable<File> label="Files" rows={rows} rowKey={(f) => f.path} height={Math.min(600, 38 * Math.max(rows.length, 3))}
        columns={[
          { id: "name", header: "File", cell: (f) => <span className="font-data text-[12px] text-ink">{f.name}</span> },
          { id: "kind", header: "Recognised as", width: "160px",
            cell: (f) => <span className="text-ink-2">{f.recognised ?? "—"}</span> },
          { id: "use", header: "Used for", width: "180px", cell: (f) => (
            <span className={f.sample || f.used_as ? "text-ink-2" : "text-needs-you-ink"}>
              {f.used_as === "reference" ? "reference" : f.sample ? `sample ${f.sample}` : "did not fit the rule"}
            </span>
          ) },
          { id: "size", header: "Size", width: "90px", cell: (f) => <span className="font-data text-[12px] text-ink-3">{size(f.size)}</span> },
        ]} />
    </Panel>
  );
}
