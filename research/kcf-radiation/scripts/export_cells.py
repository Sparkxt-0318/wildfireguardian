"""Per road cell and input: the step-3 table (flame length, height, flux at the road from the adjacent cell, zone,
safe distances, leads, closure times for no heat / old law / baseline), one CSV.gz per panel.

    python scripts/export_cells.py PANEL_DIR OUT_DIR
"""
import csv, gzip, json, sys
from pathlib import Path

COLS = ["panel", "region", "issue_utc", "cell", "arrival_s", "ros_m_min", "lc_class", "fuel_group", "wind10_m_s", "rh_pct",
        "I_surface_kw_m", "crown", "cfb", "I_total_kw_m", "flame_length_m", "tilt_deg", "flame_height_m",
        "dstar_7_m", "dstar_4.7_m", "dstar_2.5_m", "lead_7_s", "lead_4.7_s", "lead_2.5_s",
        "adjacent_distance_m", "flux_from_adjacent_kw_m2", "zone_from_adjacent",
        "close_min_s_none", "close_min_s_old_7", "close_min_s_old_4.7", "close_min_s_old_2.5",
        "close_min_s_baseline_7", "close_min_s_baseline_4.7", "close_min_s_baseline_2.5"]

def main():
    pdir, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for panel in ("A", "B"):
        with gzip.open(out / ("road_cells_panel_%s.csv.gz" % panel), "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLS)
            for p in sorted(pdir.glob("%s_*.json.gz" % panel)):
                d = json.load(gzip.open(p, "rt"))
                for c in d["cells"]:
                    c = dict(c, panel=panel)
                    w.writerow(["" if c.get(k) is None else c.get(k) for k in COLS])

if __name__ == "__main__":
    main()
