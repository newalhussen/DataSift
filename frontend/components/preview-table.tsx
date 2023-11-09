"use client";

import { useEffect, useState } from "react";
import { preview, type Preview } from "@/lib/api";

export function PreviewTable({ id, version }: { id: string; version: string }) {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setError("");
    preview(id, offset, version).then(setData).catch((e) => setError(e.message));
  }, [id, offset, version]);

  return (
    <section className="rounded-xl border border-line bg-card">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold">Data preview</h2>
        {data && (
          <div className="flex items-center gap-2 text-xs text-muted">
            {offset + 1}–{Math.min(offset + data.rows.length, data.total)} of {data.total.toLocaleString()}
            <button className="btn !py-0.5" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Prev</button>
            <button className="btn !py-0.5" disabled={offset + 25 >= data.total} onClick={() => setOffset(offset + 25)}>Next</button>
          </div>
        )}
      </div>
      {error && <p role="alert" className="p-4 text-sm text-red-600">{error}</p>}
      {!data && !error && <p className="p-4 text-sm text-muted">Loading preview…</p>}
      {data && (
        <div className="max-h-[28rem] overflow-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card text-left"><tr><th className="px-3 py-2 text-muted">#</th>{data.columns.map((c) => <th key={c} className="whitespace-nowrap px-3 py-2">{c}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {data.rows.map((r, i) => (
                <tr key={i}><td className="px-3 py-1.5 text-muted">{offset + i + 1}</td>{r.map((v, j) => <td key={j} className="max-w-[16rem] truncate whitespace-nowrap px-3 py-1.5" title={v}>{v === "" ? <span className="text-muted">∅</span> : v}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
