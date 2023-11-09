"""Temporary dataset storage on disk. Files expire after a TTL and the total count is capped."""
from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path

import pandas as pd

from . import config

_ID = re.compile(r"^[0-9a-f]{32}$")


def _dir(dataset_id: str) -> Path:
    if not _ID.match(dataset_id):
        raise KeyError(dataset_id)
    return config.UPLOAD_DIR / dataset_id


def sweep(now: float | None = None) -> int:
    """Remove expired datasets and, if over the cap, the oldest ones. Returns how many were removed."""
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    now = now or time.time()
    entries = sorted((p for p in config.UPLOAD_DIR.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
    removed = 0
    for p in entries[:]:
        if now - p.stat().st_mtime > config.TTL_SECONDS:
            shutil.rmtree(p, ignore_errors=True)
            entries.remove(p)
            removed += 1
    while len(entries) > config.MAX_DATASETS:
        shutil.rmtree(entries.pop(0), ignore_errors=True)
        removed += 1
    return removed


def create(df: pd.DataFrame, filename: str, delimiter: str) -> str:
    sweep()
    dataset_id = uuid.uuid4().hex
    d = _dir(dataset_id)
    d.mkdir(parents=True)
    df.to_csv(d / "original.csv", index=False)
    (d / "meta.json").write_text(json.dumps({"filename": filename, "delimiter": delimiter, "created": time.time()}))
    return dataset_id


def meta(dataset_id: str) -> dict:
    p = _dir(dataset_id) / "meta.json"
    if not p.exists():
        raise KeyError(dataset_id)
    return json.loads(p.read_text())


def load(dataset_id: str, version: str = "current") -> pd.DataFrame:
    d = _dir(dataset_id)
    cleaned, original = d / "cleaned.csv", d / "original.csv"
    path = cleaned if version in ("current", "cleaned") and cleaned.exists() else original
    if version == "cleaned" and not cleaned.exists():
        raise KeyError("no cleaned version")
    if not path.exists():
        raise KeyError(dataset_id)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def save_cleaned(dataset_id: str, df: pd.DataFrame) -> None:
    df.to_csv(_dir(dataset_id) / "cleaned.csv", index=False)


def has_cleaned(dataset_id: str) -> bool:
    return (_dir(dataset_id) / "cleaned.csv").exists()


def delete(dataset_id: str) -> bool:
    d = _dir(dataset_id)
    if not d.exists():
        return False
    shutil.rmtree(d, ignore_errors=True)
    return True
