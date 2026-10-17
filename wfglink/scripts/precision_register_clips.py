"""Register the USFS archive videos fetched for the precision evaluation as clips.

For every record in results/validation/precision_20261017/fetch_receipts.jsonl this writes
data/clips/<clip_id>.yaml (whole recording, no ROI, the split from the content-blind selection)
and a provenance row in data/clips.csv (container metadata probed with PyAV, no frames decoded).
Afterwards `python scripts/fetch_clips.py --sources` rebuilds the clip table in data/SOURCES.md.

    python scripts/precision_register_clips.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import av

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / "results/validation/precision_20261017/fetch_receipts.jsonl"
CSV = ROOT / "data/clips.csv"

ARCHIVES = {
    "C8": {
        "title": "Fire Behavior Assessment Team: in-fire videos (RDS-2021-0069)",
        "page_url": "https://doi.org/10.2737/RDS-2021-0069",
        "license": "US Government funded data: usable without additional permissions or fees; citation required",
        "credit": ("Reiner, A.L.; Ewell, C.M.; Fites-Kaufman, J.A.; Dailey, S.N.; Noonan-Wright, E.K.; Norman, T.P.; "
                   "Vaillant, N.M.; Dickinson, M.B.; Morgan, C.; Courson, M.; Campbell, M. 2021. Fire Behavior "
                   "Assessment Team: in-fire videos. Updated 17 April 2024. Fort Collins, CO: Forest Service Research "
                   "Data Archive. https://doi.org/10.2737/RDS-2021-0069"),
        "camera_type": "fixed in-fire video camera in a fire-resistant box (FBAT plot)",
        "event": "wildland fire {fire}, FBAT plot {plot}",
    },
    "C7": {
        "title": "Firebrand generation from trees, outdoor tree-scale burns (RDS-2022-0071)",
        "page_url": "https://doi.org/10.2737/RDS-2022-0071",
        "license": "US Government funded data: usable without additional permissions or fees; citation required",
        "credit": ("Hudson, T.R.; Blunck, D.L. 2022. Videos, images, and processed results from laboratory and field "
                   "studies of firebrand generation from trees. Fort Collins, CO: Forest Service Research Data Archive. "
                   "https://doi.org/10.2737/RDS-2022-0071"),
        "camera_type": "tripod camera at an outdoor tree burn",
        "event": "outdoor tree burn, test {test}",
    },
}
SPLIT = {"calibration": "calibration", "test": "test", "test_negative_footage": "test"}


def probe(path: Path) -> dict:
    c = av.open(str(path))
    s = c.streams.video[0]
    out = {"width": s.codec_context.width, "height": s.codec_context.height,
           "fps": round(float(s.average_rate or 0), 3), "codec": s.codec_context.name,
           "duration_s": round(float(c.duration / av.time_base), 3) if c.duration else ""}
    c.close()
    return out


def main() -> int:
    recs = [json.loads(line) for line in RECEIPTS.read_text().splitlines() if line.strip()]
    with open(CSV, newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    have = {r["clip_id"] for r in rows}
    for rec in recs:
        raw = Path(rec["file"]).name if "raw_name" not in rec else rec["raw_name"]
        clip_id = raw.rsplit(".", 1)[0]
        grp = rec["clip_group"]
        a = ARCHIVES[grp]
        parts = rec["member"].split("/")
        prefix = not rec["whole_member"]
        meta = probe(ROOT / "data/raw" / raw)
        if grp == "C8":
            fire, base = parts[1], parts[-1]
            event = a["event"].format(fire=fire, plot=base.split("_")[0].split(".")[0])
        else:
            event = a["event"].format(test=parts[-1].rsplit(".", 1)[0])
        notes = (f"file {raw}; {rec['bytes_written']} bytes; archive member {rec['member']}"
                 + (f" (first {rec['bytes_written']} bytes of a {rec['member_bytes']} byte member; truncated, "
                    "the container duration describes the whole member)" if prefix else "; CRC-32 checked")
                 + f"; precision_20261017 role {rec['role']}")
        row = {k: "" for k in fields}
        row.update({"clip_id": clip_id, "title": f"{a['title']}: {rec['member']}", "source": "fs.usda.gov (Box)",
                    "page_url": a["page_url"], "media_url": rec["archive_url"], "license": a["license"],
                    "credit_line": a["credit"], "permission_notes": "archive use constraints: no additional permissions or fees; cite",
                    "date_accessed": rec["fetched_at"][:10], "event_location": event,
                    "duration_s": meta["duration_s"] if not prefix else "", "width": meta["width"],
                    "height": meta["height"], "fps": meta["fps"], "codec": meta["codec"], "sha256": rec["sha256"],
                    "camera_type": a["camera_type"], "split": SPLIT[rec["role"]], "metrics_scope": "all",
                    "notes": notes})
        if clip_id in have:
            rows = [row if r["clip_id"] == clip_id else r for r in rows]
        else:
            rows.append(row)
        yml = ROOT / "data/clips" / f"{clip_id}.yaml"
        yml.write_text(
            f"# Clip settings for file mode (python -m wfglink process data/clips/{clip_id}.yaml).\n"
            f"# Fetched for the precision evaluation of 2026-10-17 by a content-blind seeded selection\n"
            f"# (results/validation/precision_20261017/data_selection.json); role: {rec['role']}.\n"
            f"clip_id: {clip_id}\nfile: data/raw/{raw}\nsplit: {SPLIT[rec['role']]}\nmetrics_scope: all\nroi: null\n"
            f"# The whole recording is analysed; no segment was chosen by looking at the content.\n"
            f"segments_s: null\ngate: null\ndistance_m: null\npeak_gust_ms: null\ngust_source: null\n"
            f"z_interval_m: null\nfocal_px: null\nhfov_deg: null\ndrift_deg: null\ndrift_basis: null\n"
            f"drift_tolerance_deg: null\nnotes: >\n  {a['title']}. {event}. Timebase assumed real time\n"
            f"  (not verified against an external clock).\n")
        print(f"{clip_id}: {meta}")
    rows.sort(key=lambda r: r["clip_id"])
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
