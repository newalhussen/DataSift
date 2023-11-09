export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ColumnReport {
  name: string; type: string; missing: number; missingPct: number; unique: number; samples: string[]; whitespace: number;
  inconsistent: number; inconsistentExamples: string[]; stats: Record<string, number>; topValues: { value: string; count: number }[];
}
export interface Issue { severity: "error" | "warning" | "info"; kind: string; column?: string; message: string }
export interface Analysis {
  id: string; filename: string; cleaned: boolean; rows: number; columns: number; duplicateRows: number; missingCells: number; missingPct: number;
  score: number; issues: Issue[]; columnReports: ColumnReport[]; report?: { trimmed: number; duplicatesRemoved: number; rowsDroppedForMissing: number; cellsFilled: number };
  before?: { rows: number };
}
export interface Preview { columns: string[]; rows: string[][]; offset: number; total: number }
export interface MissingSpec { strategy: string; value?: string }
export interface CleanRequest { trimWhitespace: boolean; dropDuplicates: boolean; missing: Record<string, MissingSpec> }

async function parse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map((x: { msg: string }) => x.msg).join("; ") : `Request failed (${res.status})`);
  }
  return data as T;
}
const net = (e: unknown) => (e instanceof Error && e.message !== "Failed to fetch" ? e : new Error("Cannot reach the analysis server."));

export const upload = (file: File) => {
  const f = new FormData();
  f.append("file", file);
  return fetch(`${API}/api/datasets`, { method: "POST", body: f }).then((r) => parse<Analysis>(r)).catch((e) => { throw net(e); });
};
export const preview = (id: string, offset: number, version = "current") =>
  fetch(`${API}/api/datasets/${id}/preview?offset=${offset}&limit=25&version=${version}`).then((r) => parse<Preview>(r)).catch((e) => { throw net(e); });
export const cleanDataset = (id: string, body: CleanRequest) =>
  fetch(`${API}/api/datasets/${id}/clean`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }).then((r) => parse<Analysis>(r)).catch((e) => { throw net(e); });
export const resetDataset = (id: string) => fetch(`${API}/api/datasets/${id}/reset`, { method: "POST" }).then((r) => parse<Analysis>(r)).catch((e) => { throw net(e); });
export const removeDataset = (id: string) => fetch(`${API}/api/datasets/${id}`, { method: "DELETE" }).catch(() => undefined);
export const downloadUrl = (id: string, version: "cleaned" | "original") => `${API}/api/datasets/${id}/download?version=${version}`;
