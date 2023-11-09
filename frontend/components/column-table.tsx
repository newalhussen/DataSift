"use client";

import { Fragment, useState } from "react";
import type { ColumnReport } from "@/lib/api";

const TYPE_COLOR: Record<string, string> = { integer: "bg-sky-100 text-sky-800", float: "bg-sky-100 text-sky-800", datetime: "bg-violet-100 text-violet-800", boolean: "bg-teal-100 text-teal-800", text: "bg-slate-100 text-slate-800", empty: "bg-red-100 text-red-800" };

export function ColumnTable({ columns }: { columns: ColumnReport[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <section className="rounded-xl border border-line bg-card">
      <h2 className="border-b border-line px-4 py-3 text-sm font-semibold">Columns</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-muted"><tr><th className="px-4 py-2">Column</th><th>Type</th><th className="w-48">Missing</th><th>Unique</th><th>Problems</th><th /></tr></thead>
          <tbody className="divide-y divide-line">
            {columns.map((c) => (
              <Fragment key={c.name}>
                <tr className="align-middle">
                  <td className="px-4 py-2"><div className="font-medium">{c.name}</div><div className="max-w-xs truncate text-xs text-muted">{c.samples.join(" · ")}</div></td>
                  <td><span className={`rounded px-1.5 py-0.5 text-xs font-medium ${TYPE_COLOR[c.type] ?? TYPE_COLOR.text}`}>{c.type}</span></td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 overflow-hidden rounded bg-bg" aria-hidden="true"><div className="h-full bg-amber-500" style={{ width: `${Math.min(100, c.missingPct)}%` }} /></div>
                      <span className="text-xs tabular-nums text-muted">{c.missing} ({c.missingPct}%)</span>
                    </div>
                  </td>
                  <td className="tabular-nums">{c.unique.toLocaleString()}</td>
                  <td className="text-xs">
                    {c.inconsistent > 0 && <span className="mr-2 text-red-600">{c.inconsistent} wrong type</span>}
                    {c.whitespace > 0 && <span className="mr-2 text-sky-700">{c.whitespace} padded</span>}
                    {c.stats.outliers > 0 && <span className="text-amber-700">{c.stats.outliers} outliers</span>}
                    {c.inconsistent === 0 && c.whitespace === 0 && !c.stats.outliers && <span className="text-muted">—</span>}
                  </td>
                  <td className="pr-4 text-right"><button className="btn !py-0.5 text-xs" aria-expanded={open === c.name} onClick={() => setOpen(open === c.name ? null : c.name)}>{open === c.name ? "Hide" : "Details"}</button></td>
                </tr>
                {open === c.name && (
                  <tr><td colSpan={6} className="bg-bg px-4 py-3">
                    <div className="grid gap-4 text-sm sm:grid-cols-2">
                      <div>
                        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Statistics</h3>
                        {Object.keys(c.stats).length === 0 ? <p className="text-muted">None for this column.</p> : (
                          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5">{Object.entries(c.stats).map(([k, v]) => (<Fragment key={k}><dt className="text-muted">{k}</dt><dd className="tabular-nums">{v}</dd></Fragment>))}</dl>
                        )}
                        {c.inconsistentExamples.length > 0 && <p className="mt-2 text-red-600">Values that don’t fit: {c.inconsistentExamples.map((e) => `“${e}”`).join(", ")}</p>}
                      </div>
                      <div>
                        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Most common values</h3>
                        <ul>{c.topValues.map((t) => <li key={t.value} className="flex justify-between gap-4"><span className="truncate">{t.value}</span><span className="tabular-nums text-muted">{t.count}</span></li>)}</ul>
                      </div>
                    </div>
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
