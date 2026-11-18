"""Assemble numbers.json from the committed outputs. Usage: python3 build_numbers.py   (run from anywhere)"""
import json
from pathlib import Path

H = Path(__file__).resolve().parent
S3 = json.loads((H / "out/s3_satellite_extent.json").read_text())
S3X = json.loads((H / "out/s3_exploratory.json").read_text())
TW = json.loads((H / "out/twin_summary.json").read_text())
NI = json.loads((H / "out/nist_lag.json").read_text())
JA = json.loads((H / "out/jaenan_summary.json").read_text())
KD = json.loads((H / "out/kec_daily_summary.json").read_text())
num = {
    "label": "Model output on reconstructed inputs or synthetic truth. Not what happened to people.",
    "protocol": "research/kcf-validate/PROTOCOL.md (amendments 1-2)",
    "sources": {
        "1_KEC_traffic": {"status": "PARTLY_OBTAINED_DAILY_ONLY", "why": "user-supplied dataset 512 daily section volumes 22-27 Mar; 15-minute API 0305 needs a key, 15-minute files need a login; closure times and surges not derivable"},
        "2_emergency_texts": {"status": "OBTAINED", "why": "user-supplied export (62,192 rows), 312 messages for the five counties + 경북 전체, 22-27 Mar 2025; 23 of 29 REPORTED rows replaced"},
        "3_satellite": {"status": "OBTAINED_IN_PART", "scene": "Sentinel-2 L2A 2025-03-24 02:17 UTC (52SDF, 52SEF); GK-2A needs data.kma.go.kr + login (not attempted); Landsat not used"},
        "4_NIST_Camp_Fire": {"status": "PARTLY_OBTAINED", "why": "tables extracted from the two PDFs; no fire-arrival field; roadlayer run on Paradise NOT run (no field, no Paradise graph)"},
        "5_twin": {"status": "RUN", "seeds": TW["seeds"]},
        "6_prospective_log": {"status": "STARTED_NO_ENTRY", "why": "no active Korean fire identified (web search only; FIRMS/KFS unreachable)"},
    },
    "reported_rows_replaced_by_official_records": 23,
    "reported_rows_in_roadcut_validation_table": 29,
    "reading_notes": [
        "source5_twin.arms.*.places_pooled.cutoff_err_min_system_minus_true has median 0 and p90 0 only because 103 of 214 places were already cut at issue (error exactly 0). Quote places_split.truth_cut_inside_horizon instead (n=111, median -175.6 min).",
        "source3 primary map is maps.raw_dnbr0.1 (frozen); the other three maps are sensitivity, and burned area differs more than 13-fold between them.",
        "source3 coverage_newly_burned_* counts burned cells outside the known area at the issue time; the exploratory block shows none was detected by FIRMS/AHI between issue and t_S.",
    ],
    "source3_sentinel2_24mar": {"t_S_utc": S3["t_S_utc"], "choi_hours_at_t_S": S3["choi_hours_at_t_S"], "zones": S3["zones"],
                                "maps": S3["maps"], "exploratory": S3X},
    "source4_nist_camp_fire": NI,
    "source2_jaenan_munja": JA,
    "source1_kec_daily": KD,
    "source5_twin": TW,
}
(H / "numbers.json").write_text(json.dumps(num, indent=1))
print("numbers.json written,", (H / "numbers.json").stat().st_size, "bytes")
