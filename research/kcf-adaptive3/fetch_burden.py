#!/usr/bin/env python3
"""Fetch issued GFS 0.25 deg forecasts over Korea for the burden set (PROTOCOL.md section 6, target A).

Same source, cycles, leads (6..18 h) and lattice as kcf-aloft/fetch_gfs.py (imported), but with 2 m relative humidity
added, because the tracker's transition model reads gust, 850 hPa wind and humidity. No value is interpreted here.

    python3 fetch_burden.py --out NWP_DIR --seasons 2021 2022 2023 2024 2025 [--procs 4]
Output: NWP_DIR/gfs_KOR/<YYYYMMDDHH>.npz, arr[lead, field, lat, lon]; fields GUST, U850, V850, RH2m.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kcf-aloft"))
import fetch_gfs  # noqa: E402

fetch_gfs.FIELDS = [("GUST", "surface"), ("UGRD", "850 mb"), ("VGRD", "850 mb"), ("RH", "2 m above ground")]
fetch_gfs.HGT_LEADS = ()

if __name__ == "__main__":
    fetch_gfs.main()
