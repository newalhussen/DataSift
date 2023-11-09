import type { Analysis } from "@/lib/api";

const SEV = { error: "bg-red-100 text-red-800", warning: "bg-amber-100 text-amber-800", info: "bg-sky-100 text-sky-800" };

function Score({ value }: { value: number }) {
  const color = value >= 90 ? "#16a34a" : value >= 70 ? "#d97706" : "#dc2626";
  const r = 34, c = 2 * Math.PI * r;
  return (
    <div className="relative size-24" role="img" aria-label={`Quality score ${value} out of 100`}>
      <svg viewBox="0 0 80 80" className="size-full -rotate-90">
        <circle cx="40" cy="40" r={r} fill="none" stroke="var(--line)" strokeWidth="8" />
        <circle cx="40" cy="40" r={r} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round" strokeDasharray={`${(value / 100) * c} ${c}`} />
      </svg>
      <div className="absolute inset-0 grid place-items-center"><div className="text-center"><div className="text-2xl font-semibold leading-none">{value}</div><div className="text-[10px] text-muted">quality</div></div></div>
    </div>
  );
}

export function Summary({ data }: { data: Analysis }) {
  const tile = (label: string, value: string, hint?: string, warn?: boolean) => (
    <div className="rounded-xl border border-line bg-card p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${warn ? "text-amber-600" : ""}`}>{value}</div>
      {hint && <div className="text-xs text-muted">{hint}</div>}
    </div>
  );
  return (
    <section className="grid gap-4 lg:grid-cols-[auto_1fr]">
      <div className="flex items-center justify-center rounded-xl border border-line bg-card p-4"><Score value={data.score} /></div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {tile("Rows", data.rows.toLocaleString())}
        {tile("Columns", String(data.columns))}
        {tile("Duplicate rows", String(data.duplicateRows), data.rows ? `${((data.duplicateRows / data.rows) * 100).toFixed(1)}% of rows` : undefined, data.duplicateRows > 0)}
        {tile("Missing cells", data.missingCells.toLocaleString(), `${data.missingPct}% of all cells`, data.missingCells > 0)}
      </div>
      <div className="rounded-xl border border-line bg-card p-4 lg:col-span-2">
        <h2 className="mb-2 text-sm font-semibold">Issues found</h2>
        {data.issues.length === 0 ? <p className="text-sm text-emerald-600">No problems detected.</p> : (
          <ul className="space-y-1.5 text-sm">
            {data.issues.map((i, n) => (
              <li key={n} className="flex items-start gap-2"><span className={`mt-0.5 rounded px-1.5 py-0.5 text-[11px] font-medium ${SEV[i.severity]}`}>{i.severity}</span><span>{i.message}</span></li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
