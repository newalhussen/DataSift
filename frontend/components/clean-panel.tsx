"use client";

import { useState } from "react";
import { cleanDataset, downloadUrl, resetDataset, type Analysis, type MissingSpec } from "@/lib/api";

const NUMERIC = new Set(["integer", "float"]);

export function CleanPanel({ data, onChange }: { data: Analysis; onChange: (a: Analysis) => void }) {
  const [trim, setTrim] = useState(true);
  const [dups, setDups] = useState(data.duplicateRows > 0);
  const [spec, setSpec] = useState<Record<string, MissingSpec>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const withMissing = data.columnReports.filter((c) => c.missing > 0);

  async function apply() {
    setBusy(true);
    setError("");
    try {
      const missing = Object.fromEntries(Object.entries(spec).filter(([, s]) => s.strategy !== "keep"));
      onChange(await cleanDataset(data.id, { trimWhitespace: trim, dropDuplicates: dups, missing }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-line bg-card p-4">
      <h2 className="text-sm font-semibold">Clean</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={trim} onChange={(e) => setTrim(e.target.checked)} />Trim leading and trailing spaces</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={dups} onChange={(e) => setDups(e.target.checked)} />Remove duplicate rows ({data.duplicateRows} found, first occurrence kept)</label>
      </div>
      {withMissing.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Missing values</h3>
          <div className="grid gap-2 md:grid-cols-2">
            {withMissing.map((c) => {
              const s = spec[c.name] ?? { strategy: "keep" };
              return (
                <div key={c.name} className="flex items-center gap-2 rounded-lg border border-line p-2 text-sm">
                  <div className="min-w-0 flex-1"><div className="truncate font-medium">{c.name}</div><div className="text-xs text-muted">{c.missing} missing · {c.type}</div></div>
                  <select className="input !w-auto" aria-label={`Missing values in ${c.name}`} value={s.strategy} onChange={(e) => setSpec({ ...spec, [c.name]: { ...s, strategy: e.target.value } })}>
                    <option value="keep">Leave as is</option>
                    <option value="drop_rows">Drop those rows</option>
                    {NUMERIC.has(c.type) && <option value="mean">Fill with mean</option>}
                    {NUMERIC.has(c.type) && <option value="median">Fill with median</option>}
                    <option value="mode">Fill with most common</option>
                    <option value="constant">Fill with a value…</option>
                  </select>
                  {s.strategy === "constant" && <input className="input !w-28" aria-label={`Fill value for ${c.name}`} placeholder="value" value={s.value ?? ""} onChange={(e) => setSpec({ ...spec, [c.name]: { ...s, value: e.target.value } })} />}
                </div>
              );
            })}
          </div>
        </div>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-red-600">{error}</p>}
      {data.report && (
        <p className="mt-3 rounded-lg bg-bg px-3 py-2 text-sm">
          Cleaned: {data.before ? `${data.before.rows.toLocaleString()} → ${data.rows.toLocaleString()} rows` : ""}
          {data.report.duplicatesRemoved ? ` · ${data.report.duplicatesRemoved} duplicates removed` : ""}
          {data.report.rowsDroppedForMissing ? ` · ${data.report.rowsDroppedForMissing} rows dropped` : ""}
          {data.report.cellsFilled ? ` · ${data.report.cellsFilled} cells filled` : ""}
          {data.report.trimmed ? ` · ${data.report.trimmed} values trimmed` : ""}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn btn-primary" disabled={busy} onClick={apply}>{busy ? "Cleaning…" : "Apply cleaning"}</button>
        {data.cleaned && <a className="btn" href={downloadUrl(data.id, "cleaned")}>Download cleaned CSV</a>}
        {data.cleaned && <button className="btn" onClick={async () => onChange(await resetDataset(data.id))}>Reset to original</button>}
        <a className="btn" href={downloadUrl(data.id, "original")}>Download original</a>
      </div>
      <p className="mt-2 text-xs text-muted">Cleaning always starts from the original file, so changing options never compounds. Downloads prefix spreadsheet-formula-looking cells (=, @) with an apostrophe.</p>
    </section>
  );
}
