"""Records the remaining numbers quoted in README, RESULTS and LOG: measured literature values
(kind "measured"), and derived summary statistics computed from saved results and OpenMRG.

Usage: .venv/bin/python -I src/run_extras.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import RESULTS, load_config, record  # noqa: E402
from detect import alarm_onsets  # noqa: E402
from physics import FireColumn  # noqa: E402
from run_detection import DT, dry_chunks, load_openmrg, observe, wet_mask_from_gauges  # noqa: E402


def main():
    lit = {
        "lit.mphale2007.loss_min_db": (1.64, "dB", "Mphale and Heron 2007 J Phys D, min relative attenuation 8-10.5 GHz (S1)"),
        "lit.mphale2007.loss_max_db": (5.68, "dB", "Mphale and Heron 2007, max relative attenuation, 8 GHz at 72 s (S1)"),
        "lit.mphale2007.ne_min": (0.51e16, "m^-3", "Mphale and Heron 2007, min inverted electron density (S1)"),
        "lit.mphale2007.ne_max": (1.35e16, "m^-3", "Mphale and Heron 2007, max inverted electron density (S1)"),
        "lit.mphale2007.nu_min": (3.43e10, "s^-1", "Mphale and Heron 2007, min collision frequency (S1)"),
        "lit.mphale2007.nu_max": (5.97e10, "s^-1", "Mphale and Heron 2007, max collision frequency (S1)"),
        "lit.mphale2007.burner_diameter_m": (0.5, "m", "Burner internal diameter (S1)"),
        "lit.grassfire_vhf_total_db_min": (0.03, "dB", "Grassfire VHF total loss over 44 m, lower (S4)"),
        "lit.grassfire_vhf_total_db_max": (0.05, "dB", "Grassfire VHF total loss over 44 m, upper (S4)"),
        "lit.canefire_151MHz_total_db": (0.43, "dB", "Sugarcane fire 151 MHz total over 590 m (S5)"),
        "lit.euroka_bound_db": (5.0, "dB", "Operation Euroka UHF and X band bound over about 40 m (S8, second hand)"),
        "lit.euroka_path_m": (40.0, "m", "Operation Euroka path through fire (S8, second hand)"),
        "lit.bystrov_max_db_per_m": (0.13, "dB/m", "Bystrov et al. 2021 max smoke or flame loss at 79 and 300 GHz (S13)"),
        "lit.ericsson_ne_asia_microwave_share": (0.06, "fraction", "Microwave share of backhaul in North East Asia to 2030 (S40)"),
        "lit.kfs_cameras": (1971, "count", "Korea Forest Service fire surveillance cameras (S45)"),
        "lit.kt_link_freq_max_ghz": (10, "GHz", "KT microwave relays at 10 GHz or less (S37)"),
        "lit.uiseong.burned_ha": (99289, "ha", "Official forest damage, five counties (S23)"),
        "lit.uiseong.peak_spread_kmh": (8.2, "km/h", "Reported peak spread (S23)"),
        "lit.uiseong.gust_m_s": (27, "m/s", "Reported maximum gust (S23)"),
        "lit.uiseong.rh_min_pct": (16, "%", "Relative humidity 18:00 23 March 2025 (S23)"),
        "lit.uiseong.rain_mm_min": (1, "mm", "Rain 27-28 March 2025, lowest county total (S23)"),
        "lit.uiseong.rain_mm_max": (3, "mm", "Rain 27-28 March 2025, highest county total (S23)"),
        "lit.uiseong.dead": (26, "count", "Deaths in the five Gyeongbuk counties (S23)"),
        "lit.uiseong.track_km": (50, "km", "Uiseong to Yeongdeok coast, 14:00 25 March to 02:00 26 March (S23)"),
        "lit.openmrg.size_bytes": (317994487, "bytes", "OpenMRG.zip size (D2)"),
    }
    record(lit, "src/run_extras.py", None, kind="measured")

    nums = {}
    pcfg = load_config("physics.json")
    col = FireColumn(30000, 30.0, pcfg["T_flame_K"], 1.35e16, 3.43e10, T_amb=pcfg["T_amb_K"], rh=pcfg["rh_amb"])
    nums["phys.dN_flame_vs_ambient"] = (float(col.N_thermal(np.array([1.0]))[0] - col.N_ambient()), "N-units",
                                        "Thermal refractivity change inside the 1100 K flame band")

    far = pd.read_csv(RESULTS / "detection" / "far.csv")
    g = far[(far.scheme == "s10") & (far.detector == "drop") & (far.thr == 3.0)].set_index("noise").far_per_link_day
    nums["conf.far.wet_over_screened_s10_drop3"] = (float(g["wet"] / g["screened"]), "ratio",
                                                    "Rainy-period over screened-dry false alarm rate, 10 s drop >= 3 dB")

    cfg = load_config("detection.json")
    rng = np.random.default_rng(cfg["seed"])  # same draw of sub-links as run_detection.py
    x, _ = load_openmrg(cfg, cfg["n_sublinks"], rng)
    wet = wet_mask_from_gauges(x.index, cfg)
    rows = []
    for sl, _, arr in dry_chunks(x, wet, cfg["min_chunk_h"] * 3600):
        step, st = observe(arr, "s10")
        w = int(cfg["warmup_h"] * 3600 / step)
        rows.append({"sl": sl, "days": (len(arr) - w) * DT / 86400, "n": len(alarm_onsets(st["drop"][w:], 3.0, 360))})
    d = pd.DataFrame(rows).groupby("sl").sum()
    d = d[d.days > 0].sort_values("n", ascending=False)
    top = d.n.head(max(len(d) // 10, 1)).sum() / d.n.sum()
    nums["det.noise.share_alarms_worst10pct"] = (float(top), "fraction", "Share of dry 3 dB drop alarms from the worst 10 percent of sub-links")
    nums["det.noise.share_sublinks_no_alarm"] = (float((d.n == 0).mean()), "fraction", "Share of sub-links with no dry 3 dB drop alarm")
    nums["det.noise.median_dry_days_per_sublink"] = (float(d.days.median()), "days", "Median dry days analysed per sub-link")
    record(nums, "src/run_extras.py", "configs/detection.json")
    print({k: v[0] for k, v in nums.items()})


if __name__ == "__main__":
    main()
