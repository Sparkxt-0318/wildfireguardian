"""Error inventory of the C5 baseline audit for the precision evaluation of 2026-10-17.

Joins the audit table of the baseline run (results/runs/precision_20261017/audit/items.csv,
written by `python -m wfglink verify audit`: every scored detection and label of the 40 C5
tiles with its frame-level status, its track, whether the track was confirmed, drawn by the
booth or made a gate crossing) with the blind agent categories
(results/validation/precision_20261017/audit/c5_audit_categories.json: two categorisers and an
adjudicator per sheet). Writes, next to the categories:

- c5_error_inventory.csv: one row per audited item with its status, track fields and categories;
- c5_audit_summary.json: counts by status and category, the share of false positives that survive
  track confirmation, are drawn by the booth or cross the gate, and the categorisers' agreement;
- c5_audit_examples.jpg: one credited example sheet per main category (under 5 MB).

The categories are agent-only (PROVISIONAL), and the audit run is development evidence.

    python scripts/precision_audit_summary.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/runs/precision_20261017/audit"
OUT = ROOT / "results/validation/precision_20261017/audit"
CREDIT = ("Video: NIST Emberometer firebrand shower test (C5, public domain, credit NIST). "
          "Sheets: wfglink precision audit 2026-10-17. Categories are agent-only (PROVISIONAL).")
EXAMPLES = [("fp", "codec_artifact"), ("fp", "reflection"), ("fp", "fixture_light"), ("fp", "true_ember"),
            ("tp", "true_ember"), ("fn", "detected_but_displaced"), ("fn", "missed_merged_or_crowded"),
            ("fn", "missed_large_or_saturated")]


def _flag(s: pd.Series) -> pd.Series:
    return s.map(lambda v: str(v).lower() == "true")


def inventory() -> pd.DataFrame:
    items = pd.read_csv(RUN / "items.csv")
    cats = {r["item_id"]: r for r in json.loads((OUT / "c5_audit_categories.json").read_text())["items"]}
    rows = []
    for _, it in items.iterrows():
        c = cats.get(it["item_id"]) or {}
        fin, a, b = c.get("final") or {}, c.get("A") or {}, c.get("B") or {}
        rows.append({**{k: it[k] for k in ("item_id", "kind", "tile_id", "frame", "t", "status", "x", "y", "length",
                                            "track_id", "track_static", "confirmed_at_frame", "booth_drawn",
                                            "track_has_crossing", "label_confidence", "nearest_det_px")},
                     "category": fin.get("category"), "confidence": fin.get("confidence"),
                     "ember_present_at_mark": fin.get("ember_present_at_mark"),
                     "category_A": a.get("category"), "category_B": b.get("category"),
                     "adjudicated": bool(c.get("adjudicated")), "note": fin.get("note", "")})
    return pd.DataFrame(rows)


def summary(inv: pd.DataFrame) -> dict:
    by = {st: dict(Counter(g["category"])) for st, g in inv.groupby("status")}
    fp = inv[inv["status"] == "fp"]
    conf, drawn, cross = _flag(fp["confirmed_at_frame"]), _flag(fp["booth_drawn"]), _flag(fp["track_has_crossing"])
    fp_by = {}
    for cat, g in fp.groupby("category"):
        fp_by[cat] = {"n": int(len(g)), "with_track": int(g["track_id"].notna().sum()),
                      "confirmed": int(_flag(g["confirmed_at_frame"]).sum()),
                      "booth_drawn": int(_flag(g["booth_drawn"]).sum()),
                      "crossing": int(_flag(g["track_has_crossing"]).sum())}
    both = inv["category_A"].notna() & inv["category_B"].notna()
    return {"schema_version": 1, "run": "baseline f9e72c2 C5_multiscale (Linux reproduction: TP 24, FP 156, FN 20)",
            "tag": "agent-labeled, PROVISIONAL, development evidence",
            "n_items": int(len(inv)), "by_status": {k: int(v) for k, v in inv["status"].value_counts().items()},
            "categories_by_status": by,
            "fp": {"n": int(len(fp)), "with_track": int(fp["track_id"].notna().sum()), "confirmed": int(conf.sum()),
                   "booth_drawn": int(drawn.sum()), "crossing": int(cross.sum()), "by_category": fp_by,
                   "unlabelled_real_embers": int((fp["category"] == "true_ember").sum())},
            "agreement": {"items_with_both": int(both.sum()),
                          "same_category": int((inv.loc[both, "category_A"] == inv.loc[both, "category_B"]).sum()),
                          "adjudicated": int(inv["adjudicated"].sum())},
            "credit": CREDIT}


def examples(inv: pd.DataFrame, path: Path) -> list[str]:
    panels, chosen = [], []
    for st, cat in EXAMPLES:
        g = inv[(inv["status"] == st) & (inv["category"] == cat)]
        if not len(g):
            continue
        g = g.sort_values(["confidence", "item_id"], key=lambda s: s.map({"sure": 0, "unsure": 1}) if s.name == "confidence" else s)
        r = g.iloc[0]
        kind = "det" if r["kind"] == "detection" else "lab"
        src = next((p for p in (RUN / "sheets_blind" / f"{kind}_{r['item_id']}.jpg",
                                RUN / "sheets_blind" / f"{kind}_{r['item_id']}.png") if p.exists()), None)
        if src is None:
            continue
        im = Image.open(src).convert("RGB")
        im = im.resize((im.width // 2, im.height // 2))
        bar = Image.new("RGB", (im.width, 22), (20, 20, 20))
        ImageDraw.Draw(bar).text((6, 5), f"{r['item_id']}: {st.upper()}, {cat} ({r['confidence']})", fill=(255, 255, 255))
        panel = Image.new("RGB", (im.width, im.height + 22))
        panel.paste(bar, (0, 0))
        panel.paste(im, (0, 22))
        panels.append(panel)
        chosen.append(str(r["item_id"]))
    if not panels:
        return []
    w, h = max(p.width for p in panels), max(p.height for p in panels)
    rows = (len(panels) + 1) // 2
    sheet = Image.new("RGB", (2 * w, rows * h + 30), (0, 0, 0))
    for i, p in enumerate(panels):
        sheet.paste(p, ((i % 2) * w, (i // 2) * h))
    ImageDraw.Draw(sheet).text((8, rows * h + 9), CREDIT, fill=(230, 230, 230))
    sheet.save(path, quality=85)
    return chosen


def main() -> int:
    inv = inventory()
    inv.to_csv(OUT / "c5_error_inventory.csv", index=False, lineterminator="\n")
    s = summary(inv)
    s["examples"] = {"file": "c5_audit_examples.jpg", "items": examples(inv, OUT / "c5_audit_examples.jpg")}
    (OUT / "c5_audit_summary.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps({k: s[k] for k in ("by_status", "fp", "agreement")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
