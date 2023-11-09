"use client";

import { useCallback, useRef, useState } from "react";
import { CleanPanel } from "@/components/clean-panel";
import { ColumnTable } from "@/components/column-table";
import { PreviewTable } from "@/components/preview-table";
import { Summary } from "@/components/summary";
import { removeDataset, upload, type Analysis } from "@/lib/api";

const MAX_MB = 10;

export default function Home() {
  const [data, setData] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const send = useCallback(async (file: File | undefined) => {
    if (!file) return;
    setError("");
    if (!/\.(csv|tsv|txt)$/i.test(file.name)) return setError("Choose a .csv file.");
    if (file.size > MAX_MB * 1024 * 1024) return setError(`That file is larger than ${MAX_MB} MB.`);
    setBusy(true);
    try {
      if (data) void removeDataset(data.id);
      setData(await upload(file));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }, [data]);

  if (!data) {
    return (
      <div className="mx-auto max-w-2xl space-y-6 pt-8 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Find what’s wrong with your CSV.</h1>
        <p className="text-muted">Upload a file to see missing values, duplicates, inconsistent types and column statistics. Fix the simple problems and download a clean copy.</p>
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); void send(e.dataTransfer.files?.[0]); }}
          className={`rounded-2xl border-2 border-dashed p-12 transition ${drag ? "border-accent bg-card" : "border-line"}`}
        >
          <input ref={input} type="file" accept=".csv,.tsv,.txt,text/csv" className="sr-only" id="file" onChange={(e) => send(e.target.files?.[0])} />
          <p className="mb-4 text-sm text-muted">Drop a CSV here, or</p>
          <button className="btn btn-primary" disabled={busy} onClick={() => input.current?.click()}>{busy ? "Analyzing…" : "Choose a file"}</button>
          <p className="mt-4 text-xs text-muted">Up to {MAX_MB} MB and 200,000 rows. Files are deleted automatically after an hour.</p>
        </div>
        {error && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-semibold">{data.filename}</h1>
          <p className="text-sm text-muted">{data.cleaned ? "Showing the cleaned version" : "Original file"}</p>
        </div>
        <input ref={input} type="file" accept=".csv,.tsv,.txt,text/csv" className="sr-only" aria-label="Upload another file" onChange={(e) => send(e.target.files?.[0])} />
        <button className="btn" disabled={busy} onClick={() => input.current?.click()}>{busy ? "Analyzing…" : "Upload another file"}</button>
      </div>
      {error && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <Summary data={data} />
      <CleanPanel data={data} onChange={setData} />
      <ColumnTable columns={data.columnReports} />
      <PreviewTable id={data.id} version={data.cleaned ? "cleaned" : "original"} key={`${data.id}-${data.cleaned}-${data.rows}`} />
    </div>
  );
}
