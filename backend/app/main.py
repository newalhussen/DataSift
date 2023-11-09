from __future__ import annotations

import csv
import io
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import config, store
from .analysis import analyze
from .cleaning import CleaningError, CleanOptions, clean, neutralize_formulas

app = FastAPI(title="DataSift API", version="1.0.0", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"],
                   expose_headers=["Content-Disposition"])


def parse_csv(raw: bytes) -> tuple[pd.DataFrame, str]:
    """Decode and parse a CSV safely. Raises ValueError with a user-facing message."""
    if not raw.strip():
        raise ValueError("The file is empty.")
    if b"\x00" in raw[:4096]:
        raise ValueError("This does not look like a text CSV file (binary content found).")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - cp1252 can fail on a few bytes
        text = raw.decode("latin-1")
    try:
        delimiter = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    header = next(csv.reader(io.StringIO(text), delimiter=delimiter), [])
    if len(header) > config.MAX_COLUMNS:
        raise ValueError(f"Too many columns ({len(header)}). The limit is {config.MAX_COLUMNS}.")
    names = [h.strip() for h in header]
    if len(set(names)) != len(names):
        raise ValueError("Column names must be unique; some are repeated in the header row.")
    if any(n == "" for n in names):
        raise ValueError("Every column needs a name; the header row has an empty one.")
    try:
        for n, row in enumerate(csv.reader(io.StringIO(text), delimiter=delimiter), start=1):
            if row and len(row) != len(header):
                raise ValueError(f"The CSV is malformed: row {n} has {len(row)} fields but the header has {len(header)}.")
        df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False, index_col=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, csv.Error) as e:
        raise ValueError(f"The CSV is malformed: {str(e).splitlines()[0][:200]}") from e
    if df.empty:
        raise ValueError("The file has a header but no data rows.")
    if len(df) > config.MAX_ROWS:
        raise ValueError(f"Too many rows ({len(df):,}). The limit is {config.MAX_ROWS:,}.")
    df.columns = names
    return df, delimiter


def _get(dataset_id: str, version: str = "current") -> pd.DataFrame:
    try:
        return store.load(dataset_id, version)
    except KeyError:
        raise HTTPException(404, "Dataset not found. It may have expired; upload the file again.") from None


def _payload(dataset_id: str, df: pd.DataFrame, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    m = store.meta(dataset_id)
    return {"id": dataset_id, "filename": m["filename"], "cleaned": store.has_cleaned(dataset_id), **analyze(df), **(extra or {})}


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/datasets", status_code=201)
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    name = (file.filename or "upload.csv").replace("\\", "/").split("/")[-1][:120]
    if not name.lower().endswith((".csv", ".tsv", ".txt")):
        raise HTTPException(415, "Upload a .csv file.")
    # read in chunks so an oversized upload is refused without holding it all in memory
    buf = bytearray()
    while chunk := await file.read(1024 * 1024):
        buf += chunk
        if len(buf) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"The file is larger than the {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
    try:
        df, delimiter = parse_csv(bytes(buf))
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    dataset_id = store.create(df, name, delimiter)
    return _payload(dataset_id, df)


@app.get("/api/datasets/{dataset_id}")
def get_dataset(dataset_id: str) -> dict[str, Any]:
    return _payload(dataset_id, _get(dataset_id))


@app.get("/api/datasets/{dataset_id}/preview")
def preview(dataset_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), version: str = "current") -> dict[str, Any]:
    df = _get(dataset_id, version if version in ("current", "original", "cleaned") else "current")
    page = df.iloc[offset: offset + limit]
    return {"columns": list(df.columns), "rows": page.values.tolist(), "offset": offset, "total": len(df)}


class MissingSpec(BaseModel):
    strategy: str = "keep"
    value: str | None = Field(default=None, max_length=500)


class CleanRequest(BaseModel):
    trimWhitespace: bool = True
    dropDuplicates: bool = False
    duplicateSubset: list[str] | None = None
    missing: dict[str, MissingSpec] = {}
    defaultStrategy: str = "keep"


@app.post("/api/datasets/{dataset_id}/clean")
def clean_dataset(dataset_id: str, req: CleanRequest) -> dict[str, Any]:
    original = _get(dataset_id, "original")  # always clean from the original so options are not compounded
    opts = CleanOptions(
        trim_whitespace=req.trimWhitespace, drop_duplicates=req.dropDuplicates, duplicate_subset=req.duplicateSubset or None,
        missing={k: v.model_dump() for k, v in req.missing.items()}, default_strategy=req.defaultStrategy,
    )
    try:
        cleaned, report = clean(original, opts)
    except CleaningError as e:
        raise HTTPException(422, str(e)) from None
    if cleaned.empty:
        raise HTTPException(422, "These options would remove every row.")
    store.save_cleaned(dataset_id, cleaned)
    return _payload(dataset_id, cleaned, {"report": report, "before": {"rows": len(original)}})


@app.post("/api/datasets/{dataset_id}/reset")
def reset(dataset_id: str) -> dict[str, Any]:
    original = _get(dataset_id, "original")
    try:
        (store.config.UPLOAD_DIR / dataset_id / "cleaned.csv").unlink(missing_ok=True)
    except OSError:
        pass
    return _payload(dataset_id, original)


@app.get("/api/datasets/{dataset_id}/download")
def download(dataset_id: str, version: str = "cleaned", safe: bool = True) -> Response:
    if version not in ("cleaned", "original"):
        raise HTTPException(400, "version must be cleaned or original")
    try:
        df = store.load(dataset_id, version)
    except KeyError:
        raise HTTPException(404, "Nothing to download. Clean the dataset first, or upload it again if it expired.") from None
    if safe:
        df = neutralize_formulas(df)
    base = store.meta(dataset_id)["filename"].rsplit(".", 1)[0] or "data"
    safe_name = "".join(c for c in base if c.isalnum() or c in "-_ ")[:80] or "data"
    return Response(df.to_csv(index=False), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{safe_name}_{version}.csv"'})


@app.delete("/api/datasets/{dataset_id}", status_code=204)
def delete(dataset_id: str) -> Response:
    try:
        store.delete(dataset_id)
    except KeyError:
        raise HTTPException(404, "Dataset not found.") from None
    return Response(status_code=204)
