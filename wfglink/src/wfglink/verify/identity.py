"""Canonical identity of a run folder: content hashes of its tables and of its summary.

Two runs are the same analysis when every table holds the same rows and the summaries
agree apart from what changes on every run. A table's hash covers its column names and
dtypes, its row count and pandas.util.hash_pandas_object over its rows (index left out),
so it ignores the Parquet file's bytes (writer version, compression, row groups) but not
a single changed value, column order or dtype. Timing columns are dropped first (frames.ms,
the per-frame processing time; hp_frames.observer_ms likewise). The summary hash is the
hash of summary.json without created, seconds, git_commit, git_dirty and the
high_precision block. `compare(a, b)` tells which tables differ.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DROP_COLUMNS = {"frames": ("ms",), "hp_frames": ("observer_ms",)}
DROP_SUMMARY = ("created", "seconds", "git_commit", "git_dirty", "high_precision")


def table_hash(df, drop: tuple[str, ...] = ()) -> str:
    """SHA-256 of column names, dtypes, row count and the rows' pandas hashes."""
    import pandas as pd

    df = df.drop(columns=[c for c in drop if c in df.columns])
    head = json.dumps({"columns": [str(c) for c in df.columns], "dtypes": [str(t) for t in df.dtypes],
                       "rows": int(len(df))}, sort_keys=True).encode("utf-8")
    h = hashlib.sha256(head)
    if len(df) and len(df.columns):
        h.update(pd.util.hash_pandas_object(df, index=False).to_numpy().astype("<u8").tobytes())
    return h.hexdigest()


def clean_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in summary.items() if k not in DROP_SUMMARY}


def summary_hash(summary: dict[str, Any]) -> str:
    from wfglink.provenance import sha256_json

    return sha256_json(clean_summary(summary))


def run_identity(run_dir: str | Path, recursive: bool = True) -> dict[str, Any]:
    """{"tables": {relative path: hash}, "summary": hash or None} of a run folder (Parquet
    tables, also in subfolders such as high_precision/ when recursive)."""
    import pandas as pd

    run = Path(run_dir)
    if not run.is_dir():
        raise ValueError(f"{run} is not a folder")
    files = sorted(run.rglob("*.parquet") if recursive else run.glob("*.parquet"))
    tables = {p.relative_to(run).as_posix(): table_hash(pd.read_parquet(p), DROP_COLUMNS.get(p.stem, ()))
              for p in files}
    s = run / "summary.json"
    return {"tables": tables,
            "summary": summary_hash(json.loads(s.read_text(encoding="utf-8"))) if s.exists() else None}


def compare(a: str | Path | dict[str, Any], b: str | Path | dict[str, Any], tables: list[str] | None = None,
            recursive: bool = True) -> dict[str, Any]:
    """Which tables (all, or the given relative paths) and whether the cleaned summaries
    agree between two run folders (or their run_identity records)."""
    ia = a if isinstance(a, dict) else run_identity(a, recursive)
    ib = b if isinstance(b, dict) else run_identity(b, recursive)
    names = tables if tables is not None else sorted(set(ia["tables"]) | set(ib["tables"]))
    per = {n: {"a": ia["tables"].get(n), "b": ib["tables"].get(n),
               "equal": ia["tables"].get(n) is not None and ia["tables"].get(n) == ib["tables"].get(n)} for n in names}
    summary_equal = ia["summary"] == ib["summary"]
    return {"identical": all(v["equal"] for v in per.values()) and summary_equal, "summary_equal": summary_equal,
            "tables": per, "only_a": sorted(n for n in names if n in ia["tables"] and n not in ib["tables"]),
            "only_b": sorted(n for n in names if n in ib["tables"] and n not in ia["tables"]),
            "different": sorted(n for n, v in per.items() if not v["equal"])}
