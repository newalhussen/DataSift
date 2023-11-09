"""CSV data-quality analysis. Pure functions over a DataFrame of strings (nothing is guessed at read time)."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

# Cell values treated as "missing" in addition to blank cells.
NULL_TOKENS = {"", "na", "n/a", "nan", "null", "none", "nil", "-", "--", "?", "#n/a"}
BOOL_TOKENS = {"true", "false", "yes", "no", "y", "n", "t", "f", "0", "1"}
_NUMBER = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
_INTEGER = re.compile(r"^[+-]?\d+$")


def missing_mask(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower().isin(NULL_TOKENS)


def _is_number(v: str) -> bool:
    return bool(_NUMBER.match(v.replace(",", "") if re.match(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$", v) else v))


def _to_number(v: str) -> float:
    return float(v.replace(",", ""))


def _is_date_series(values: pd.Series) -> pd.Series:
    """Boolean mask of values that parse as dates (ISO-like or common separators; must contain a digit separator)."""
    shaped = values.str.match(r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}([ T]\d{1,2}:\d{2}(:\d{2})?)?(Z|[+-]\d{2}:?\d{2})?$")
    parsed = pd.to_datetime(values.where(shaped), errors="coerce", format="mixed", utc=True)
    return parsed.notna()


def infer_column(values: pd.Series) -> dict[str, Any]:
    """Infer the type of the non-missing values and report values that do not fit it."""
    vals = values.astype(str).str.strip()
    n = len(vals)
    if n == 0:
        return {"type": "empty", "conforming": 0, "offenders": []}
    num = vals.map(_is_number)
    lower = vals.str.lower()
    is_bool = lower.isin(BOOL_TOKENS)
    only_01 = lower.isin({"0", "1"}).all()
    is_date = _is_date_series(vals)
    candidates = {
        "boolean": (is_bool, 0.0 if only_01 else 1.0),  # all-0/1 columns read better as integers
        "integer": (vals.map(lambda v: bool(_INTEGER.match(v.replace(",", "")))) & num, 1.0),
        "float": (num, 1.0),
        "datetime": (is_date, 1.0),
    }
    best, best_share = "text", 0.0
    for name, (mask, weight) in candidates.items():
        if weight == 0.0:
            continue
        share = float(mask.mean())
        if share > best_share + 1e-9:
            best, best_share = name, share
    if best_share < 0.8:
        return {"type": "text", "conforming": n, "offenders": []}
    mask = candidates[best][0]
    offenders = vals[~mask].unique().tolist()[:5]
    return {"type": best, "conforming": int(mask.sum()), "offenders": offenders, "offenderCount": int((~mask).sum())}


def _numeric_stats(values: pd.Series) -> dict[str, Any]:
    nums = values.map(_to_number)
    q1, q3 = nums.quantile(0.25), nums.quantile(0.75)
    iqr = q3 - q1
    outliers = int(((nums < q1 - 1.5 * iqr) | (nums > q3 + 1.5 * iqr)).sum()) if iqr > 0 else 0
    return {
        "min": float(nums.min()), "max": float(nums.max()), "mean": round(float(nums.mean()), 4),
        "median": float(nums.median()), "std": round(float(nums.std()), 4) if len(nums) > 1 else 0.0, "outliers": outliers,
    }


def analyze_column(name: str, col: pd.Series) -> dict[str, Any]:
    miss = missing_mask(col)
    present = col[~miss].astype(str)
    stripped = present.str.strip()
    info = infer_column(stripped)
    out: dict[str, Any] = {
        "name": name,
        "type": info["type"],
        "missing": int(miss.sum()),
        "missingPct": round(float(miss.mean()) * 100, 2) if len(col) else 0.0,
        "unique": int(stripped.nunique()),
        "samples": stripped.head(3).tolist(),
        "whitespace": int((present != stripped).sum()),
        "inconsistent": 0,
        "inconsistentExamples": [],
        "stats": {},
        "topValues": [{"value": str(k), "count": int(v)} for k, v in stripped.value_counts().head(5).items()],
    }
    if info["type"] in ("integer", "float") and info.get("offenderCount", 0) == 0 and len(stripped):
        out["stats"] = _numeric_stats(stripped)
    elif info["type"] in ("integer", "float", "boolean", "datetime") and info.get("offenderCount", 0) > 0:
        out["inconsistent"] = info["offenderCount"]
        out["inconsistentExamples"] = info["offenders"]
    if info["type"] == "text" and len(stripped):
        lengths = stripped.str.len()
        out["stats"] = {"minLength": int(lengths.min()), "maxLength": int(lengths.max()), "meanLength": round(float(lengths.mean()), 2)}
    elif info["type"] in ("integer", "float") and info.get("offenderCount", 0) > 0:
        numeric_only = stripped[stripped.map(_is_number)]
        if len(numeric_only):
            out["stats"] = _numeric_stats(numeric_only)
    return out


def duplicate_mask(df: pd.DataFrame, subset: list[str] | None = None) -> pd.Series:
    key = df[subset] if subset else df
    return key.apply(lambda c: c.astype(str).str.strip()).duplicated(keep="first")


def analyze(df: pd.DataFrame) -> dict[str, Any]:
    rows, cols = df.shape
    columns = [analyze_column(str(c), df[c]) for c in df.columns]
    dups = duplicate_mask(df)
    missing_cells = sum(c["missing"] for c in columns)
    total_cells = rows * cols
    issues: list[dict[str, Any]] = []
    if dups.sum():
        issues.append({"severity": "warning", "kind": "duplicates", "message": f"{int(dups.sum())} duplicate rows ({dups.mean() * 100:.1f}%)"})
    for c in columns:
        if c["type"] == "empty" or (rows and c["missing"] == rows):
            issues.append({"severity": "error", "kind": "empty_column", "column": c["name"], "message": f"“{c['name']}” has no values"})
            continue
        if c["missingPct"] >= 1:
            issues.append({"severity": "error" if c["missingPct"] >= 30 else "warning", "kind": "missing", "column": c["name"],
                           "message": f"“{c['name']}” is {c['missingPct']}% missing ({c['missing']} rows)"})
        if c["inconsistent"]:
            issues.append({"severity": "error", "kind": "inconsistent_types", "column": c["name"],
                           "message": f"“{c['name']}” looks {c['type']} but {c['inconsistent']} values do not fit (e.g. {', '.join(map(repr, c['inconsistentExamples'][:3]))})"})
        if c["whitespace"]:
            issues.append({"severity": "info", "kind": "whitespace", "column": c["name"], "message": f"“{c['name']}” has {c['whitespace']} values with leading/trailing spaces"})
        if c["unique"] == 1 and rows > 1 and c["missing"] == 0:
            issues.append({"severity": "info", "kind": "constant", "column": c["name"], "message": f"“{c['name']}” has the same value in every row"})
        if c["stats"].get("outliers"):
            issues.append({"severity": "info", "kind": "outliers", "column": c["name"], "message": f"“{c['name']}” has {c['stats']['outliers']} statistical outliers"})
    names = [str(c) for c in df.columns]
    if len(set(names)) != len(names):
        issues.append({"severity": "error", "kind": "duplicate_columns", "message": "Some column names are repeated"})
    return {
        "rows": rows,
        "columns": cols,
        "duplicateRows": int(dups.sum()),
        "missingCells": int(missing_cells),
        "missingPct": round(missing_cells / total_cells * 100, 2) if total_cells else 0.0,
        "score": quality_score(rows, cols, int(dups.sum()), missing_cells, columns),
        "issues": issues,
        "columnReports": columns,
    }


def quality_score(rows: int, cols: int, dup_rows: int, missing_cells: int, columns: list[dict[str, Any]]) -> int:
    """0-100. Penalises missing cells, duplicate rows, type inconsistencies and whitespace, each weighted by how much of the data they touch."""
    if rows == 0 or cols == 0:
        return 0
    cells = rows * cols
    penalty = 70 * (missing_cells / cells) + 40 * (dup_rows / rows)
    penalty += 50 * (sum(c["inconsistent"] for c in columns) / cells) + 10 * (sum(c["whitespace"] for c in columns) / cells)
    return max(0, min(100, round(100 - penalty)))
