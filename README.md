# DataSift

CSV data-quality analyzer. Upload a file, see what is wrong with it, fix the simple problems and download a clean copy.

## Features
- Upload with enforced limits (10 MB, 200,000 rows, 200 columns, `.csv/.tsv/.txt`), encoding (UTF-8/Windows-1252) and delimiter detection.
- Real analysis with pandas: per-column type inference (integer, float, boolean, datetime, text), missing values (blank, `NA`, `null`, `-`…), duplicate rows, values that break a column's type (e.g. `abc` in an age column), padded whitespace, numeric statistics and IQR outliers, top values, constant columns, and an overall 0–100 quality score.
- Cleaning: trim whitespace, drop duplicate rows (optionally by chosen columns via API), and per-column missing-value handling (drop rows, mean, median, most common, constant). Cleaning always starts from the original upload, so options never compound.
- Paged data preview, downloads of the cleaned or original file.

## Architecture
```
frontend/ Next.js + Tailwind  ──fetch (CORS)──▶  backend/ FastAPI + pandas  ──▶  temp files on disk
```
Everything is read as text (`dtype=str`) so nothing is silently coerced; types are inferred from the values and reported. There is no database: each upload lives in its own random-ID directory under the system temp folder.

## Safety and limits
- Oversized uploads are cut off while streaming (413). Binary files, ragged rows, repeated/empty headers, empty files and over-limit shapes return clear 422 messages instead of stack traces.
- Dataset IDs are 32-hex UUIDs validated before touching the filesystem (no path traversal); files are stored as plain CSV, never pickled.
- Temporary data is swept after `DATASET_TTL_MINUTES` (60) and capped at `MAX_DATASETS` (50, oldest evicted).
- Downloads prefix cells that start with `=` or `@` (and `+`/`-` followed by non-numbers) with `'` to prevent spreadsheet formula injection; pass `?safe=false` to disable.
- No authentication: this is a single-tenant utility. Anyone who can reach the API can upload; put it behind your own auth if exposed.

## Setup
Prerequisites: Python 3.10+, Node 20+.
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000                        # API docs at http://localhost:8000/docs

cd ../frontend
cp .env.example .env.local
npm install && npm run dev                              # http://localhost:3000
```
Backend configuration is via environment variables, see `backend/.env.example` (`MAX_UPLOAD_MB`, `MAX_ROWS`, `MAX_COLUMNS`, `DATASET_TTL_MINUTES`, `MAX_DATASETS`, `UPLOAD_DIR`, `CORS_ORIGINS`). Load the file with `uvicorn --env-file .env`.

## Tests
`cd backend && pip install -r requirements-dev.txt && pytest` (32 tests): type inference and issue detection, quality score, every cleaning strategy and its error cases, input immutability, formula neutralisation, CSV parsing edge cases, and the full upload → clean → download → reset → delete API flow including size/extension limits, malformed files, ID validation, TTL sweep and eviction.
