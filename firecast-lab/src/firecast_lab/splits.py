"""Whole-fire splits (``firecast-lab/SPLITS.json``) and the checks that keep them honest.

The splits cover the repo's event catalog (``forecast/data/environment/events.json``, metadata only) exactly
once, by whole fire. ``check`` raises on any violation; the tests run it on the committed file.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from datetime import datetime
from pathlib import Path

LAB = Path(__file__).resolve().parents[2]
REPO = LAB.parent
SPLITS_PATH = LAB / "SPLITS.json"
CATALOG_PATH = REPO / "forecast" / "data" / "environment" / "events.json"

SPLITS = ("dev", "test", "fresh_holdout")
TEST_SEASONS = {("US", 2024), ("KR", 2025)}
FOLD_OF_YEAR = {2020: "Y2020", 2021: "Y2021", 2022: "Y2022_2023", 2023: "Y2022_2023"}
FLAGS = {"too_short_24h", "no_c651_rows"}
FIRE_KEYS = {"id", "name", "country", "year", "split", "fold", "flags", "c651_role", "truth", "start_utc",
             "end_utc", "duration_h", "grid_wh", "valid_arrival_pixels", "approx_windows_24h", "approx_windows_12h"}
WINDOW_SPACING_H = 12.0


def load_splits(path: Path | str = SPLITS_PATH) -> dict:
    return json.loads(Path(path).read_text())


def load_catalog(path: Path | str = CATALOG_PATH) -> tuple[list[dict], str]:
    """The event catalog and its SHA-256 (metadata only; rasters live in the real data root)."""
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def fires(split: str, *, fold: str | None = None, splits: dict | None = None) -> list[str]:
    """Fire ids of one split, optionally one dev fold."""
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    records = (splits or load_splits())["fires"]
    return [f["id"] for f in records if f["split"] == split and (fold is None or f["fold"] == fold)]


def approx_windows(start_utc: str, end_utc: str, lead_h: float, spacing_h: float = WINDOW_SPACING_H) -> int:
    """Cutoffs c = start + spacing*k (k >= 1) with c + lead < end, from catalog times only (SPLITS window_rule)."""
    duration = (datetime.fromisoformat(end_utc) - datetime.fromisoformat(start_utc)).total_seconds() / 3600.0
    n = 0
    while spacing_h * (n + 1) + lead_h < duration:
        n += 1
    return n


def check(splits: dict, catalog: list[dict], catalog_sha256: str) -> None:
    """Raise ValueError unless the splits are disjoint, cover the catalog exactly and are by whole fire."""
    problems: list[str] = []
    if splits["catalog"]["sha256"] != catalog_sha256:
        problems.append("catalog sha256 differs from SPLITS.json: the catalog changed, revisit the splits")
    records = splits["fires"]
    ids = [f["id"] for f in records]
    by_id = {e["id"]: e for e in catalog}
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        problems.append(f"fires listed more than once: {duplicates}")
    if set(ids) != set(by_id):
        problems.append(f"not an exact cover of the catalog: missing {sorted(set(by_id) - set(ids))}, "
                        f"unknown {sorted(set(ids) - set(by_id))}")
    if set(splits["folds"]) != set(FOLD_OF_YEAR.values()):
        problems.append(f"folds must be exactly {sorted(set(FOLD_OF_YEAR.values()))}")
    for f in records:
        e = by_id.get(f["id"])
        if set(f) != FIRE_KEYS:
            problems.append(f"{f['id']}: fields must be exactly {sorted(FIRE_KEYS)} (whole-fire records only)")
        if e is None:
            continue
        for key in ("name", "country", "year", "start_utc", "end_utc", "valid_arrival_pixels"):
            if f.get(key) != e[key]:
                problems.append(f"{f['id']}: {key} differs from the catalog")
        if f.get("grid_wh") != [e["width"], e["height"]]:
            problems.append(f"{f['id']}: grid_wh differs from the catalog")
        test = (e["country"], e["year"]) in TEST_SEASONS
        expected = ("test", None) if test else ("dev", FOLD_OF_YEAR.get(e["year"]))
        if expected[1] is None and not test:
            problems.append(f"{f['id']}: no fold rule for year {e['year']}")
        elif (f.get("split"), f.get("fold")) != expected:
            problems.append(f"{f['id']}: split and fold must be {expected} (season rule)")
        w24 = approx_windows(e["start_utc"], e["end_utc"], 24.0)
        w12 = approx_windows(e["start_utc"], e["end_utc"], 12.0)
        if (f.get("approx_windows_24h"), f.get("approx_windows_12h")) != (w24, w12):
            problems.append(f"{f['id']}: approx window counts must be {w24} (24 h) and {w12} (12 h)")
        flags = set(f.get("flags", []))
        if not flags <= FLAGS:
            problems.append(f"{f['id']}: unknown flags {sorted(flags - FLAGS)}")
        if ("too_short_24h" in flags) != (w24 == 0):
            problems.append(f"{f['id']}: too_short_24h must be set exactly when no 24 h window exists")
        no_rows = f.get("c651_role") in ("none", "test_declared_no_rows")
        if ("no_c651_rows" in flags) != no_rows:
            problems.append(f"{f['id']}: no_c651_rows must match c651_role")
    holdout = splits["splits"]["fresh_holdout"]
    if not holdout.get("locked", False):
        problems.append("fresh_holdout must stay locked until a final claim")
    if sorted(holdout.get("fires", [])) != sorted(fires("fresh_holdout", splits=splits)):
        problems.append("fresh_holdout.fires must list exactly the fires whose split is fresh_holdout")
    # Fires whose rectangles overlap in space and time may be one fire or complex: keep them together.
    split_of = {f["id"]: (f["split"], f["fold"]) for f in records}
    for a, b in itertools.combinations([e for e in catalog if e["id"] in split_of], 2):
        if _overlap(a, b) and split_of[a["id"]] != split_of[b["id"]]:
            problems.append(f"{a['id']} and {b['id']} overlap in space and time but differ in split or fold")
    if problems:
        raise ValueError("SPLITS.json check failed:\n  " + "\n  ".join(problems))


def _overlap(a: dict, b: dict) -> bool:
    w1, s1, e1, n1 = a["bounds_wgs84"]
    w2, s2, e2, n2 = b["bounds_wgs84"]
    t = datetime.fromisoformat
    space = w1 < e2 and w2 < e1 and s1 < n2 and s2 < n1
    time = t(a["start_utc"]) < t(b["end_utc"]) and t(b["start_utc"]) < t(a["end_utc"])
    return space and time
