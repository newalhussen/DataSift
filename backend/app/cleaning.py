"""Cleaning operations. Each returns a new DataFrame; the input is never modified."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .analysis import _is_number, _to_number, duplicate_mask, missing_mask

STRATEGIES = {"keep", "drop_rows", "mean", "median", "mode", "constant"}
NUMERIC_STRATEGIES = {"mean", "median"}


class CleaningError(ValueError):
    pass


@dataclass
class CleanOptions:
    trim_whitespace: bool = True
    drop_duplicates: bool = False
    duplicate_subset: list[str] | None = None
    missing: dict[str, dict[str, Any]] = field(default_factory=dict)  # column -> {"strategy": ..., "value": ...}
    default_strategy: str = "keep"


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:.6g}"


def clean(df: pd.DataFrame, opts: CleanOptions) -> tuple[pd.DataFrame, dict[str, int]]:
    out = df.copy()
    report = {"trimmed": 0, "duplicatesRemoved": 0, "rowsDroppedForMissing": 0, "cellsFilled": 0}
    unknown = [c for c in list(opts.missing) + (opts.duplicate_subset or []) if c not in out.columns]
    if unknown:
        raise CleaningError(f"Unknown column(s): {', '.join(unknown)}")
    if opts.default_strategy not in STRATEGIES - {"constant"}:
        raise CleaningError(f"Unsupported default strategy: {opts.default_strategy}")

    if opts.trim_whitespace:
        for c in out.columns:
            s = out[c].astype(str)
            trimmed = s.str.strip()
            report["trimmed"] += int((s != trimmed).sum())
            out[c] = trimmed

    drop_idx: set[Any] = set()
    for c in out.columns:
        spec = opts.missing.get(c, {"strategy": opts.default_strategy})
        strategy = spec.get("strategy", "keep")
        if strategy not in STRATEGIES:
            raise CleaningError(f"Unsupported strategy “{strategy}” for column “{c}”")
        if strategy == "keep":
            continue
        miss = missing_mask(out[c])
        if not miss.any():
            continue
        if strategy == "drop_rows":
            drop_idx.update(out.index[miss])
            continue
        present = out.loc[~miss, c]
        if strategy in NUMERIC_STRATEGIES:
            if len(present) == 0 or not present.map(_is_number).all():
                raise CleaningError(f"Column “{c}” is not numeric, so it cannot be filled with the {strategy}")
            nums = present.map(_to_number)
            fill = _fmt(nums.mean() if strategy == "mean" else nums.median())
        elif strategy == "mode":
            if len(present) == 0:
                raise CleaningError(f"Column “{c}” has no values to take a most common value from")
            fill = present.mode().iloc[0]
        else:  # constant
            value = spec.get("value")
            if value is None or str(value) == "":
                raise CleaningError(f"Enter the value to fill “{c}” with")
            fill = str(value)
        out.loc[miss, c] = fill
        report["cellsFilled"] += int(miss.sum())

    if drop_idx:
        report["rowsDroppedForMissing"] = len(drop_idx)
        out = out.drop(index=list(drop_idx))

    if opts.drop_duplicates:
        dups = duplicate_mask(out, opts.duplicate_subset)
        report["duplicatesRemoved"] = int(dups.sum())
        out = out[~dups]

    return out.reset_index(drop=True), report


def neutralize_formulas(df: pd.DataFrame) -> pd.DataFrame:
    """Prefix cells that a spreadsheet would run as formulas (=, @, or +/- followed by non-numbers) with an apostrophe."""
    out = df.copy()
    for c in out.columns:
        s = out[c].astype(str)
        risky = s.str.match(r"^[=@]") | (s.str.match(r"^[+-]") & ~s.map(_is_number))
        out[c] = s.where(~risky, "'" + s)
    return out
