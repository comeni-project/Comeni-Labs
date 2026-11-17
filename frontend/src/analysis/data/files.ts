import { get } from "../../api/client";
import type { components } from "../../api/schema";

type FilesPage = components["schemas"]["FilesPage"];
type File = FilesPage["files"][number];

/** Every file, a page at a time: no cap, however many there are (Checkpoint C). */
export async function allFiles(draftId: string): Promise<FilesPage> {
  const files: File[] = [];
  let total = 0;
  do {
    const page = await get<FilesPage>(`/data/${encodeURIComponent(draftId)}/files?offset=${files.length}&limit=1000`);
    files.push(...page.files);
    total = page.total;
    if (page.files.length === 0) break;
  } while (files.length < total);
  return { files, total };
}
